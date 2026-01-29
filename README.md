# AI Patent Pipeline - Web Interface Edition

## Project Overview

A comprehensive AI-powered patent extraction pipeline with modern web interface for researching pharmaceutical and biotechnology patents. The system fetches patents from PubChem or DrugBank, extracts detailed metadata, processes patent families, scrapes Google Patents for comprehensive content, and exports results to both JSON and Google Sheets.

## Current Status: PRODUCTION READY

- Complete end-to-end pipeline
- Modern web interface with real-time progress tracking
- Multiple data sources: PubChem (keyword search) and DrugBank (ID-based)
- Google Sheets integration (OAuth)
- Search history with auto-cleanup (SQLite)
- Multi-word keyword search support
- Configurable search parameters
- Docker containerized

---

## Quick Start

### Option 1: Web Interface (Recommended)

```bash
# Start the web server
python start_web_interface.py

# Open browser
http://localhost:8000
```

### Option 2: Command Line

**PubChem Search:**
```bash
# Basic usage
python main_patent_pipeline.py golimumab

# Advanced usage
python main_patent_pipeline.py golimumab --max-families 3 --countries US EP JP
```

**DrugBank Search:**
```bash
# Basic usage
python main_patent_pipeline.py --source drugbank --drugbank-id DB05541

# Advanced usage
python main_patent_pipeline.py --source drugbank --drugbank-id DB05541 --countries US EP
```

---

## Web Interface Features

### User-Friendly Patent Search

The web interface provides an intuitive way to search patents without command-line knowledge:

**Features:**
- Data Source Selection - Choose between PubChem (keyword) or DrugBank (ID)
- Keyword Search - Enter drug names, compounds, or technologies (supports multi-word queries)
- DrugBank ID Search - Enter DrugBank IDs (e.g., DB05541) for direct patent lookup
- Maximum Patents - Control result size (PubChem only, DrugBank returns fixed set)
- Patent Family Toggle - Optional family member search across countries (PubChem only)
- Multi-Country Selection - US, EP, JP, WIPO support
- Google Sheets Export - One-click shareable spreadsheets
- Search History - View all past searches with Google Sheets links
- **Delete Functionality** - Remove individual entries or clear all history
- Real-Time Progress - Live updates with phase tracking
- JSON Download - Raw data export for further analysis

### Real-Time Progress Tracking

Monitor your search with detailed phase information:

```
Phase 1: Retrieving patents from PubChem: 28/28 (100.0%) - WO-2024228135-A1
Phase 2: Retrieving Google Patents: 15/28 (53.6%) - EP-3222634-A1
```

### Results Display

Clean, focused results view:
- Source indicator (PubChem or DrugBank)
- Search term display
- Total Patents Found: Simple count display
- Download JSON: Raw data file
- View Google Sheets: Opens spreadsheet in new tab
- Copy Link: One-click copy of Google Sheets URL

### Search History Management

**History Display:**
- Shows source prefix (PubChem/DrugBank) with search term
- Extracts and displays drug names for DrugBank entries
- Links to Google Sheets exports
- Timestamp for each search

**Delete Operations:**
- Individual delete button per entry
- Clear All History button with confirmation dialog
- Deletes database entries, JSON files, and Google Sheets (best effort)
- Continues on errors with detailed logging

---

## Pipeline Architecture

### Complete Processing Flow:

```
1. Data Source Selection (PubChem or DrugBank)
   |
   +-- PubChem Branch:
   |   - Keyword Search
   |   - Extract Main Patent Metadata (JSON API)
   |   - Process Patent Families (Optional, Multi-Country)
   |
   +-- DrugBank Branch:
       - DrugBank ID Lookup (Selenium Stealth Mode)
       - Extract Patents from DrugBank Page
       - Bypass Cloudflare Protection
   |
   v
2. Enrich with PubChem Metadata
   |
   v
3. Scrape Google Patents (Selenium)
   |
   v
4. Deduplicate & Consolidate
   |
   v
5. Output: JSON + Google Sheets
```

### Data Sources:

| Source | Data Extracted | Method |
|--------|----------------|--------|
| **PubChem** | Patent IDs, titles, basic metadata, family info | JSON API |
| **DrugBank** | Patent IDs, approval dates, expiration dates, pediatric extension info | Selenium Web Scraping (Stealth Mode) |
| **Google Patents** | Abstracts, inventors, assignees, claims | Selenium Web Scraping |
| **Output** | Consolidated JSON + Google Sheets | File + OAuth API |

---

## Core Components

### 1. Web Interface (`web_interface/`)

