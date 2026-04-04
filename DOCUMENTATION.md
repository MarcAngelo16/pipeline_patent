# Patent Pipeline — Project Documentation

## Overview

A web-based patent research tool that searches the Indonesian patent database (PDKI) for patents related to a given drug/compound. The workflow: fetch source patent metadata → AI-generate search terms → run PDKI searches → extract patent details → AI-categorise results → export to Google Sheets.

---

## Directory Structure

### Root
| File | Purpose |
|------|---------|
| `start_web_interface.py` | Entry point — starts the FastAPI server on port 8000 |
| `main_patent_pipeline.py` | Standalone pipeline orchestrator (non-web mode) |
| `requirements.txt` | Python dependencies |
| `Dockerfile` / `docker-compose.yml` | Container setup |

---

### `PDKI/` — Indonesian Patent Search Engine
Core of the search system. Uses Selenium + undetected_chromedriver against `pdki-indonesia.dgip.go.id`.

| File | Purpose |
|------|---------|
| `PDKI_advanced.py` | **Main search driver.** Two-layer search: (1) main search bar, (2) optional 5-field advanced filter. Handles captcha detection (page < 20 000 chars + `id="main-iframe"`). Pauses indefinitely on captcha — no auto-resolve. Key functions: `load_search_page`, `fill_main_search`, `submit_main_search`, `fill_advanced_search`, `click_terapkan`, `extract_links`, `detect_captcha`. |
| `PDKI_detail_extractor.py` | Extracts structured data from a single patent detail page: title, status, inventors, assignees, abstract, priority numbers, filing date. Individual functions can be called directly on an already-loaded page (avoids double-navigation). |
| `PDKI_extrac_undetected.py` | Legacy extractor — older single-layer search approach. Largely superseded by `PDKI_advanced.py`. |
| `pdki_pipeline.py` | Orchestrates a full PDKI Phase 1 run: loads Chrome, runs all batch searches via `PDKI_advanced.py`, collects links. Called by the web API's batch job. |
| `pdki_categorizer.py` | AI relevance scoring. Given a source patent and a PDKI result, calls Claude API to return `category` (relevant / uncertain / not_relevant), `score`, and `reasoning`. |
| `pdki_config.py` | Shared constants (PDKI base URL, Chrome profile path, display settings). |
| `search_and_extract_links100.py` | Standalone script — search + extract with pagination set to 100. |
| `testing/` | Development/debug scripts: `test_captcha_observation.py` (manual captcha testing), `debug_captcha_page.py`, `test_parallel_chrome.py`. |

---

### `googlepatent_extract/` — Google Patents Metadata
| File | Purpose |
|------|---------|
| `google_patents_clean_extractor.py` | Selenium scraper for `patents.google.com`. Extracts title, abstract, inventors, assignees, claims, classifications from a Google Patent page. |
| `web_structure_analyzer.py` | Dev tool — analyses page DOM structure for selector discovery. |

---

### `pubchem_extract/` & `pubchem_fetcher/` — PubChem Data Source
| File | Purpose |
|------|---------|
| `pubchem_patent_fetcher.py` | Fetches patent list for a compound from PubChem API. |
| `pubchem_json_extractor.py` | Parses PubChem API response JSON. |
| `google_patents_url_generator.py` | Converts PubChem patent IDs to Google Patents URLs. |
| `pubchem_web_analyzer.py` | Dev tool — analyses PubChem page structure. |

---

### `drugbank_extract/` — DrugBank Data Source
| File | Purpose |
|------|---------|
| `drugbank_patent_fetcher.py` | Selenium scraper for DrugBank patent pages. Alternative to PubChem as a data source. |
| `test_*.py` | Dev scripts for access/stealth testing. |

---

### `google_sheets_integration/` — Export
| File | Purpose |
|------|---------|
| `google_sheets_exporter.py` | Writes categorised results to Google Sheets (OAuth). Creates/updates a spreadsheet with tabs: Summary, Results, Stats. **Only triggered by the AI categoriser — never by PDKI search directly.** |
| `setup_credentials.py` | One-time OAuth credential setup. |
| `local_setup/generate_oauth_token.py` | Generates `oauth_token.json` for local dev. |
| `*.json.example` | Credential file templates. |

