#!/usr/bin/env python3
"""
PDKI Advanced Search - Two-layer search pipeline (Phase 1)

Flow per search item:
  1. clear_all_fields()        — wipe main bar + all 5 advanced inputs
  2. fill_main_search()        — type into top search bar
  3. submit_main_search()      — click "Pencarian Data" button
  4. fill_advanced_search()    — (optional) fill Judul/Inventor/Konsultan/Abstrak/Pemegang
  5. click_terapkan()          — (optional) only when advanced fields are used
  6. set_pagination(n)         — 10, 50, or 100 — only changes if needed
  7. extract_links()           — collect patent URLs from results

Use run_search() to orchestrate multiple searches in one session.
"""

import os
import json
import time
import random
from datetime import datetime

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.keys import Keys

PDKI_DIR   = os.path.dirname(os.path.abspath(__file__))
SEARCH_URL = "https://pdki-indonesia.dgip.go.id/search"

# ── Advanced field labels (order matches the page top-to-bottom) ──────────────
ADVANCED_FIELDS = [
    "Judul",
    "Nama Inventor",
    "Nama Konsultan",
    "Abstrak",
    "Nama Pemegang",
]


# ══════════════════════════════════════════════════════════════════════════════
# Driver setup
# ══════════════════════════════════════════════════════════════════════════════

def setup_driver():
    os.environ['DISPLAY'] = ':99'

    profile_dir = "/root/chrome-profile"
    for lock_file in ["SingletonLock", "SingletonSocket", "SingletonCookie"]:
        lock_path = os.path.join(profile_dir, lock_file)
        if os.path.exists(lock_path) or os.path.islink(lock_path):
            try:
                os.remove(lock_path)
            except OSError:
                pass

    options = uc.ChromeOptions()
    options.add_argument("--user-data-dir=/root/chrome-profile")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=en-US")

    return uc.Chrome(options=options, version_main=145)


# ══════════════════════════════════════════════════════════════════════════════
# Captcha detection & handling
# ══════════════════════════════════════════════════════════════════════════════

def detect_captcha(driver) -> bool:
    """
    Return True if the current page is the Imperva captcha shell.

    The shell page is ~1198 chars and contains id="main-iframe".
    Normal PDKI pages are 50k+ chars. Checking only _Incapsula_Resource
    causes false positives because Imperva injects it into normal pages too.
    """
    src = driver.page_source
    return len(src) < 5000 and 'id="main-iframe"' in src


def wait_for_captcha_or_page(driver, page_ready_selector: str, timeout: int = 20) -> str:
    """
    Poll every second until captcha shell appears or expected element loads.

    Returns: "captcha" | "loaded" | "timeout"
    """
    for _ in range(timeout):
        if detect_captcha(driver):
            return "captcha"
        try:
            driver.find_element(By.CSS_SELECTOR, page_ready_selector)
            return "loaded"
        except NoSuchElementException:
            pass
        time.sleep(1)
    return "timeout"


def handle_captcha(driver) -> bool:
    """
    Attempt to resolve Imperva hCaptcha via simulated mouse movement.

    Structure:
      main document → iframe#main-iframe → iframe[title*='hCaptcha']

    Returns True if resolved, False otherwise.
    """
    if not detect_captcha(driver):
        return False

    print("[captcha] Detected — waiting 3s for iframe to render...")
    time.sleep(3)

    try:
        main_iframe = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "main-iframe"))
        )
        driver.switch_to.frame(main_iframe)
        print("[captcha] Switched into main-iframe")

        hcaptcha_iframe = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "iframe[title*='hCaptcha']")
            )
        )
        print(f"[captcha] hCaptcha iframe at {hcaptcha_iframe.location}")

        rand_x = -126 + random.randint(-4, 4)
        rand_y = random.randint(-5, 5)

        actions = ActionChains(driver)
        actions.move_to_element(driver.find_element(By.CSS_SELECTOR, "div.main-inner"))
        actions.pause(random.uniform(0.4, 0.8))
        actions.move_to_element(hcaptcha_iframe)
        actions.pause(random.uniform(0.2, 0.5))
        actions.move_to_element_with_offset(hcaptcha_iframe, rand_x, rand_y)
        actions.pause(random.uniform(0.1, 0.3))
        actions.click()
        actions.perform()

        print("[captcha] Click performed — waiting 5s...")
        driver.switch_to.default_content()
        time.sleep(5)

        if not detect_captcha(driver):
            print("[captcha] Resolved!")
            return True

        print("[captcha] Still present — pausing 30s for manual resolution via VNC...")
        time.sleep(30)
        return not detect_captcha(driver)

    except Exception as e:
        print(f"[captcha] Error: {e}")
        driver.switch_to.default_content()
        return False


