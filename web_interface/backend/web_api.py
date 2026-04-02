#!/usr/bin/env python3
"""
FastAPI Web Interface for AI Patent Pipeline
Integrated with existing pipeline structure
"""

import os
import sys
import uuid
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

# Add current directory to path for imports
current_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(current_dir))

# Load .env from PDKI directory (same as pdki_pipeline.py)
_env_file = current_dir / "PDKI" / ".env"
if _env_file.exists():
    with open(_env_file) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

# Import the existing pipeline
from main_patent_pipeline import PatentPipeline

# Import search history database
from utils.search_history_db import SearchHistoryDB

# Import analysis database
from utils.analysis_db import AnalysisDB

# Job storage (in production, use Redis or database)
jobs: Dict[str, Dict] = {}

# Categorization job tracker
categorization_jobs: Dict[str, Dict] = {}

# Initialize search history database
history_db = SearchHistoryDB()

# Initialize analysis database
analysis_db = AnalysisDB()

app = FastAPI(
    title="AI Patent Pipeline Web Interface",
    description="Web interface for patent extraction and analysis",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup event: cleanup old database entries
@app.on_event("startup")
async def startup_event():
    """Run cleanup on startup"""
    try:
        deleted_count = history_db.cleanup_old_entries(months=3)
        print(f"🧹 Startup cleanup: Removed {deleted_count} entries older than 3 months")
    except Exception as e:
        print(f"⚠️  Startup cleanup failed: {e}")

# Request/Response Models
class PipelineRequest(BaseModel):
    source: str = "pubchem"  # "pubchem" or "drugbank"
    keyword: Optional[str] = None  # Required for pubchem
    drugbank_id: Optional[str] = None  # Required for drugbank
    countries: List[str] = ["US"]
    max_families: int = 3
    max_main_patents: Optional[int] = None  # None = get all results
    export_sheets: bool = True

class PipelineResponse(BaseModel):
    job_id: str
    status: str
    message: str

class JobStatus(BaseModel):
    job_id: str
    status: str  # "queued", "running", "completed", "failed"
    progress: int  # 0-100
    current_stage: str
    created_at: str
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    results: Optional[Dict] = None
    sheets_url: Optional[str] = None  # Google Sheets URL when available

def create_job(job_id: str, source: str, keyword: Optional[str], drugbank_id: Optional[str],
               countries: List[str], max_families: int, max_main_patents: Optional[int] = None) -> Dict:
    """Create a new job entry"""
    return {
        "job_id": job_id,
        "status": "queued",
        "progress": 0,
        "current_stage": "Initializing...",
        "source": source,
        "keyword": keyword,
        "drugbank_id": drugbank_id,
        "countries": countries,
        "max_families": max_families,
        "max_main_patents": max_main_patents,
        "created_at": datetime.now().isoformat(),
        "completed_at": None,
        "error_message": None,
        "results": None,
        "output_file": None,
        "sheets_url": None
    }

async def run_pipeline_job(job_id: str, source: str, keyword: Optional[str],
                          drugbank_id: Optional[str], countries: List[str],
                          max_families: int, max_main_patents: Optional[int] = None,
                          export_sheets: bool = True):
    """Background task to run the patent pipeline"""
    try:
        # Update job status
        jobs[job_id]["status"] = "running"
        jobs[job_id]["current_stage"] = "Starting pipeline..."
        jobs[job_id]["progress"] = 5

        # Define progress callback to update job status
        def update_progress(progress: int, message: str):
            """Callback function to update job progress in real-time"""
            jobs[job_id]["progress"] = min(progress, 95)  # Cap at 95%, leave 5% for finalization
            jobs[job_id]["current_stage"] = message

        # Create and run pipeline with progress callback
        pipeline = PatentPipeline(
            keyword=keyword,
            drugbank_id=drugbank_id,
            source=source,
            max_families=max_families,
            target_countries=countries,
            max_main_patents=max_main_patents,
            export_to_sheets=export_sheets,
            progress_callback=update_progress
        )

        # Run the pipeline in executor to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        output_file = await loop.run_in_executor(None, pipeline.run_pipeline)

        jobs[job_id]["progress"] = 95
        jobs[job_id]["current_stage"] = "Finalizing results..."

        # Capture sheets_url with debug
        sheets_url = getattr(pipeline, 'sheets_url', None)
        print(f"\n🔍 DEBUG BACKEND:")
        print(f"  - Pipeline has 'sheets_url' attr: {hasattr(pipeline, 'sheets_url')}")
        print(f"  - sheets_url value: {sheets_url}")
        print(f"  - sheets_url type: {type(sheets_url)}")

        # Prepare results
        search_term = keyword if source == "pubchem" else drugbank_id

        # Get drug name for DrugBank sources
        drug_name = getattr(pipeline, 'drug_name', None)
        display_name = drug_name if source == "drugbank" and drug_name else search_term

        results = {
            "total_patents": len(pipeline.all_patents),
            "duplicates_removed": pipeline.duplicates_removed,
            "countries": countries,
            "source": source,
            "keyword": keyword if source == "pubchem" else None,
            "drugbank_id": drugbank_id if source == "drugbank" else None,
            "drug_name": drug_name if source == "drugbank" else None
        }

        # Update job completion
        jobs[job_id].update({
            "status": "completed",
            "progress": 100,
            "current_stage": "Completed successfully",
            "completed_at": datetime.now().isoformat(),
            "results": results,
            "output_file": output_file,
            "sheets_url": sheets_url
        })

        print(f"  - Job sheets_url stored: {jobs[job_id].get('sheets_url')}")
        print(f"🔍 DEBUG END\n")

        # Save to search history database
        try:
            # Extract spreadsheet ID from URL for future deletion (Phase 2)
            spreadsheet_id = None
            if sheets_url:
                try:
                    # Extract ID from URL: https://docs.google.com/spreadsheets/d/{ID}/edit...
                    spreadsheet_id = sheets_url.split('/d/')[1].split('/')[0]
                except:
                    pass

            history_db.add_search(
                keyword=search_term,
                google_sheets_url=sheets_url if sheets_url else None,
                source=source,
                display_name=display_name,
                spreadsheet_id=spreadsheet_id,
                output_file=output_file
            )
            print(f"✅ Saved search to history database: {source} - {display_name} ({search_term})")
        except Exception as db_error:
            print(f"⚠️  Failed to save to history database: {db_error}")

    except Exception as e:
        # Update job failure
        jobs[job_id].update({
            "status": "failed",
            "current_stage": "Failed",
            "completed_at": datetime.now().isoformat(),
            "error_message": str(e)
        })

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the frontend HTML"""
    frontend_path = current_dir / "web_interface" / "frontend" / "index.html"
    return FileResponse(frontend_path)

@app.post("/api/v1/pipeline/start", response_model=PipelineResponse)
async def start_pipeline(request: PipelineRequest, background_tasks: BackgroundTasks):
    """Start a new pipeline job"""

    # Validate request based on source
    if request.source == "pubchem":
        if not request.keyword or not request.keyword.strip():
            raise HTTPException(status_code=400, detail="Keyword is required when source is 'pubchem'")
    elif request.source == "drugbank":
        if not request.drugbank_id or not request.drugbank_id.strip():
            raise HTTPException(status_code=400, detail="DrugBank ID is required when source is 'drugbank'")
    else:
        raise HTTPException(status_code=400, detail="Invalid source. Must be 'pubchem' or 'drugbank'")

    if not request.countries:
        request.countries = ["US"]

    # Generate job ID
    job_id = str(uuid.uuid4())

    # Create job entry
    jobs[job_id] = create_job(job_id, request.source, request.keyword, request.drugbank_id,
                              request.countries, request.max_families, request.max_main_patents)

    # Start background task
    background_tasks.add_task(
        run_pipeline_job,
        job_id,
        request.source,
        request.keyword,
        request.drugbank_id,
        request.countries,
        request.max_families,
        request.max_main_patents,
        request.export_sheets
    )

    search_term = request.keyword if request.source == "pubchem" else request.drugbank_id
    return PipelineResponse(
        job_id=job_id,
        status="queued",
        message=f"Pipeline started from {request.source.upper()}: {search_term}"
    )

@app.get("/api/v1/pipeline/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    """Get the status of a pipeline job"""

    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]
    return JobStatus(**job)

@app.get("/api/v1/pipeline/{job_id}/download")
async def download_results(job_id: str):
    """Download the JSON results file"""

    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]

    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Job not completed")

    output_file = job.get("output_file")
    if not output_file or not os.path.exists(output_file):
        raise HTTPException(status_code=404, detail="Results file not found")

    # Determine filename based on source
    source = job.get("source", "pubchem")
    search_term = job.get("keyword") if source == "pubchem" else job.get("drugbank_id")
    filename = f"{search_term}_patents.json" if search_term else "patents.json"

    return FileResponse(
        output_file,
        media_type='application/json',
        filename=filename
    )

@app.get("/api/v1/jobs")
async def list_jobs():
    """List all jobs (for debugging/admin)"""
    return {"jobs": list(jobs.values())}

@app.delete("/api/v1/pipeline/{job_id}")
async def delete_job(job_id: str):
    """Delete a job from memory"""

    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    del jobs[job_id]
    return {"message": "Job deleted"}

@app.get("/api/v1/history")
async def get_search_history(limit: int = 100):
    """
    Get search history

    Args:
        limit: Maximum number of records to return (default: 100)

    Returns:
        List of search history entries with keyword and Google Sheets URL
    """
    try:
        history = history_db.get_history(limit=limit)
        return {
            "success": True,
            "count": len(history),
            "history": history
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve history: {str(e)}")


# IMPORTANT: More specific routes must come BEFORE generic routes
# /clear must be before /{history_id} to avoid routing conflicts
@app.delete("/api/v1/history/clear")
async def clear_all_history():
    """
    Clear all search history

    Returns:
        Success status and count of deleted entries
    """
    try:
        print("\n🔍 DEBUG: Clear all history endpoint called")

        # Delete all from database
        deleted_entries = history_db.clear_all_history()
        print(f"   - Deleted {len(deleted_entries)} entries from database")

        # Delete all JSON files and Google Sheets
        files_deleted = []
        files_failed = []
        sheets_deleted = []
        sheets_failed = []

        # Initialize Google Sheets exporter for deletion
        sheets_exporter = None
        try:
            from google_sheets_integration.google_sheets_exporter import GoogleSheetsExporter
            sheets_exporter = GoogleSheetsExporter(use_oauth=True)
            print("   - Google Sheets exporter initialized for deletion")
        except Exception as init_error:
            print(f"   ⚠️  Could not initialize Google Sheets exporter: {init_error}")

        for entry in deleted_entries:
            # Delete JSON file
            if entry.get('output_file'):
                output_file_path = entry['output_file']
                print(f"   - Attempting to delete file: {output_file_path}")

                try:
                    output_file = Path(output_file_path)
                    if output_file.exists():
                        output_file.unlink()
                        files_deleted.append(str(output_file))
                        print(f"     ✅ Deleted: {output_file}")
                    else:
                        print(f"     ⚠️  File not found: {output_file}")
                except Exception as file_error:
                    print(f"     ❌ Failed to delete: {file_error}")
                    files_failed.append(str(output_file_path))

            # Delete Google Sheet (Phase 2)
            if entry.get('spreadsheet_id') and sheets_exporter:
                spreadsheet_id = entry['spreadsheet_id']
                print(f"   - Attempting to delete Google Sheet: {spreadsheet_id}")

                try:
                    result = sheets_exporter.delete_spreadsheet(spreadsheet_id)
                    if result.get('success'):
                        sheets_deleted.append(spreadsheet_id)
                        print(f"     ✅ Deleted Google Sheet: {spreadsheet_id}")
                    else:
                        sheets_failed.append(spreadsheet_id)
                        print(f"     ⚠️  Failed to delete sheet: {result.get('error', 'Unknown error')}")
                except Exception as sheet_error:
                    print(f"     ❌ Sheet deletion error: {sheet_error}")
                    sheets_failed.append(spreadsheet_id)

        print(f"✅ Cleared all history: {len(deleted_entries)} entries, {len(files_deleted)} files, {len(sheets_deleted)} sheets deleted\n")

        return {
            "success": True,
            "message": "All history cleared",
            "entries_deleted": len(deleted_entries),
            "files_deleted": len(files_deleted),
            "files_failed": len(files_failed),
            "sheets_deleted": len(sheets_deleted),
            "sheets_failed": len(sheets_failed)
        }

    except Exception as e:
        print(f"❌ Error in clear_all_history: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to clear history: {str(e)}")


@app.delete("/api/v1/history/{history_id}")
async def delete_search_history(history_id: int):
    """
    Delete a single search history entry

    Args:
        history_id: ID of the history entry to delete

    Returns:
        Success status and details of deleted entry
    """
    try:
        # Delete from database
        deleted_entry = history_db.delete_search(history_id)

        if not deleted_entry:
            raise HTTPException(status_code=404, detail="History entry not found")

        # Delete JSON file if it exists
        files_deleted = []
        if deleted_entry.get('output_file'):
            output_file = Path(deleted_entry['output_file'])
            if output_file.exists():
                try:
                    output_file.unlink()
                    files_deleted.append(str(output_file))
                    print(f"✅ Deleted JSON file: {output_file}")
                except Exception as file_error:
                    print(f"⚠️  Failed to delete JSON file: {file_error}")

        # Delete Google Sheet if spreadsheet_id exists (Phase 2)
        sheet_deleted = False
        sheet_error = None
        if deleted_entry.get('spreadsheet_id'):
            try:
                from google_sheets_integration.google_sheets_exporter import GoogleSheetsExporter
                sheets_exporter = GoogleSheetsExporter(use_oauth=True)

                spreadsheet_id = deleted_entry['spreadsheet_id']
                print(f"🔍 Attempting to delete Google Sheet: {spreadsheet_id}")

                result = sheets_exporter.delete_spreadsheet(spreadsheet_id)
                if result.get('success'):
                    sheet_deleted = True
                    print(f"✅ Deleted Google Sheet: {spreadsheet_id}")
                else:
                    sheet_error = result.get('error', 'Unknown error')
                    print(f"⚠️  Failed to delete Google Sheet: {sheet_error}")

            except Exception as sheet_error_ex:
                sheet_error = str(sheet_error_ex)
                print(f"⚠️  Could not delete Google Sheet: {sheet_error}")

        return {
            "success": True,
            "message": f"History entry {history_id} deleted",
            "deleted_entry": deleted_entry,
            "files_deleted": files_deleted,
            "sheet_deleted": sheet_deleted,
            "sheet_error": sheet_error
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete history entry: {str(e)}")


# Serve static files (CSS, JS, images)
static_path = current_dir / "web_interface" / "frontend" / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


# ─────────────────────────────────────────────────────────────────────────────
# Patent Analysis — Pydantic models
# ─────────────────────────────────────────────────────────────────────────────

class CreateAnalysisRequest(BaseModel):
    google_patent_id: str

class UpdateSearchPlanRequest(BaseModel):
    search_plan: List[Dict]

class CreateBatchRequest(BaseModel):
    searches: List[Dict]   # [{judul, nama_inventor, nama_pemegang}]
    pagination: int = 100

class UpdateCategoryRequest(BaseModel):
    category: str          # relevant | not_relevant | uncertain

class CategorizeRequest(BaseModel):
    result_ids: Optional[List[str]] = None  # None = all uncategorized


# ─────────────────────────────────────────────────────────────────────────────
# Patent Analysis — Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _convert_to_pdki_batches(searches: List[Dict]) -> List[Dict]:
    """
    Convert [{judul, nama_inventor, nama_pemegang}] to PDKI batch dicts with _tag.
    Each dict maps directly to fill_advanced_search kwargs.
    """
    batches = []
    for s in searches:
        judul         = (s.get("judul")         or "").strip() or None
        nama_inventor = (s.get("nama_inventor") or "").strip() or None
        nama_pemegang = (s.get("nama_pemegang") or "").strip() or None

        if not any([judul, nama_inventor, nama_pemegang]):
            continue  # skip fully empty rows

        tag_parts = []
        if judul:         tag_parts.append(f"title:{judul}")
        if nama_inventor: tag_parts.append(f"inventor:{nama_inventor}")
        if nama_pemegang: tag_parts.append(f"assignee:{nama_pemegang}")

        batches.append({
            "judul":         judul,
            "nama_inventor": nama_inventor,
            "nama_pemegang": nama_pemegang,
            "_tag":          " + ".join(tag_parts),
        })
    return batches


def _set_pagination(driver, n: int):
    """
    Click the pagination combobox on the PDKI search page and select n (10/50/100).
    """
    import time
    from selenium.webdriver.common.by import By

    valid = {10, 50, 100}
    target = str(n) if n in valid else "100"
    try:
        buttons = driver.find_elements(By.CSS_SELECTOR, "button[role='combobox']")
        dropdown_btn = None
        current_val  = None

        for btn in buttons:
            try:
                span = btn.find_element(By.TAG_NAME, "span")
                if span.text.strip() in ['10', '50', '100']:
                    dropdown_btn = btn
                    current_val  = span.text.strip()
                    break
            except Exception:
                continue

        if not dropdown_btn:
            return False

        if current_val == target:
            return True

        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", dropdown_btn)
        time.sleep(0.5)
        dropdown_btn.click()
        time.sleep(1.5)

        option = None
        for selector in ["div[role='option']", "li", "button"]:
            for opt in driver.find_elements(By.CSS_SELECTOR, selector):
                if opt.text.strip() == target and opt.is_displayed():
                    option = opt
                    break
            if option:
                break

        if not option:
            return False

        option.click()
        time.sleep(3)
        return True
    except Exception as exc:
        print(f"   _set_pagination error: {exc}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Patent Analysis — Background tasks
# ─────────────────────────────────────────────────────────────────────────────

async def run_extraction_job(analysis_id: str, google_patent_id: str):
    """
    Background task:
      1. Fetch Google Patent metadata via Selenium
      2. Run AI planner to build search plan
      3. Store results in analysis_db
    """
    import gc
    import time as _time

    loop = asyncio.get_event_loop()

    def _sync_extract():
        # Lazy imports to avoid startup failures
        from googlepatent_extract.google_patents_clean_extractor import (
            setup_chrome_driver,
            extract_patent_data,
        )
        url = f"https://patents.google.com/patent/{google_patent_id}"
        driver = setup_chrome_driver()
        try:
            data = extract_patent_data(driver, url)
        finally:
            driver.quit()
        return data

    def _sync_ai_plan(patent_data: dict):
        from PDKI.pdki_pipeline import ai_plan_searches
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        return ai_plan_searches(patent_data, api_key)

    try:
        # Step 1: Google Patents extraction
        patent_data = await loop.run_in_executor(None, _sync_extract)

        if patent_data.get("error"):
            raise RuntimeError(f"Google Patents extraction failed: {patent_data['error']}")

        gc.collect()
        import time as _time2
        _time2.sleep(3)

        # Step 2: AI search plan
        ai_plan = await loop.run_in_executor(None, _sync_ai_plan, patent_data)

        # Convert AI plan to flat [{term, field}] list
        search_plan_flat: List[Dict] = []
        for kw in ai_plan.get("title_keywords", []):
            search_plan_flat.append({"term": kw, "field": "title"})
        for a in ai_plan.get("assignees", []):
            search_plan_flat.append({"term": a["search_term"], "field": "assignee"})
        for inv in ai_plan.get("inventors", []):
            search_plan_flat.append({"term": inv["search_term"], "field": "inventor"})

        analysis_db.update_analysis_ready(analysis_id, patent_data, search_plan_flat)
        print(f"[extraction_job] {analysis_id} ready — {len(search_plan_flat)} plan items")

    except Exception as exc:
        print(f"[extraction_job] {analysis_id} failed: {exc}")
        analysis_db.update_analysis_error(analysis_id, str(exc))


async def run_batch_job(
    analysis_id: str,
    batch_id: str,
    searches: List[Dict],
    pagination: int,
):
    """
    Background task:
      1. Convert searches to PDKI batches
      2. Run PDKI searches, collect links
      3. Fetch detail pages for unique URLs
      4. Save results to analysis_db
    """
    import gc
    import time as _time

    loop = asyncio.get_event_loop()
    analysis_db.update_batch_status(batch_id, "running")

    pdki_batches = _convert_to_pdki_batches(searches)
    if not pdki_batches:
        analysis_db.update_batch_status(batch_id, "failed", error="No search terms provided")
        return

    def _sync_run_searches():
        import time
        from PDKI.PDKI_advanced import (
            setup_driver as setup_pdki_driver,
            wait_for_page,
            set_category_paten,
            fill_advanced_search,
            click_terapkan,
            extract_links,
        )

        driver = setup_pdki_driver()
        all_raw: List[Dict] = []   # [{url, text, tag}]
        try:
            driver.get("https://pdki-indonesia.dgip.go.id/search")
            if not wait_for_page(driver):
                raise RuntimeError("PDKI page failed to load")
            if not set_category_paten(driver):
                raise RuntimeError("Could not set category to Paten")

            _set_pagination(driver, pagination)

            for i, batch in enumerate(pdki_batches, 1):
                tag          = batch["_tag"]
                search_fields = {k: v for k, v in batch.items() if not k.startswith("_")}

                print(f"  [batch_job] {i}/{len(pdki_batches)}: {tag}")
                fill_advanced_search(driver, **search_fields)

                label = tag.replace(":", "_").replace(" ", "-")
                if not click_terapkan(driver, label=label, screenshot=False):
                    print(f"    Terapkan failed — skipping {tag}")
                    continue

                links = extract_links(driver)
                print(f"    {len(links)} links")

                for link in links:
                    all_raw.append({"url": link["url"], "text": link.get("text", ""), "tag": tag})

                if i < len(pdki_batches):
                    time.sleep(3)
        finally:
            driver.quit()

        return all_raw

    def _sync_fetch_details(unique_results: List[Dict]) -> List[Dict]:
        import time
        from PDKI.PDKI_detail_extractor import (
            setup_driver as setup_detail_driver,
            extract_detail,
        )

        driver = setup_detail_driver()
        try:
            for i, item in enumerate(unique_results, 1):
                detail = extract_detail(driver, item["url"], debug=False)
                item["detail"] = detail
                if i < len(unique_results):
                    time.sleep(2)
        finally:
            driver.quit()

        return unique_results

    try:
        # Step 1: Run searches
        all_raw = await loop.run_in_executor(None, _sync_run_searches)

        # Deduplicate by URL, merging tags
        seen: Dict[str, Dict] = {}
        for item in all_raw:
            url = item["url"]
            if url in seen:
                if item["tag"] not in seen[url]["tags"]:
                    seen[url]["tags"].append(item["tag"])
            else:
                seen[url] = {"url": url, "text": item["text"], "tags": [item["tag"]]}

        unique_items = list(seen.values())
        print(f"[batch_job] {len(all_raw)} raw hits → {len(unique_items)} unique URLs")

        gc.collect()
        import time as _time3
        _time3.sleep(3)

        # Step 2: Fetch details
        detail_inputs = [{"url": u["url"], "text": u["text"], "tags": u["tags"]} for u in unique_items]
        detail_results = await loop.run_in_executor(None, _sync_fetch_details, detail_inputs)

        # Step 3: Save to DB — each URL may have multiple tags; upsert once per tag
        results_to_upsert: List[Dict] = []
        for item in detail_results:
            tags = item.get("tags", [])
            first_tag = tags[0] if tags else ""
            results_to_upsert.append({
                "url":    item["url"],
                "text":   item.get("text", ""),
                "tag":    first_tag,
                "detail": item.get("detail"),
            })
            # Upsert extra tags
            for extra_tag in tags[1:]:
                results_to_upsert.append({
                    "url":    item["url"],
                    "text":   item.get("text", ""),
                    "tag":    extra_tag,
                    "detail": None,
                })

        upsert_stats = analysis_db.upsert_results(analysis_id, results_to_upsert)
        hit_count = upsert_stats["new"] + upsert_stats["duplicates"]

        analysis_db.update_batch_status(batch_id, "completed", hit_count=hit_count)
        print(f"[batch_job] {batch_id} completed — {hit_count} total hits, {upsert_stats['new']} new")

    except Exception as exc:
        print(f"[batch_job] {batch_id} failed: {exc}")
        analysis_db.update_batch_status(batch_id, "failed", error=str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# Patent Analysis — AI Categorisation
# ─────────────────────────────────────────────────────────────────────────────

# Lazy import — avoids startup failure if anthropic not installed
def _get_categorize_result():
    from PDKI.pdki_categorizer import categorize_result
    return categorize_result


def _sync_google_sheet(analysis_id: str):
    """Create or overwrite the Google Sheet for an analysis. Stores URL in DB."""
    try:
        from datetime import datetime as _dt
        from google_sheets_integration.google_sheets_exporter import GoogleSheetsExporter

        analysis = analysis_db.get_analysis(analysis_id)
        if not analysis:
            return

        results = analysis_db.get_results(analysis_id)
        stats   = analysis_db.get_stats(analysis_id)
        patent_data = analysis.get("patent_data") or {}

        exporter = GoogleSheetsExporter(use_oauth=True)
        client   = exporter.client

        sheet_url = analysis.get("sheet_url")
        spreadsheet = None

        if sheet_url:
            try:
                spreadsheet_id = sheet_url.split("/d/")[1].split("/")[0]
                spreadsheet = client.open_by_key(spreadsheet_id)
            except Exception:
                spreadsheet = None

        if not spreadsheet:
            title = f"PDKI_Analysis_{analysis['google_patent_id']}"
            spreadsheet = client.create(title)
            spreadsheet.share("", perm_type="anyone", role="reader")
            sheet_url = spreadsheet.url
            analysis_db.update_analysis_sheet_url(analysis_id, sheet_url)
            print(f"[sync_sheet] Created new sheet: {sheet_url}")

        # ── Tab 1: Summary ───────────────────────────────────────────────────
        try:
            summary_ws = spreadsheet.worksheet("Summary")
            summary_ws.clear()
        except Exception:
            summary_ws = spreadsheet.sheet1
            summary_ws.update_title("Summary")

        summary_data = [
            ["PDKI Patent Analysis", ""],
            ["", ""],
            ["Google Patent ID", analysis["google_patent_id"]],
            ["Title",     patent_data.get("title", "—")],
            ["Inventors", ", ".join(patent_data.get("inventors") or [])],
            ["Assignees", ", ".join(patent_data.get("assignees") or [])],
            ["", ""],
            ["Statistics", ""],
            ["Total Results",  stats["total"]],
            ["Analyzed",       stats["analyzed"]],
            ["Unanalyzed",     stats["unanalyzed"]],
            ["Relevant",       stats["relevant"]],
            ["Not Relevant",   stats["not_relevant"]],
            ["Uncertain",      stats["uncertain"]],
            ["", ""],
            ["Generated", _dt.now().strftime("%Y-%m-%d %H:%M")],
        ]
        summary_ws.update("A1", summary_data)
        summary_ws.format("A1:B1", {"textFormat": {"bold": True, "fontSize": 14}})
        summary_ws.format("A8:B8", {"textFormat": {"bold": True}})

        # ── Tab 2: PDKI Results ──────────────────────────────────────────────
        try:
            results_ws = spreadsheet.worksheet("PDKI Results")
            results_ws.clear()
        except Exception:
            results_ws = spreadsheet.add_worksheet("PDKI Results", rows=2000, cols=10)

        headers = ["#", "Title", "PDKI URL", "Status", "Found By", "Score", "Category", "Reasoning"]
        rows = [headers]
        for i, r in enumerate(results, 1):
            detail   = r.get("detail") or {}
            found_by = r.get("found_by") or []
            rows.append([
                i,
                detail.get("title") or r.get("text") or "",
                r.get("url", ""),
                detail.get("status") or "—",
                "; ".join(found_by) if isinstance(found_by, list) else str(found_by),
                r.get("score") if r.get("score") is not None else "",
                r.get("category") or "—",
                r.get("reasoning") or "",
            ])

        if len(rows) > 1:
            end_col = chr(ord("A") + len(headers) - 1)
            results_ws.update(f"A1:{end_col}{len(rows)}", rows)
            results_ws.format(
                f"A1:{end_col}1",
                {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.8, "green": 0.9, "blue": 1.0}},
            )

        print(f"[sync_sheet] Synced {len(results)} results for analysis {analysis_id}")

    except Exception as exc:
        print(f"[sync_sheet] Failed for {analysis_id}: {exc}")


async def run_categorization_job(
    analysis_id: str,
    job_id: str,
    result_ids: Optional[List[str]] = None,
):
    """
    Background task: categorise uncategorised PDKI results using Haiku.
    After all results processed, syncs Google Sheet.
    """
    loop = asyncio.get_event_loop()

    def _sync_run():
        print(f"[categorize_job] {job_id} _sync_run started")
        try:
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            if not api_key:
                categorization_jobs[job_id]["status"] = "failed"
                categorization_jobs[job_id]["error"]  = "ANTHROPIC_API_KEY not set"
                print(f"[categorize_job] {job_id} no API key")
                return

            analysis = analysis_db.get_analysis(analysis_id)
            if not analysis:
                categorization_jobs[job_id]["status"] = "failed"
                categorization_jobs[job_id]["error"]  = "Analysis not found"
                return

            patent_data = analysis.get("patent_data") or {}

            # Determine which results to process
            if result_ids:
                id_set = set(result_ids)
                all_results = analysis_db.get_results(analysis_id)
                to_process = [r for r in all_results if r["id"] in id_set and not r.get("category")]
            else:
                to_process = analysis_db.get_uncategorized_results(analysis_id)

            total = len(to_process)
            categorization_jobs[job_id]["total"] = total
            print(f"[categorize_job] {job_id} to_process={total}")

            if total == 0:
                categorization_jobs[job_id]["status"] = "completed"
                return

            categorize_fn = _get_categorize_result()

            for i, result in enumerate(to_process):
                print(f"[categorize_job] {job_id} processing {i+1}/{total}: {result['id'][:8]}")
                try:
                    assessed = categorize_fn(patent_data, result, api_key)
                    analysis_db.update_result_category(
                        result["id"],
                        assessed["category"],
                        assessed["reasoning"],
                        assessed["score"],
                    )
                    print(f"[categorize_job] → {assessed['category']} (score={assessed['score']})")

                except Exception as exc:
                    print(f"[categorize_job] result {result['id'][:8]} failed: {exc}")
                    analysis_db.update_result_category(result["id"], "uncertain", f"Categorization error: {exc}")

                categorization_jobs[job_id]["done"] = i + 1

            # Sync sheet once after all results
            _sync_google_sheet(analysis_id)
            categorization_jobs[job_id]["status"] = "completed"
            print(f"[categorize_job] {job_id} completed")

        except Exception as exc:
            import traceback
            print(f"[categorize_job] {job_id} EXCEPTION: {exc}")
            traceback.print_exc()
            categorization_jobs[job_id]["status"] = "failed"
            categorization_jobs[job_id]["error"]  = str(exc)

    await loop.run_in_executor(None, _sync_run)


# ─────────────────────────────────────────────────────────────────────────────
# Patent Analysis — Routes
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/v1/analysis")
async def create_analysis(request: CreateAnalysisRequest, background_tasks: BackgroundTasks):
    """Create a new analysis and start background extraction."""
    if not request.google_patent_id.strip():
        raise HTTPException(status_code=400, detail="google_patent_id is required")

    analysis_id = analysis_db.create_analysis(request.google_patent_id.strip())
    background_tasks.add_task(run_extraction_job, analysis_id, request.google_patent_id.strip())

    return {
        "analysis_id": analysis_id,
        "google_patent_id": request.google_patent_id.strip(),
        "status": "extracting",
        "message": "Extraction started in background",
    }


@app.get("/api/v1/analysis")
async def list_analyses():
    """List all patent analyses."""
    analyses = analysis_db.list_analyses()
    return {"analyses": analyses, "count": len(analyses)}


@app.get("/api/v1/analysis/{analysis_id}")
async def get_analysis(analysis_id: str):
    """Get a single analysis by ID."""
    analysis = analysis_db.get_analysis(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis


@app.patch("/api/v1/analysis/{analysis_id}/search-plan")
async def update_search_plan(analysis_id: str, request: UpdateSearchPlanRequest):
    """Update the search plan for an analysis."""
    analysis = analysis_db.get_analysis(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    analysis_db.update_search_plan(analysis_id, request.search_plan)
    return {"success": True, "search_plan": request.search_plan}


@app.post("/api/v1/analysis/{analysis_id}/batches")
async def create_batch(
    analysis_id: str,
    request: CreateBatchRequest,
    background_tasks: BackgroundTasks,
):
    """Create a search batch and start the PDKI run in background."""
    analysis = analysis_db.get_analysis(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    if not request.searches:
        raise HTTPException(status_code=400, detail="searches must not be empty")

    batch_config = {
        "searches":   request.searches,
        "pagination": request.pagination,
    }
    batch_id = analysis_db.create_batch(analysis_id, batch_config)

    background_tasks.add_task(
        run_batch_job,
        analysis_id,
        batch_id,
        request.searches,
        request.pagination,
    )

    return {
        "batch_id": batch_id,
        "analysis_id": analysis_id,
        "status": "pending",
        "message": "Batch job started in background",
    }


@app.get("/api/v1/analysis/{analysis_id}/batches")
async def list_batches(analysis_id: str):
    """List all batches for an analysis."""
    analysis = analysis_db.get_analysis(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    batches = analysis_db.list_batches(analysis_id)
    return {"batches": batches, "count": len(batches)}


@app.get("/api/v1/analysis/{analysis_id}/batches/{batch_id}")
async def get_batch(analysis_id: str, batch_id: str):
    """Get a single batch — used for polling."""
    batch = analysis_db.get_batch(batch_id)
    if not batch or batch.get("analysis_id") != analysis_id:
        raise HTTPException(status_code=404, detail="Batch not found")
    return batch


@app.get("/api/v1/analysis/{analysis_id}/results")
async def get_results(analysis_id: str):
    """Get all PDKI results for an analysis."""
    analysis = analysis_db.get_analysis(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    results = analysis_db.get_results(analysis_id)
    return {"results": results, "count": len(results)}


@app.delete("/api/v1/analysis/{analysis_id}")
async def delete_analysis(analysis_id: str):
    """Delete an analysis and all its batches and results."""
    analysis = analysis_db.get_analysis(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    if analysis_db.has_running_batch(analysis_id):
        raise HTTPException(
            status_code=409,
            detail="Cannot delete: a batch is currently running. Wait for it to finish first."
        )

    analysis_db.delete_analysis(analysis_id)
    return {"success": True, "message": f"Analysis {analysis_id} deleted"}


@app.get("/api/v1/analysis/{analysis_id}/stats")
async def get_stats(analysis_id: str):
    """Get result stats for an analysis."""
    analysis = analysis_db.get_analysis(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis_db.get_stats(analysis_id)


@app.post("/api/v1/analysis/{analysis_id}/categorize")
async def start_categorize(
    analysis_id: str,
    request: CategorizeRequest,
    background_tasks: BackgroundTasks,
):
    """Start AI categorisation job for uncategorised results (or a specific subset)."""
    analysis = analysis_db.get_analysis(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # Check how many will be processed
    if request.result_ids:
        id_set = set(request.result_ids)
        all_results = analysis_db.get_results(analysis_id)
        count = sum(1 for r in all_results if r["id"] in id_set and not r.get("category"))
    else:
        count = len(analysis_db.get_uncategorized_results(analysis_id))

    if count == 0:
        raise HTTPException(status_code=400, detail="No uncategorised results to process")

    job_id = str(uuid.uuid4())
    categorization_jobs[job_id] = {
        "job_id":      job_id,
        "analysis_id": analysis_id,
        "status":      "running",
        "total":       count,
        "done":        0,
        "error":       None,
    }

    background_tasks.add_task(
        run_categorization_job,
        analysis_id,
        job_id,
        request.result_ids,
    )

    return {"job_id": job_id, "total": count, "status": "running"}


@app.get("/api/v1/analysis/{analysis_id}/categorize/status")
async def get_categorize_status(analysis_id: str, job_id: str):
    """Poll the status of a categorisation job."""
    job = categorization_jobs.get(job_id)
    if not job or job.get("analysis_id") != analysis_id:
        raise HTTPException(status_code=404, detail="Categorisation job not found")
    return job


@app.patch("/api/v1/analysis/{analysis_id}/results/{result_id}/category")
async def update_result_category(
    analysis_id: str,
    result_id: str,
    request: UpdateCategoryRequest,
    background_tasks: BackgroundTasks,
):
    """User override: update a result's category and sync the Google Sheet."""
    valid = {"relevant", "not_relevant", "uncertain"}
    if request.category not in valid:
        raise HTTPException(status_code=400, detail=f"category must be one of {valid}")

    analysis = analysis_db.get_analysis(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    analysis_db.update_result_category(result_id, request.category)

    # Sync sheet in background if it already exists
    if analysis.get("sheet_url"):
        background_tasks.add_task(_sync_google_sheet, analysis_id)

    return {"success": True, "result_id": result_id, "category": request.category}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)