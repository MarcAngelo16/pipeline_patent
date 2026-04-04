#!/usr/bin/env python3
"""
Captcha Observation Test — Two-Layer Pipeline

Uses:
  Phase 1 — PDKI_advanced.py   : search + extract links
  Phase 2 — PDKI_detail_extractor.py : visit each link + extract detail

Fill SEARCHES below, then run. Watch VNC to observe captcha triggers.
"""

import sys
import time
from pathlib import Path
from datetime import datetime

from selenium.webdriver.common.by import By

# ── Paths ─────────────────────────────────────────────────────────────────────
TESTING_DIR  = Path(__file__).parent
PDKI_DIR     = TESTING_DIR.parent
PIPELINE_DIR = PDKI_DIR.parent

sys.path.insert(0, str(PIPELINE_DIR))

from PDKI.PDKI_advanced import (
    setup_driver,
    load_search_page,
    set_category_paten,
    run_search,
    detect_captcha,
    wait_for_captcha_or_page,
    handle_captcha,
    save_results,
)
from PDKI.PDKI_detail_extractor import (
    setup_driver as setup_detail_driver,
    extract_detail,
)

# ══════════════════════════════════════════════════════════════════════════════
# Fill in your searches here
# ══════════════════════════════════════════════════════════════════════════════
SEARCHES = [
    {
        "main_title":     "komposisi",   # required — top search bar
        "pagination":     10,         # required — 10, 50, or 100
        "judul":          None,        # optional advanced fields below
        "nama_inventor":  None,
        "nama_konsultan": None,
        "abstrak":        "infus",
        "nama_pemegang":  None,
    },
        {
        "main_title":     "karboksamida",   # required — top search bar
        "pagination":     50,         # required — 10, 50, or 100
        "judul":          None,        # optional advanced fields below
        "nama_inventor":  "Bayer",
        "nama_konsultan": None,
        "abstrak":        None,
        "nama_pemegang":  None,
    },
        {
        "main_title":     "valbenazin",   # required — top search bar
        "pagination":     100,         # required — 10, 50, or 100
        "judul":          None,        # optional advanced fields below
        "nama_inventor":  None,
        "nama_konsultan": None,
        "abstrak":        None,
        "nama_pemegang":  "Neurocrine Biosciences",
    },
]

DELAY_BETWEEN_DETAILS = 5   # seconds between each detail page visit (Phase 2)
# ══════════════════════════════════════════════════════════════════════════════


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def wait_for_page_or_manual_fix(driver, url: str) -> bool:
    """
    Poll indefinitely every 5 seconds until the detail page fully loads.

    If the page is blocked (captcha or frozen):
      - Takes a screenshot so you can see what's on screen
      - Prints a clear message to terminal
      - Keeps polling — resumes automatically once you fix it in VNC

    Returns True when page is ready, raises if Chrome itself has died.
    """
    poll_interval = 5
    notified      = False

    while True:
        try:
            _ = driver.current_url  # raises if Chrome crashed
        except Exception:
            log("  Chrome session lost — cannot continue")
            raise

        src = driver.page_source
        src_len = len(src)

        # Page fully loaded — has h1 and enough content
        try:
            driver.find_element(By.CSS_SELECTOR, "h1")
            if src_len > 20000:
                if notified:
                    log("  Page loaded — continuing")
                return True
        except Exception:
            pass

        # Not loaded yet — notify once, then keep polling silently
        if not notified:
            log(f"  Page inaccessible ({src_len:,} chars) — waiting for manual fix in VNC")
            log(f"  URL: {url}")
            screenshot_path = Path(__file__).parent / f"blocked_{int(time.time())}.png"
            try:
                driver.save_screenshot(str(screenshot_path))
                log(f"  Screenshot: {screenshot_path}")
            except Exception:
                pass
            log("  Polling every 5s — solve captcha in VNC to continue, Ctrl+C to stop")
            notified = True

        time.sleep(poll_interval)


def fetch_detail_with_captcha_check(driver, url: str) -> dict | None:
    """
    Navigate to a detail URL, wait indefinitely for it to become accessible,
    then run extract_detail. If blocked or captcha, pauses for manual VNC fix.
    """
    driver.get(url)
    time.sleep(2)

    try:
        wait_for_page_or_manual_fix(driver, url)
    except Exception:
        return None

    return extract_detail(driver, url, debug=False)


def main():
    if not SEARCHES:
        print("Fill in the SEARCHES list at the top of this file first.")
        return

    print("=" * 60)
    print("Captcha Observation Test — Two-Layer Pipeline")
    print(f"Searches: {len(SEARCHES)}")
    print("Watch VNC to observe captcha triggers")
    print("=" * 60)

    # ── Phase 1: search & extract links ───────────────────────────────────────
    log("Starting Phase 1 — search & extract links")
    driver = setup_driver()
    links  = []

    try:
        if not load_search_page(driver):
            log("FAILED — could not load search page")
            return

        if not set_category_paten(driver):
            log("FAILED — could not set category to Paten")
            return

        links = run_search(driver, SEARCHES)
        log(f"Phase 1 done — {len(links)} unique links extracted")

        for i, link in enumerate(links, 1):
            log(f"  [{i:>3}] {link['url']}")

        if links:
            save_results(SEARCHES, links)

    finally:
        driver.quit()
        log("Search driver closed")

    if not links:
        log("No links to process — stopping here")
        return

    # ── Phase 2: visit each detail page ───────────────────────────────────────
    print()
    print("=" * 60)
    log(f"Starting Phase 2 — detail extraction for {len(links)} links")
    print("=" * 60)

    detail_driver = setup_detail_driver()

    try:
        for i, link in enumerate(links, 1):
            url  = link["url"]
            text = link.get("text", "")[:60]

            log(f"[{i}/{len(links)}] {text}")
            log(f"  URL: {url}")

            detail = fetch_detail_with_captcha_check(detail_driver, url)

            if detail:
                log(f"  OK — title:  {detail.get('title', 'N/A')}")
                log(f"       status: {detail.get('status', 'N/A')}")
            else:
                log(f"  FAILED — skipping")
                time.sleep(5)

            if i < len(links):
                log(f"  Waiting {DELAY_BETWEEN_DETAILS}s...")
                time.sleep(DELAY_BETWEEN_DETAILS)

    finally:
        detail_driver.quit()
        log("Detail driver closed")

    print()
    print("=" * 60)
    log("Test complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