**Backend** (`backend/web_api.py`):
- FastAPI REST API
- Async job management
- Real-time progress callbacks
- Background task processing
- Support for both PubChem and DrugBank sources

**Frontend** (`frontend/index.html`):
- Single-page application
- Real-time polling for progress
- Source selection (PubChem/DrugBank)
- Dynamic form fields based on source
- Responsive design
- No framework dependencies

**Endpoints:**
- `POST /api/v1/pipeline/start` - Start new analysis (accepts source parameter)
- `GET /api/v1/pipeline/{job_id}` - Get job status
- `GET /api/v1/pipeline/{job_id}/download` - Download JSON
- `GET /api/v1/history` - Get search history
- `DELETE /api/v1/history/{history_id}` - Delete individual history entry
- `DELETE /api/v1/history/clear` - Clear all history
- `GET /api/v1/jobs` - List all jobs (debug)

### 2. Main Pipeline (`main_patent_pipeline.py`)

**Features:**
- Complete orchestration of all stages
- Support for multiple data sources (PubChem, DrugBank)
- Configurable limits and countries
- Real-time progress reporting via callbacks
- Comprehensive logging
- Automatic deduplication
- Google Sheets integration

**Key Parameters:**
- `source` - Data source: "pubchem" or "drugbank" (default: "pubchem")
- `keyword` - Search term for PubChem (required when source=pubchem)
- `drugbank_id` - DrugBank ID for DrugBank search (required when source=drugbank)
- `max_main_patents` - Limit main results (default: unlimited, only applies to PubChem)
- `max_families` - Family patents per country (default: 3, 0 = disabled)
- `target_countries` - Country codes (default: ['US'])
- `export_to_sheets` - Enable Google Sheets export (default: False)

### 3. PubChem Fetcher (`pubchem_fetcher/`)

Fetches patents from PubChem by keyword search.

**Features:**
- Multi-word search support (auto-splits into AND conditions)
- Example: "lansoprazole inject" searches for patents with both terms
- Filters stop words to match PubChem behavior

**Output:** JSON file with patent IDs and basic info

### 4. DrugBank Fetcher (`drugbank_extract/`)

Fetches patents from DrugBank using DrugBank IDs.

**Features:**
- Direct drug page access using DrugBank IDs (e.g., DB05541)
- Selenium stealth mode to bypass Cloudflare protection
- Extracts patents from HTML table (id="patents")
- Optional screenshot functionality (--screenshot flag)

**Extracted Fields:**
- `patent_id` - Patent number (e.g., US6911461)
- `google_patent_url` - Link to Google Patents
- `pediatric_extension` - Yes/No indicator
- `approved_date` - Patent approval date
- `expires_date` - Patent expiration date
- `country` - Country/region code
- `drugbank_url` - URL to drug page

**Output:** Structured JSON compatible with pipeline format

**Technical Details:**
- Uses Chrome with stealth configuration to avoid bot detection
- Bypasses Cloudflare automatic JS challenge (not interactive challenges)
- Direct drug page access works; search functionality is not implemented due to Cloudflare interactive challenges

### 5. PubChem Extractor (`pubchem_extract/`)

Extracts comprehensive metadata using PubChem JSON API.

**Extracted Fields:**
- `patent_id`, `title`, `abstract_pubchem`
- `inventors_pubchem`, `assignee_pubchem`
- `priority_date`, `filing_date`, `publication_date`
- `patent_family_pubchem` (array of related patents)
- `country`

### 6. Google Patents Extractor (`googlepatent_extract/`)

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

### 7. Google Sheets Integration (`google_sheets_integration/`)

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

### 8. Search History Database (`utils/search_history_db.py`)

**Storage:** SQLite database (built-in, no extra dependencies)

**Features:**
- Auto-saves searches with keyword, source, display name, Google Sheets URL
- Stores spreadsheet_id and output_file for deletion operations
- Auto-cleanup: Removes entries older than 3 months on startup
- Public history: All users see all searches
- Database location: `utils/search_history.db`

**Methods:**
- `add_search()` - Save new search to history
- `get_history()` - Retrieve recent searches
- `delete_search()` - Delete individual entry
- `clear_all_history()` - Delete all entries
- `cleanup_old_entries()` - Delete entries older than N months

---

## Output Format

### JSON Structure:

