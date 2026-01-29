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

# Import the existing pipeline
from main_patent_pipeline import PatentPipeline

# Import search history database
from utils.search_history_db import SearchHistoryDB

# Job storage (in production, use Redis or database)
jobs: Dict[str, Dict] = {}

# Initialize search history database
history_db = SearchHistoryDB()

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)