---

### `utils/` — Shared Infrastructure
| File | Purpose |
|------|---------|
| `analysis_db.py` | SQLite ORM for the Patent Analysis feature. Tables: `patent_analyses`, `batch_searches`, `pdki_results`. Handles create/read/update for analyses, batches, results, and categorisation. |
| `search_history_db.py` | SQLite store for the legacy search history tab (non-analysis pipeline runs). Auto-cleans entries older than 3 months on startup. |
| `pipeline_logger.py` | Structured logging with timestamps and log-level filtering. |
| `file_manager.py` | Output file naming, directory creation, JSON save/load helpers. |
| `patent_url_generator.py` | Builds PDKI and Google Patents URLs from patent IDs. |

---

### `web_interface/` — Web Application
#### `backend/web_api.py`
Single FastAPI file serving the entire backend. Key areas:

| Area | Details |
|------|---------|
| **Legacy pipeline** (`/api/v1/pipeline/*`) | Original keyword→Google Patents→Sheets pipeline. Runs in background, polled by frontend. |
| **Patent Analysis** (`/api/v1/analysis/*`) | Full workflow: create analysis (Google Patent ID) → AI search plan → batch PDKI searches → results → categorise. |
| **Batch jobs** | Each batch acquires the `chrome_lock` semaphore before opening Chrome. All jobs queue globally — only one Chrome instance runs at a time. Live `current_stage` + `log_lines` exposed via polling. |
| **URL add** (`/api/v1/analysis/{id}/results/add`) | Manually add a single PDKI patent URL to an analysis. Deduplication check before starting. Same Chrome queue as batch jobs. |
| **Chrome queue** | `chrome_lock = asyncio.Semaphore(1)` + `chrome_queue` list. Ensures shared Chrome profile is only used by one job at a time across all users and analyses. |
| **VNC proxy** (`/api/vnc` WebSocket) | Pipes browser WebSocket directly to x11vnc TCP port 5900. Enables in-browser VNC for captcha solving. |
| **Static files** | Serves `frontend/index.html` at `/` and noVNC files at `/novnc/`. |

#### `frontend/index.html`
Single-page Vue 3 application (no build step — CDN). Two main sections:

| Section | Details |
|---------|---------|
| **Search History tab** | Legacy view of pipeline runs. Table of past searches with status, Google Sheets link, download. |
| **Patent Analysis tab** | Full analysis workflow. Sub-sections: Initial Setup (Google Patent ID input) → Search Plan (AI-generated terms, editable) → Batch Search (6-field form with per-search pagination, live log panel, queue-aware status) → Results table (title, status, found-by tags, AI category, reasoning) → Categorise controls → Google Sheet button. |
| **Add URL modal** | Floating "+ Add URL" button on Results section opens a modal. Paste a PDKI URL → dedup check → background extraction → live status with captcha detection message + "Open VNC" button. |
| **VNC panel** | Fixed floating "🖥 VNC" button (bottom-right, z-index above all modals). Opens a panel with noVNC iframe connected via FastAPI WebSocket proxy. Used to solve captchas without leaving the browser. |

---

### `output/` — Generated Data
Runtime output directory. Contains:
- `*.json` — pipeline result files (patent lists per search)
- `pipeline_logs/` — timestamped log files per run

---

## Key Design Decisions

**Chrome profile sharing** — All Selenium operations use a single Chrome profile at `/root/chrome-profile`. This means only one driver can run at a time. Enforced by `chrome_lock` (asyncio semaphore) in the web API.

**Captcha handling** — Detection: page source < 20 000 chars AND `id="main-iframe"` present. On detection: pause indefinitely, expose stage message to frontend, show "Open VNC" button. No auto-resolve. User solves manually via VNC panel.

**No re-navigation on extraction** — After navigating to a detail page and waiting for it to load, extraction functions (`extract_title`, `extract_status`, etc.) are called directly on the loaded DOM. `extract_detail()` (which internally re-navigates) is intentionally not used in the web API to avoid hitting a second captcha on the same page.

**Google Sheets export** — Only triggered after AI categorisation completes, never after a search. Triggered by `_sync_google_sheet()` called at the end of `run_categorize_job()`.
