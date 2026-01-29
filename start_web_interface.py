#!/usr/bin/env python3
"""
Start script for the AI Patent Pipeline Web Interface
Simple launcher for development and production
"""

import os
import sys
import uvicorn
from pathlib import Path

# Add current directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

def main():
    """Start the web interface"""
    print("🚀 Starting AI Patent Pipeline Web Interface")
    print(f"📁 Working directory: {current_dir}")
    print("🌐 Web interface will be available at: http://localhost:8000")
    print("📋 API documentation at: http://localhost:8000/docs")
    print()

    # Import and start the web API
    from web_interface.backend.web_api import app

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=False,  # Set to True for development
        access_log=True
    )

if __name__ == "__main__":
    main()