```json
{
  "pipeline_info": {
    "source": "drugbank",
    "keyword": null,
    "drugbank_id": "DB05541",
    "execution_time": "2026-01-27 14:30:00",
    "total_patents": 4,
    "countries": ["US"],
    "max_families_per_country": 3,
    "main_patents": 4,
    "family_patents": 0,
    "duplicates_removed": 0
  },
  "patents": [
    {
      "patent_id": "US6911461",
      "title": "Patent Title Here",
      "extraction_from": "DrugBank ID: DB05541",

      // DrugBank Data
      "drugbank_url": "https://go.drugbank.com/drugs/DB05541",
      "approved_date_drugbank": "2005-06-28",
      "expires_date_drugbank": "2021-02-21",
      "pediatric_extension": "No",

      // PubChem Data
      "abstract_pubchem": "Abstract from PubChem...",
      "inventors_pubchem": ["Inventor 1", "Inventor 2"],
      "assignee_pubchem": "Company Name",
      "priority_date_pubchem": "2004-02-21",
      "filing_date_pubchem": "2004-02-21",
      "publication_date_pubchem": "2005-06-28",
      "patent_family_pubchem": ["US-patent-1", "EP-patent-2"],
      "country": "US",

      // Google Patents Data
      "abstract_google": "Detailed abstract from Google...",
      "inventors_google": ["Full Name 1", "Full Name 2"],
      "assignees_google": ["Current Assignee Company"],
      "claims": [
        "1. A method comprising...",
        "2. The method of claim 1..."
      ],

      // URLs
      "google_patent": "https://patents.google.com/patent/US6911461",
      "pubchem_patent": "https://pubchem.ncbi.nlm.nih.gov/patent/US-6911461"
    }
  ]
}
```

---

## Google Sheets Setup

### Option 1: OAuth (Personal Account) - Current

**Advantages:**
- Uses your personal Google Drive storage (30GB+ with Workspace)
- Simple setup
- Token auto-refreshes indefinitely (Production mode)

**Setup Steps:**

1. **Create OAuth Credentials:**
   - Go to: https://console.cloud.google.com/apis/credentials
   - Create OAuth 2.0 Client ID (Desktop App)
   - Download JSON and save as `oauth_client_secret.json`

2. **Publish App to Production:**
   - Go to: https://console.cloud.google.com/apis/credentials/consent
   - Click "PUBLISH APP" (no verification needed for personal use)

3. **Generate OAuth Token (Local Machine):**
   ```bash
   cd google_sheets_integration/local_setup
   python3 generate_oauth_token.py
   # Browser opens, login, approve
   # Token saved to oauth_token.json
   ```

4. **Copy Token to Container:**
   ```bash
   docker cp oauth_token.json patent-pipeline:/app/patent_pipeline/google_sheets_integration/
   ```

**Files Needed:**
- `oauth_client_secret.json` (from Google Cloud Console)
- `oauth_token.json` (generated locally, then copied)

See: `google_sheets_integration/local_setup/README.md`

### Option 2: Service Account (Alternative)

Use for headless servers without browser access.

**Setup:**
- Download service account JSON from Google Cloud Console
- Save as `google_credentials.json`
- Set `use_oauth=False` in pipeline

---

## Technical Specifications

### Environment:
- **Platform:** Linux (Docker container)
- **Python:** 3.11
- **Working Directory:** `/app/patent_pipeline`
- **Web Server:** FastAPI + Uvicorn
- **Web Scraping:** Selenium + Chrome WebDriver

### Dependencies:

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

### System Requirements:

| Component | Requirement |
|-----------|-------------|
| CPU | 2+ vCPU (concurrent users) |
| RAM | 4-8GB (Selenium Chrome instances) |
| Disk | 10GB+ (output files, logs) |
| Network | Stable internet for API calls |

**Concurrent Users:**
- 1-2 users: Smooth
- 3-4 users: May slow down
- 5+ users: Consider job queue

---

## File Structure

```
/app/patent_pipeline/
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
├── drugbank_extract/
│   ├── drugbank_patent_fetcher.py      # DrugBank fetcher (main)
│   ├── test_stealth_access.py          # Cloudflare test
│   └── test_drug_page_access.py        # Drug page test
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
│   ├── oauth_token.json          # GITIGNORED - Your token
│   ├── oauth_client_secret.json  # GITIGNORED - Your client
│   └── google_credentials.json   # GITIGNORED - Service account
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

## Security & Privacy

### Sensitive Files (Not in Git):

Protected by `.gitignore`:
- `oauth_token.json` - Your OAuth refresh token
- `oauth_client_secret.json` - OAuth client credentials
- `google_credentials.json` - Service account key
- `output/` - All output files and logs
- `utils/search_history.db` - Search history database (optional)

### Example Files (Safe to Commit):

Provided as templates:
- `oauth_token.json.example`
- `oauth_client_secret.json.example`
- `google_credentials.json.example`

### Before Pushing to GitHub:

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

## Usage Examples

### Example 1: Quick PubChem Search (Web Interface)

```
Source: PubChem (by Keyword)
Keyword: golimumab
Max Main Patents: 10
Include Families: unchecked
Export to Sheets: checked

