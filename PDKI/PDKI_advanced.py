#!/usr/bin/env python3
"""
PDKI Advanced Search - Uses the Advanced Search panel fields directly
(Judul, Nama Inventor, Nama Pemegang) instead of the main search bar.
"""

import os
import json
import time
import argparse
from datetime import datetime

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.keys import Keys

PDKI_DIR = os.path.dirname(os.path.abspath(__file__))
SEARCH_URL = "https://pdki-indonesia.dgip.go.id/search"


def setup_driver():
    os.environ['DISPLAY'] = ':99'

    options = uc.ChromeOptions()
    options.add_argument("--user-data-dir=/root/chrome-profile")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=en-US")

    return uc.Chrome(options=options, version_main=145)


def wait_for_page(driver):
    print("   Waiting for page to load...")
    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input.input-advance"))
        )
        time.sleep(2)
        print(f"   Page loaded ({len(driver.page_source):,} chars)")
        return True
    except TimeoutException:
        print("   Timeout — advanced search inputs not found")
        return False


def set_category_paten(driver):
    """Switch category dropdown from Merek to Paten"""
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


def fill_advanced_search(driver, judul=None, nama_inventor=None, nama_pemegang=None):
    """Fill advanced search fields — always clears first to reset previous search values"""
    print(f"Filling advanced search: judul={judul!r}, inventor={nama_inventor!r}, pemegang={nama_pemegang!r}")

    fields = {
        'Judul': judul,
        'Nama Inventor': nama_inventor,
        'Nama Pemegang': nama_pemegang,
    }

    for label_text, value in fields.items():
        try:
            input_el = driver.find_element(
                By.XPATH,
                f"//label[normalize-space(text())='{label_text}']/following::input[contains(@class,'input-advance')][1]"
            )
            # Scroll into view and use JS click to avoid overlay interception
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", input_el)
            time.sleep(0.2)
            driver.execute_script("arguments[0].click();", input_el)
            input_el.send_keys(Keys.CONTROL + 'a')
            input_el.send_keys(Keys.BACKSPACE)
            if value:
                input_el.send_keys(value)
                print(f"   '{label_text}' = {value!r}")
            else:
                print(f"   '{label_text}' cleared")
            time.sleep(0.3)
        except Exception as e:
            print(f"   Could not interact with '{label_text}': {e}")

    return True


def click_terapkan(driver, label="", screenshot=False):
    """Click the Terapkan (Apply) button and optionally screenshot the result"""
    print("Clicking Terapkan...")
    try:
        btn = driver.find_element(By.XPATH, "//button[.//span[text()='Terapkan']]")
        btn.click()
        print("   Terapkan clicked, waiting for results...")
        time.sleep(10)

        if screenshot:
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(0.5)
            ts = int(time.time())
            slug = label.replace(" ", "_").replace("/", "-") if label else str(ts)
            shot = os.path.join(PDKI_DIR, f"advanced_result_{slug}_{ts}.png")
            driver.save_screenshot(shot)
            print(f"   Screenshot: {shot}")
        return True
    except Exception as e:
        print(f"   Could not click Terapkan: {e}")
        return False


def set_pagination_100(driver):
    """Change results per page to 100 to maximise links extracted per search."""
    print("   Setting pagination to 100...")
    try:
        buttons = driver.find_elements(By.CSS_SELECTOR, "button[role='combobox']")
        dropdown_btn = None
        current_val = None

        for btn in buttons:
            try:
                span = btn.find_element(By.TAG_NAME, "span")
                if span.text.strip() in ['10', '50', '100']:
                    dropdown_btn = btn
                    current_val = span.text.strip()
                    break
            except Exception:
                continue

        if not dropdown_btn:
            print("   Pagination dropdown not found — skipping")
            return False

        if current_val == '100':
            print("   Already at 100")
            return True

        print(f"   Current: {current_val}, switching to 100...")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", dropdown_btn)
        time.sleep(0.5)
        dropdown_btn.click()
        time.sleep(1.5)

        option_100 = None
        for selector in ["div[role='option']", "li", "button"]:
            for opt in driver.find_elements(By.CSS_SELECTOR, selector):
                if opt.text.strip() == '100' and opt.is_displayed():
                    option_100 = opt
                    break
            if option_100:
                break

        if not option_100:
            print("   100 option not found in dropdown")
            return False

        option_100.click()
        time.sleep(3)
        print("   Pagination set to 100")
        return True

    except Exception as e:
        print(f"   Pagination error: {e}")
        return False


