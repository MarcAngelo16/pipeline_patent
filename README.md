# AI Patent Pipeline - Web Interface Edition

## 🎯 Project Overview

A comprehensive AI-powered patent extraction pipeline with modern web interface for researching pharmaceutical and biotechnology patents. The system fetches patents from PubChem, extracts detailed metadata, processes patent families, scrapes Google Patents for comprehensive content, and exports results to both JSON and Google Sheets.

## ✨ Current Status: **PRODUCTION READY**

✅ Complete end-to-end pipeline
✅ Modern web interface with real-time progress tracking
✅ Google Sheets integration (OAuth)
✅ Search history with auto-cleanup (SQLite)
✅ Multi-word keyword search support
✅ Configurable search parameters
✅ Docker containerized

---

## 🚀 Quick Start

### **Option 1: Web Interface (Recommended)**

```bash
# Start the web server
python start_web_interface.py

# Open browser
http://localhost:8000
```

### **Option 2: Command Line**

```bash
# Basic usage
python main_patent_pipeline.py golimumab

# Advanced usage
python main_patent_pipeline.py golimumab --max-main-patents 50 --max-families 3 --countries US EP JP
```

---

## 🌐 Web Interface Features

### **User-Friendly Patent Search**

The web interface provides an intuitive way to search patents without command-line knowledge:

**Features:**
- 🔍 **Keyword Search** - Enter drug names, compounds, or technologies (supports multi-word queries)
- 🔢 **Main Patent Limit** - Control result size (default: 50, or unlimited)
- 👨‍👩‍👧‍👦 **Patent Family Toggle** - Optional family member search across countries
- 🌍 **Multi-Country Selection** - US, EP, JP, WIPO support
- 📊 **Google Sheets Export** - One-click shareable spreadsheets
- 📜 **Search History** - View all past searches with Google Sheets links
- 📈 **Real-Time Progress** - Live updates with phase tracking
- 📥 **JSON Download** - Raw data export for further analysis

**Screenshot:**
```
┌─────────────────────────────────────────┐
│ 🔬 AI Patent Pipeline                   │
├─────────────────────────────────────────┤
│ Research Keyword: [golimumab        ]   │
│                                         │
│ Maximum Main Patents: [50] ☐ Get all   │
│                                         │
│ ☐ Include Patent Families              │
│   (Hidden: Countries, Max per country)  │
│                                         │
│ ☑ Export to Google Sheets              │
│                                         │
│ [🚀 Start Patent Analysis]              │
└─────────────────────────────────────────┘
```

### **Real-Time Progress Tracking**

Monitor your search with detailed phase information:

```
Phase 1: Retrieving patents from PubChem: 28/28 (100.0%) - WO-2024228135-A1
Phase 2: Retrieving Google Patents: 15/28 (53.6%) - EP-3222634-A1
```

### **Results Display**

Clean, focused results view:
- **Total Patents Found**: Simple count display
- **Download JSON**: Raw data file
- **View Google Sheets**: Opens spreadsheet in new tab
- **Copy Link**: One-click copy of Google Sheets URL

---

## 📋 Pipeline Architecture

### **Complete Processing Flow:**

```
1. PubChem Keyword Search
   ↓
2. Extract Main Patent Metadata (JSON API)
   ↓
3. Process Patent Families (Optional, Multi-Country)
   ↓
4. Scrape Google Patents (Selenium)
   ↓
5. Deduplicate & Consolidate
   ↓
6. Output: JSON + Google Sheets
```

### **Data Sources:**

| Source | Data Extracted | Method |
|--------|----------------|--------|
| **PubChem** | Patent IDs, titles, basic metadata, family info | JSON API |
| **Google Patents** | Abstracts, inventors, assignees, claims | Selenium Web Scraping |
| **Output** | Consolidated JSON + Google Sheets | File + OAuth API |

---

## 🔧 Core Components

### **1. Web Interface** (`web_interface/`)

**Backend** (`backend/web_api.py`):
- FastAPI REST API
- Async job management
- Real-time progress callbacks
- Background task processing

**Frontend** (`frontend/index.html`):
- Single-page application
- Real-time polling for progress
- Responsive design
- No framework dependencies

**Endpoints:**
- `POST /api/v1/pipeline/start` - Start new analysis
- `GET /api/v1/pipeline/{job_id}` - Get job status
- `GET /api/v1/pipeline/{job_id}/download` - Download JSON
- `GET /api/v1/history` - Get search history
- `GET /api/v1/jobs` - List all jobs (debug)

