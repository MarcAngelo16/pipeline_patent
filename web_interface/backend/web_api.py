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
    keyword: str
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

def create_job(job_id: str, keyword: str, countries: List[str], max_families: int,
               max_main_patents: Optional[int] = None) -> Dict:
    """Create a new job entry"""
    return {
        "job_id": job_id,
        "status": "queued",
        "progress": 0,
        "current_stage": "Initializing...",
        "keyword": keyword,
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

async def run_pipeline_job(job_id: str, keyword: str, countries: List[str],
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
        results = {
            "total_patents": len(pipeline.all_patents),
            "duplicates_removed": pipeline.duplicates_removed,
            "countries": countries,
            "keyword": keyword
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
            history_db.add_search(
                keyword=keyword,
                google_sheets_url=sheets_url if sheets_url else None
            )
            print(f"✅ Saved search to history database: {keyword}")
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

    # Validate request
    if not request.keyword.strip():
        raise HTTPException(status_code=400, detail="Keyword is required")

    if not request.countries:
        request.countries = ["US"]

    # Generate job ID
    job_id = str(uuid.uuid4())

    # Create job entry
    jobs[job_id] = create_job(job_id, request.keyword, request.countries,
                              request.max_families, request.max_main_patents)

    # Start background task
    background_tasks.add_task(
        run_pipeline_job,
        job_id,
        request.keyword,
        request.countries,
        request.max_families,
        request.max_main_patents,
        request.export_sheets
    )

    return PipelineResponse(
        job_id=job_id,
        status="queued",
        message=f"Pipeline started for keyword: {request.keyword}"
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

    return FileResponse(
        output_file,
        media_type='application/json',
        filename=f"{job['keyword']}_patents.json"
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

# Serve static files (CSS, JS, images)
static_path = current_dir / "web_interface" / "frontend" / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)