def extract_links(driver):
    """Extract patent result links"""
    print("Extracting links...")
    all_links = []

    for pattern in ["a[href*='/link/']", "a[href*='detail']"]:
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


def save_results(filters, links):
    ts = int(time.time())
    data = {
        'filters': filters,
        'timestamp': ts,
        'generated': str(datetime.now()),
        'total_links': len(links),
        'links': links
    }

    json_file = os.path.join(PDKI_DIR, f"advanced_results_{ts}.json")
    txt_file = os.path.join(PDKI_DIR, f"advanced_links_{ts}.txt")

    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    with open(txt_file, 'w', encoding='utf-8') as f:
        f.write(f"PDKI Advanced Search Results\n")
        f.write(f"Generated: {datetime.now()}\n")
        f.write(f"Filters: {filters}\n")
        f.write(f"Total Links: {len(links)}\n")
        f.write("=" * 50 + "\n\n")
        for i, link in enumerate(links, 1):
            f.write(f"{i}. {link['url']}\n")
            f.write(f"   Text: {link['text']}\n\n")

    print(f"\nSaved: {json_file}")
    print(f"Saved: {txt_file}")


def save_combined(all_results, batches_meta):
    """Save all unique links from all batches into a single JSON, deduplicated by URL."""
    seen_urls = set()
    unique_links = []
    for result in all_results:
        for link in result['links']:
            if link['url'] not in seen_urls:
                seen_urls.add(link['url'])
                unique_links.append(link)

    ts = int(time.time())
    data = {
        'generated': str(datetime.now()),
        'batches': batches_meta,
        'total_unique_links': len(unique_links),
        'links': unique_links,
    }

    json_file = os.path.join(PDKI_DIR, f"combined_results_{ts}.json")
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\nSaved combined results: {json_file}")
    print(f"Total unique links: {len(unique_links)}")
    return json_file


def main():
    parser = argparse.ArgumentParser(description="PDKI Advanced Search - Batch Mode")
    parser.add_argument(
        '--debug',
        action='store_true',
        help="Enable per-search screenshots and individual JSON output"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("PDKI Advanced Search - Batch Mode")
    if args.debug:
        print("  [DEBUG] Screenshots and per-search output enabled")
    print("=" * 60)

    # --- Define your batch searches here ---
    BATCHES = [
        {'judul': 'OSTEOPROTEGERIN', 'nama_inventor': None,        'nama_pemegang': None},
        {'judul': 'OSTEOPROTEGERIN',  'nama_inventor': 'William J', 'nama_pemegang': None},
        {'judul': 'OSTEOPROTEGERIN', 'nama_inventor': None,        'nama_pemegang': 'PHARMEXA'},
    ]
    # ----------------------------------------

    driver = setup_driver()

    try:
        print(f"\nLoading {SEARCH_URL} ...")
        driver.get(SEARCH_URL)

        if not wait_for_page(driver):
            driver.save_screenshot(os.path.join(PDKI_DIR, "advanced_load_fail.png"))
            return

        if not set_category_paten(driver):
            return

        all_results = []

        for i, batch in enumerate(BATCHES, 1):
            print(f"\n{'='*60}")
            print(f"Batch {i}/{len(BATCHES)}: {batch}")
            print(f"{'='*60}")

            label_parts = [v for v in batch.values() if v]
            label = "_".join(label_parts) if label_parts else f"batch{i}"

            fill_advanced_search(driver, **batch)

            if not click_terapkan(driver, label=label, screenshot=args.debug):
                print(f"   Skipping batch {i} — Terapkan failed")
                continue

            links = extract_links(driver)

            if args.debug:
                save_results(batch, links)

            all_results.append({'batch': batch, 'links': links})
            print(f"   Batch {i} complete — {len(links)} links")

            if i < len(BATCHES):
                print(f"   Waiting 3 seconds before next search...")
                time.sleep(3)

        print(f"\n{'='*60}")
        print(f"All batches done. Deduplicating and saving...")

        save_combined(all_results, BATCHES)

    except Exception as e:
        print(f"Fatal error: {e}")
        driver.save_screenshot(os.path.join(PDKI_DIR, f"advanced_error_{int(time.time())}.png"))

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