### **2. Main Pipeline** (`main_patent_pipeline.py`)

**Features:**
- Complete orchestration of all stages
- Configurable limits and countries
- Real-time progress reporting via callbacks
- Comprehensive logging
- Automatic deduplication
- Google Sheets integration

**Key Parameters:**
- `keyword` - Search term (required)
- `max_main_patents` - Limit main results (default: unlimited)
- `max_families` - Family patents per country (default: 3, 0 = disabled)
- `target_countries` - Country codes (default: ['US'])
- `export_to_sheets` - Enable Google Sheets export (default: False)

### **3. PubChem Fetcher** (`pubchem_fetcher/`)

Fetches patents from PubChem by keyword search.

**Features:**
- Multi-word search support (auto-splits into AND conditions)
- Example: "lansoprazole inject" → searches for patents with both terms
- Filters stop words to match PubChem behavior

**Output:** JSON file with patent IDs and basic info

### **4. PubChem Extractor** (`pubchem_extract/`)

Extracts comprehensive metadata using PubChem JSON API.

**Extracted Fields:**
- `patent_id`, `title`, `abstract_pubchem`
- `inventors_pubchem`, `assignee_pubchem`
- `priority_date`, `filing_date`, `publication_date`
- `patent_family_pubchem` (array of related patents)
- `country`

### **5. Google Patents Extractor** (`googlepatent_extract/`)

Selenium-based web scraper for detailed content.

**Extracted Fields:**
- `abstract_google` - Full patent abstract
- `inventors_google` - Complete inventor list
- `assignees_google` - Current assignees
- `claims` - Numbered patent claims (legal definitions)

**Anti-Detection:**
- Chrome driver with stealth configuration
- User-agent rotation
- Structure-based selectors (no hardcoded patterns)

### **6. Google Sheets Integration** (`google_sheets_integration/`)

**Authentication:** OAuth 2.0 (Personal Google Account)

**Features:**
- Automatic sheet creation
- Two-tab layout: Summary + Patent Details
- Professional formatting
- Auto-share capabilities
- Works with Google Workspace (30GB+ storage)

**Tabs Created:**
1. **Pipeline_Summary** - Execution stats, counts, configuration
2. **Patent_Details** - Full patent data in table format

### **7. Search History Database** (`utils/search_history_db.py`)

**Storage:** SQLite database (built-in, no extra dependencies)

**Features:**
- Auto-saves every successful search with keyword + Google Sheets URL
- Auto-cleanup: Removes entries older than 3 months on startup
- Public history: All users see all searches
- Database location: `utils/search_history.db`

**Methods:**
- `add_search()` - Save new search to history
- `get_history()` - Retrieve recent searches
- `cleanup_old_entries()` - Delete entries older than N months

---

## 📊 Output Format

### **JSON Structure:**

```json
{
  "pipeline_info": {
    "keyword": "golimumab",
    "execution_time": "2025-11-02 13:55:02",
    "total_patents": 28,
    "countries": ["US"],
    "max_families_per_country": 3,
    "max_main_patents": 50,
    "main_patents": 28,
    "family_patents": 0,
    "duplicates_removed": 0
  },
  "patents": [
    {
      "patent_id": "WO-2024184281-A1",
      "title": "Patent Title Here",
      "extraction_from": "Pubchem keyword: golimumab",

      // PubChem Data
      "abstract_pubchem": "Abstract from PubChem...",
      "inventors_pubchem": ["Inventor 1", "Inventor 2"],
      "assignee_pubchem": "Company Name",
      "priority_date_pubchem": "2023-03-02",
      "filing_date_pubchem": "2024-03-01",
      "publication_date_pubchem": "2024-09-12",
      "patent_family_pubchem": ["US-patent-1", "EP-patent-2"],
      "country": "WO",

      // Google Patents Data
      "abstract_google": "Detailed abstract from Google...",
      "inventors_google": ["Full Name 1", "Full Name 2"],
      "assignees_google": ["Current Assignee Company"],
      "claims": [
        "1. A method comprising...",
        "2. The method of claim 1..."
      ],

      // URLs
      "google_patent": "https://patents.google.com/patent/WO2024184281A1/en",
      "pubchem_patent": "https://pubchem.ncbi.nlm.nih.gov/patent/WO-2024184281-A1"
    }
  ]
}
```

---

## 🔐 Google Sheets Setup