# ══════════════════════════════════════════════════════════════════════════════
# Page loading
# ══════════════════════════════════════════════════════════════════════════════

def load_search_page(driver) -> bool:
    """
    Navigate to the PDKI search page, handle captcha if present,
    and wait until the advanced search inputs are visible.

    Returns True on success.
    """
    print(f"Loading {SEARCH_URL} ...")
    driver.get(SEARCH_URL)

    result = wait_for_captcha_or_page(driver, "input.input-advance")
    print(f"   Page check: {result} ({len(driver.page_source):,} chars)")

    if result == "captcha":
        print("   Captcha detected — solve it manually in VNC to continue")
        while detect_captcha(driver):
            time.sleep(5)
        print("   Captcha resolved — continuing")

    elif result == "timeout":
        print("   FAILED — page did not load in time")
        return False

    time.sleep(1)
    print(f"   Search page ready ({len(driver.page_source):,} chars)")
    return True


# ══════════════════════════════════════════════════════════════════════════════
# Category
# ══════════════════════════════════════════════════════════════════════════════

def set_category_paten(driver) -> bool:
    """Switch the category dropdown to Paten."""
    print("Setting category to Paten...")
    try:
        select_el = driver.find_element(By.CSS_SELECTOR, "select[aria-hidden='true']")
        Select(select_el).select_by_visible_text("Paten")
        print("   Category set to Paten")
        time.sleep(1)
        return True
    except Exception as e:
        print(f"   Could not set category: {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════════
# Field clearing
# ══════════════════════════════════════════════════════════════════════════════

def clear_all_fields(driver):
    """
    Clear the main search bar and all 5 advanced search inputs.
    Must be called before each new search to avoid stale values.
    """
    print("Clearing all search fields...")

    # Main search bar (does not have input-advance class)
    main_input = _find_main_search_input(driver)
    if main_input:
        driver.execute_script("arguments[0].value = '';", main_input)
        main_input.send_keys(Keys.CONTROL + 'a')
        main_input.send_keys(Keys.BACKSPACE)
        print("   Main search bar cleared")
    else:
        print("   Could not find main search bar to clear")

    # Advanced inputs — one per label
    for label_text in ADVANCED_FIELDS:
        try:
            inp = driver.find_element(
                By.XPATH,
                f"//label[normalize-space(text())='{label_text}']"
                f"/following::input[contains(@class,'input-advance')][1]"
            )
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", inp)
            driver.execute_script("arguments[0].click();", inp)
            inp.send_keys(Keys.CONTROL + 'a')
            inp.send_keys(Keys.BACKSPACE)
            time.sleep(0.15)
        except Exception as e:
            print(f"   Could not clear '{label_text}': {e}")

    print("   All fields cleared")


# ══════════════════════════════════════════════════════════════════════════════
# Main search (layer 1)
# ══════════════════════════════════════════════════════════════════════════════

def _find_main_search_input(driver):
    """
    Locate the main search bar.
    It has class 'rounded-full' which the advanced inputs do not.
    """
    try:
        return driver.find_element(By.CSS_SELECTOR, "input.rounded-full")
    except Exception:
        return None


def fill_main_search(driver, title: str):
    """Fill the top search bar with title."""
    print(f"Filling main search: {title!r}")
    main_input = _find_main_search_input(driver)
    if not main_input:
        print("   Could not find main search bar")
        return
    main_input.clear()
    main_input.send_keys(title)
    print(f"   Main search filled: {title!r}")
    time.sleep(0.3)


def submit_main_search(driver) -> bool:
    """Click the 'Pencarian Data' submit button and wait for results."""
    print("Submitting main search (Pencarian Data)...")
    try:
        btn = driver.find_element(By.CSS_SELECTOR, "button.bg-pdki[type='submit']")
        btn.click()
        print("   Pencarian Data clicked, waiting for results...")
        time.sleep(8)

        return True
    except Exception as e:
        print(f"   Could not click Pencarian Data: {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════════
# Advanced search (layer 2 — optional)
# ══════════════════════════════════════════════════════════════════════════════

def fill_advanced_search(
    driver,
    judul: str = None,
    nama_inventor: str = None,
    nama_konsultan: str = None,
    abstrak: str = None,
    nama_pemegang: str = None,
):
    """
    Fill the 5 advanced search inputs. Pass None to leave a field untouched.
    All fields share the same input-advance class and label→input XPath pattern.
    """
    fields = {
        "Judul":         judul,
        "Nama Inventor": nama_inventor,
        "Nama Konsultan": nama_konsultan,
        "Abstrak":       abstrak,
        "Nama Pemegang": nama_pemegang,
    }

    print(f"Filling advanced search: { {k: v for k, v in fields.items() if v} }")

    for label_text, value in fields.items():
        try:
            inp = driver.find_element(
                By.XPATH,
                f"//label[normalize-space(text())='{label_text}']"
                f"/following::input[contains(@class,'input-advance')][1]"
            )
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", inp)
            time.sleep(0.1)
            driver.execute_script("arguments[0].click();", inp)
            inp.send_keys(Keys.CONTROL + 'a')
            inp.send_keys(Keys.BACKSPACE)
            if value:
                inp.send_keys(value)
                print(f"   '{label_text}' = {value!r}")
            else:
                print(f"   '{label_text}' skipped")
            time.sleep(0.2)
        except Exception as e:
            print(f"   Could not interact with '{label_text}': {e}")


def click_terapkan(driver) -> bool:
    """Click the Terapkan (Apply) button for advanced search and wait for results."""
    print("Clicking Terapkan...")
    try:
        btn = driver.find_element(By.XPATH, "//button[.//span[text()='Terapkan']]")
        btn.click()
        print("   Terapkan clicked, waiting for results...")
        time.sleep(10)

        return True
    except Exception as e:
        print(f"   Could not click Terapkan: {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════════
# Pagination
# ══════════════════════════════════════════════════════════════════════════════

def set_pagination(driver, n: int = 100) -> bool:
    """
    Set results per page to n (10, 50, or 100).
    Reads the current value first and skips if already correct.
    """
    assert n in (10, 50, 100), "n must be 10, 50, or 100"
    target = str(n)
    print(f"   Setting pagination to {target}...")

    try:
        dropdown_btn = None
        current_val  = None

        for btn in driver.find_elements(By.CSS_SELECTOR, "button[role='combobox']"):
            try:
                span = btn.find_element(By.TAG_NAME, "span")
                if span.text.strip() in ('10', '50', '100'):
                    dropdown_btn = btn
                    current_val  = span.text.strip()
                    break
            except Exception:
                continue

        if not dropdown_btn:
            print("   Pagination dropdown not found — skipping")
            return False

        if current_val == target:
            print(f"   Already at {target}")
            return True

        print(f"   Current: {current_val} → switching to {target}...")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", dropdown_btn)
        time.sleep(0.5)
        dropdown_btn.click()
        time.sleep(1.5)

        option = None
        for selector in ("div[role='option']", "li", "button"):
            for opt in driver.find_elements(By.CSS_SELECTOR, selector):
                if opt.text.strip() == target and opt.is_displayed():
                    option = opt
                    break
            if option:
                break

        if not option:
            print(f"   Option '{target}' not found in dropdown")
            return False

        option.click()
        time.sleep(3)
        print(f"   Pagination set to {target}")
        return True

    except Exception as e:
        print(f"   Pagination error: {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════════
# Link extraction
# ══════════════════════════════════════════════════════════════════════════════

def extract_links(driver) -> list:
    """Extract unique patent result links from the current results page."""
    print("Extracting links...")
    all_links = []

    for pattern in ("a[href*='/link/']", "a[href*='detail']"):
        try:
            for el in driver.find_elements(By.CSS_SELECTOR, pattern):
                href = el.get_attribute('href')
                text = el.text.strip()
                if href and ('/link/' in href or 'detail' in href):
                    if not any(l['url'] == href for l in all_links):
                        all_links.append({'url': href, 'text': text[:100] or 'No text'})
        except Exception:
            continue

    print(f"   Found {len(all_links)} unique links")
    return all_links


# ══════════════════════════════════════════════════════════════════════════════
# Orchestration
# ══════════════════════════════════════════════════════════════════════════════

def run_search(driver, searches: list) -> list:
    """
    Run one or more searches in a single browser session.

    Each item in `searches` is a dict:
      {
        "main_title":     str,         # required — main search bar
        "pagination":     int,         # required — 10, 50, or 100
        "judul":          str | None,  # optional advanced fields
        "nama_inventor":  str | None,
        "nama_konsultan": str | None,
        "abstrak":        str | None,
        "nama_pemegang":  str | None,
      }

    Returns a deduplicated list of all extracted links across all searches.
    """
    all_links = []
    seen_urls = set()

    for i, search in enumerate(searches, 1):
        print(f"\n{'='*60}")
        print(f"Search {i}/{len(searches)}: {search}")
        print(f"{'='*60}")

        main_title = search.get("main_title", "")
        if not main_title:
            print("   Skipping — main_title is required")
            continue

        pagination = search.get("pagination", 100)
        if pagination not in (10, 50, 100):
            print(f"   Invalid pagination {pagination} — defaulting to 100")
            pagination = 100

        # ── Clear previous values ─────────────────────────────────────────
        if i > 1:
            clear_all_fields(driver)

        # ── Layer 1: main search ──────────────────────────────────────────
        fill_main_search(driver, main_title)
        if not submit_main_search(driver):
            print(f"   Search {i} failed at main search submit")
            continue

        # ── Layer 2: advanced search (optional) ───────────────────────────
        advanced_keys = ("judul", "nama_inventor", "nama_konsultan", "abstrak", "nama_pemegang")
        advanced_vals = {k: search.get(k) for k in advanced_keys}

        if any(v for v in advanced_vals.values()):
            fill_advanced_search(driver, **advanced_vals)
            if not click_terapkan(driver):
                print(f"   Search {i} failed at Terapkan")
                continue

        # ── Pagination ────────────────────────────────────────────────────
        set_pagination(driver, pagination)

        # ── Extract ───────────────────────────────────────────────────────
        links = extract_links(driver)
        new_count = 0
        for link in links:
            if link['url'] not in seen_urls:
                seen_urls.add(link['url'])
                all_links.append(link)
                new_count += 1

        print(f"   Search {i} done — {new_count} new links ({len(all_links)} total so far)")

        if i < len(searches):
            time.sleep(3)

    return all_links


# ══════════════════════════════════════════════════════════════════════════════
# Persistence
# ══════════════════════════════════════════════════════════════════════════════

def save_results(searches: list, links: list) -> str:
    ts = int(time.time())
    data = {
        'generated':   str(datetime.now()),
        'searches':    searches,
        'total_links': len(links),
        'links':       links,
    }

    json_file = os.path.join(PDKI_DIR, f"advanced_results_{ts}.json")
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    txt_file = os.path.join(PDKI_DIR, f"advanced_links_{ts}.txt")
    with open(txt_file, 'w', encoding='utf-8') as f:
        f.write(f"PDKI Search Results\n")
        f.write(f"Generated: {datetime.now()}\n")
        f.write(f"Total Links: {len(links)}\n")
        f.write("=" * 50 + "\n\n")
        for i, link in enumerate(links, 1):
            f.write(f"{i}. {link['url']}\n")
            f.write(f"   {link['text']}\n\n")

    print(f"\nSaved: {json_file}")
    print(f"Saved: {txt_file}")
    return json_file


# ══════════════════════════════════════════════════════════════════════════════
# CLI entry point
# ══════════════════════════════════════════════════════════════════════════════

def main():
    # ── Define your searches here ─────────────────────────────────────────────
    SEARCHES = [
        {
            "main_title":     "insulin",
            "pagination":     100,
            "judul":          None,
            "nama_inventor":  None,
            "nama_konsultan": None,
            "abstrak":        None,
            "nama_pemegang":  None,
        },
        {
            "main_title":     "insulin",
            "pagination":     50,
            "judul":          "insulin",
            "nama_inventor":  "Bayer",
            "nama_konsultan": None,
            "abstrak":        None,
            "nama_pemegang":  None,
        },
    ]
    # ─────────────────────────────────────────────────────────────────────────

    print("=" * 60)
    print("PDKI Two-Layer Search — Phase 1")
    print(f"Searches: {len(SEARCHES)}")
    print("=" * 60)

    driver = setup_driver()

    try:
        if not load_search_page(driver):
            print("FAILED — could not load search page")
            return

        if not set_category_paten(driver):
            print("FAILED — could not set category")
            return

        links = run_search(driver, SEARCHES)

        print(f"\n{'='*60}")
        print(f"All searches done — {len(links)} unique links total")
        save_results(SEARCHES, links)

    except Exception as e:
        print(f"Fatal error: {e}")
        driver.save_screenshot(os.path.join(PDKI_DIR, f"error_{int(time.time())}.png"))

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