Result:
- 10 patents found
- ~2 minutes processing
- JSON + Google Sheets links provided
```

### Example 2: DrugBank Search (Web Interface)

```
Source: DrugBank (by ID)
DrugBank ID: DB05541
Export to Sheets: checked

Result:
- 4 patents found (Brivaracetam)
- ~1 minute processing
- JSON + Google Sheets links provided
```

### Example 3: Comprehensive PubChem Analysis (Web Interface)

```
Source: PubChem (by Keyword)
Keyword: insulin
Max Main Patents: 100
Include Families: checked
  Countries: US, EP, JP
  Max per country: 5
Export to Sheets: checked

Result:
- 100 main patents + ~50 family members
- ~30 minutes processing
- 150 total patents in output
```

### Example 4: Command Line DrugBank (Scripting)

```bash
# Automated DrugBank patent extraction
python main_patent_pipeline.py \
  --source drugbank \
  --drugbank-id DB05541 \
  --countries US \
  --export-sheets
```

---

## Troubleshooting

### Issue: Google Sheets Link Not Showing

**Check:**
1. OAuth token is valid: `cat google_sheets_integration/oauth_token.json | grep refresh_token`
2. App is in Production mode (not Testing)
3. Browser console shows: `Job sheets_url: https://docs.google.com/...`

**Solution:** Regenerate OAuth token if expired

### Issue: Progress Bar Stuck

**Check:**
1. Browser DevTools - Console for errors
2. Server logs for exceptions
3. Chrome driver is running: `ps aux | grep chrome`

**Solution:** Restart web server

### Issue: Selenium Errors

**Common:**
- "Chrome binary not found" - Install chromium in Docker
- "Session not created" - Update chromedriver version
- "Element not found" - Site changed structure (update selectors)

### Issue: DrugBank Cloudflare Block

**Symptoms:**
- "Just a moment..." message in logs
- No patents returned from DrugBank

**Solutions:**
1. Verify stealth mode is enabled
2. Check if accessing drug page directly (not search page)
3. Increase wait time in fetcher
4. DrugBank search is intentionally disabled (use direct IDs only)

---

## Future Enhancements

### Planned Features:

- Job queue for concurrent users
- User authentication system
- Email notifications on completion
- Advanced filtering (date ranges, assignees)
- Patent PDF download integration
- Batch processing for multiple keywords
- API rate limiting and retry logic
- WebSocket for real-time progress (replace polling)
- Dark mode for web interface
- Frontend UI improvement: Hide irrelevant options for DrugBank source
- Additional data sources (EPO, USPTO direct APIs)

---

## License

This project is for educational and research purposes.

**Important:**
- Respect PubChem, DrugBank, and Google Patents Terms of Service
- Implement rate limiting for production use
- Patents data is publicly available but may have usage restrictions
- Google Sheets API has quota limits (check Google Cloud Console)
- DrugBank stealth mode is for legitimate research purposes only

---

## Contributing

When contributing to this repository:

1. **Never commit credentials:**
   - Check `.gitignore` is working
   - Use example files for templates

2. **Test thoroughly:**
   - Web interface functionality
   - Both PubChem and DrugBank sources
   - Both OAuth and Service Account modes
   - Error handling for API failures

3. **Document changes:**
   - Update README.md
   - Add comments for complex logic
   - Include example usage

---

## Support

**Issues:**
- Check logs: `/app/patent_pipeline/output/pipeline_logs/`
- Enable debug mode in pipeline
- Review web server console output

**Resources:**
- PubChem API: https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest
- DrugBank: https://go.drugbank.com
- Google Sheets API: https://developers.google.com/sheets/api
- Selenium Docs: https://www.selenium.dev/documentation/

---

## Acknowledgments

Built with:
- **PubChem** - Patent data source
- **DrugBank** - Drug and patent information
- **Google Patents** - Comprehensive patent information
- **FastAPI** - Modern web framework
- **Selenium** - Web automation
- **Google Sheets API** - Data export and sharing

---

**Version:** 2.2.0 (Multi-Source Edition with History Management)
**Last Updated:** January 2026
**Status:** Production Ready