### **Option 1: OAuth (Personal Account) ✅ Current**

**Advantages:**
- Uses your personal Google Drive storage (30GB+ with Workspace)
- Simple setup
- Token auto-refreshes indefinitely (Production mode)

**Setup Steps:**

1. **Create OAuth Credentials:**
   - Go to: https://console.cloud.google.com/apis/credentials
   - Create OAuth 2.0 Client ID (Desktop App)
   - Download JSON → Save as `oauth_client_secret.json`

2. **Publish App to Production:**
   - Go to: https://console.cloud.google.com/apis/credentials/consent
   - Click "PUBLISH APP" (no verification needed for personal use)

3. **Generate OAuth Token (Local Machine):**
   ```bash
   cd google_sheets_integration/local_setup
   python3 generate_oauth_token.py
   # Browser opens → Login → Approve
   # Token saved to oauth_token.json
   ```

4. **Copy Token to Container:**
   ```bash
   docker cp oauth_token.json patent-pipeline:/app/AI_pipeline/google_sheets_integration/
   ```

**Files Needed:**
- `oauth_client_secret.json` (from Google Cloud Console)
- `oauth_token.json` (generated locally, then copied)

See: `google_sheets_integration/local_setup/README.md`

### **Option 2: Service Account (Alternative)**

Use for headless servers without browser access.

**Setup:**
- Download service account JSON from Google Cloud Console
- Save as `google_credentials.json`
- Set `use_oauth=False` in pipeline

---

## 🛠️ Technical Specifications

### **Environment:**
- **Platform:** Linux (Docker container)
- **Python:** 3.11
- **Working Directory:** `/app/AI_pipeline`
- **Web Server:** FastAPI + Uvicorn
- **Web Scraping:** Selenium + Chrome WebDriver

### **Dependencies:**

```
requests>=2.31.0
beautifulsoup4>=4.12.0
selenium>=4.15.0
gspread>=5.12.0
google-auth>=2.23.0
google-auth-oauthlib>=1.1.0
fastapi>=0.104.1
uvicorn>=0.24.0
pydantic>=2.12.3
```

**Note:** SQLite3 is included in Python's standard library (no additional installation needed)

### **System Requirements:**

| Component | Requirement |
|-----------|-------------|
| CPU | 2+ vCPU (concurrent users) |
| RAM | 4-8GB (Selenium Chrome instances) |
| Disk | 10GB+ (output files, logs) |
| Network | Stable internet for API calls |

**Concurrent Users:**
- 1-2 users: ✅ Smooth
- 3-4 users: ⚠️ May slow down
- 5+ users: ❌ Consider job queue

---

## 📁 File Structure

```
/app/AI_pipeline/
├── start_web_interface.py         # Web server launcher
├── main_patent_pipeline.py        # Main orchestrator
├── requirements.txt               # Python dependencies
├── Dockerfile                     # Container setup
├── docker-compose.yml             # Docker configuration
├── .gitignore                     # Git ignore rules
│
├── web_interface/
│   ├── backend/
│   │   └── web_api.py            # FastAPI REST API
│   └── frontend/
│       └── index.html            # Single-page app
│
├── pubchem_fetcher/
│   └── pubchem_patent_fetcher.py # PubChem API fetcher
│
├── pubchem_extract/
│   └── pubchem_json_extractor.py # Metadata extractor
│
├── googlepatent_extract/
│   └── google_patents_clean_extractor.py  # Selenium scraper
│
├── google_sheets_integration/
│   ├── google_sheets_exporter.py # Sheets export logic
│   ├── setup_credentials.py      # Credential helper
│   ├── local_setup/              # OAuth token generator
│   │   ├── generate_oauth_token.py
│   │   └── README.md
│   ├── oauth_token.json          # ⚠️ GITIGNORED - Your token
│   ├── oauth_client_secret.json  # ⚠️ GITIGNORED - Your client
│   └── google_credentials.json   # ⚠️ GITIGNORED - Service account
│
├── utils/
│   ├── pipeline_logger.py        # Logging system
│   ├── file_manager.py           # File operations
│   ├── patent_url_generator.py   # URL utilities
│   ├── search_history_db.py      # Search history database
│   └── search_history.db         # SQLite database (auto-created)
│
└── output/
    ├── {keyword}_patents.json    # Final output
    └── pipeline_logs/            # Execution logs
```

---

## 🔒 Security & Privacy

### **Sensitive Files (Not in Git):**

✅ Protected by `.gitignore`:
- `oauth_token.json` - Your OAuth refresh token
- `oauth_client_secret.json` - OAuth client credentials
- `google_credentials.json` - Service account key
- `output/` - All output files and logs
- `utils/search_history.db` - Search history database (optional)

### **Example Files (Safe to Commit):**

Provided as templates:
- `oauth_token.json.example`
- `oauth_client_secret.json.example`
- `google_credentials.json.example`

### **Before Pushing to GitHub:**

```bash
# 1. Verify .gitignore is working
git status
# Should NOT show *.json files in google_sheets_integration/

# 2. Check for accidentally committed secrets
git log --all --full-history -- "*oauth*" "*credentials*"

# 3. If secrets were committed, use git-filter-repo to remove
pip install git-filter-repo
git filter-repo --path google_sheets_integration/oauth_token.json --invert-paths
```

---

## 📈 Usage Examples

### **Example 1: Quick Search (Web Interface)**

```
Keyword: golimumab
Max Main Patents: 10
Include Families: ☐ (unchecked)
Export to Sheets: ☑ (checked)

Result:
- 10 patents found
- ~2 minutes processing
- JSON + Google Sheets links provided
```

### **Example 2: Comprehensive Analysis (Web Interface)**

```
Keyword: insulin
Max Main Patents: 100
Include Families: ☑ (checked)
  Countries: US, EP, JP
  Max per country: 5
Export to Sheets: ☑ (checked)

Result:
- 100 main patents + ~50 family members
- ~30 minutes processing
- 150 total patents in output
```

### **Example 3: Command Line (Scripting)**

```bash
# Automated nightly patent search
python main_patent_pipeline.py "monoclonal antibody" \
  --max-main-patents 50 \
  --max-families 0 \
  --countries US \
  --export-sheets
```

---

## 🐛 Troubleshooting

### **Issue: Google Sheets Link Not Showing**

**Check:**
1. OAuth token is valid: `cat google_sheets_integration/oauth_token.json | grep refresh_token`
2. App is in Production mode (not Testing)
3. Browser console shows: `Job sheets_url: https://docs.google.com/...`

**Solution:** Regenerate OAuth token if expired

### **Issue: Progress Bar Stuck**

**Check:**
1. Browser DevTools → Console for errors
2. Server logs for exceptions
3. Chrome driver is running: `ps aux | grep chrome`

**Solution:** Restart web server

### **Issue: Selenium Errors**

**Common:**
- "Chrome binary not found" → Install chromium in Docker
- "Session not created" → Update chromedriver version
- "Element not found" → Google Patents changed structure (update selectors)

---

## 🚀 Future Enhancements

### **Planned Features:**

- [ ] Job queue for concurrent users
- [ ] User authentication system
- [ ] Email notifications on completion
- [ ] Advanced filtering (date ranges, assignees)
- [ ] Patent PDF download integration
- [ ] Batch processing for multiple keywords
- [ ] API rate limiting and retry logic
- [ ] WebSocket for real-time progress (replace polling)
- [ ] Dark mode for web interface

---

## 📝 License

This project is for educational and research purposes.

**Important:**
- Respect PubChem and Google Patents Terms of Service
- Implement rate limiting for production use
- Patents data is publicly available but may have usage restrictions
- Google Sheets API has quota limits (check Google Cloud Console)

---

## 🤝 Contributing

When contributing to this repository:

1. **Never commit credentials:**
   - Check `.gitignore` is working
   - Use example files for templates

2. **Test thoroughly:**
   - Web interface functionality
   - Both OAuth and Service Account modes
   - Error handling for API failures

3. **Document changes:**
   - Update README.md
   - Add comments for complex logic
   - Include example usage

---

## 📞 Support

**Issues:**
- Check logs: `/app/AI_pipeline/output/pipeline_logs/`
- Enable debug mode in pipeline
- Review web server console output

**Resources:**
- PubChem API: https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest
- Google Sheets API: https://developers.google.com/sheets/api
- Selenium Docs: https://www.selenium.dev/documentation/

---

## 🎉 Acknowledgments

Built with:
- **PubChem** - Patent data source
- **Google Patents** - Comprehensive patent information
- **FastAPI** - Modern web framework
- **Selenium** - Web automation
- **Google Sheets API** - Data export and sharing

---

**Version:** 2.0.0 (Web Interface Edition)
**Last Updated:** November 2025
**Status:** Production Ready ✅
