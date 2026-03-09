#!/usr/bin/env python3
"""
PDKI Detail Extractor - Visits each link from combined_results JSON
and extracts patent details: title, status, priority numbers,
inventors, assignees, and abstract.
"""

import os
import json
import time
import glob
import argparse
from datetime import datetime

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

PDKI_DIR = os.path.dirname(os.path.abspath(__file__))


def setup_driver():
    os.environ['DISPLAY'] = ':99'
    options = uc.ChromeOptions()
    options.add_argument("--user-data-dir=/root/chrome-profile")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=en-US")
    return uc.Chrome(options=options, version_main=145)


def wait_for_detail_page(driver):
    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "h1"))
        )
        time.sleep(3)
        return True
    except TimeoutException:
        return False


def extract_title(driver):
    try:
        return driver.find_element(By.CSS_SELECTOR, "h1.text-xl").text.strip()
    except Exception:
        return None


def extract_status(driver):
    # Scope to the Status label's sibling container to avoid matching other rounded-full elements
    try:
        label = driver.find_element(
            By.XPATH,
            "//div[contains(@class,'text-gray-700') and normalize-space(text())='Status']"
        )
        container = label.find_element(By.XPATH, "following-sibling::div[1]")
        badge = container.find_element(By.CSS_SELECTOR, "div.inline-flex")
        return badge.text.strip()
    except Exception:
        return None


def extract_field_by_label(driver, *label_texts):
    """Extract a value by trying one or more label texts. Returns the first match."""
    for label_text in label_texts:
        try:
            label = driver.find_element(
                By.XPATH,
                f"//div[contains(@class,'text-gray-700') and normalize-space(text())='{label_text}']"
            )
            value = label.find_element(By.XPATH, "following-sibling::div[1]").text.strip()
            if value:
                return value
        except Exception:
            continue
    return None


def extract_abstract(driver):
    try:
        heading = driver.find_element(
            By.XPATH,
            "//div[contains(@class,'font-semibold') and normalize-space(text())='Abstract']"
        )
        text_div = heading.find_element(By.XPATH, "following-sibling::div[1]")
        return text_div.text.strip()
    except Exception:
        return None


def find_section_rows(driver, keyword):
    """Find tbody rows for a section identified by a keyword in its heading."""
    # Section headings use font-bold (not font-semibold)
    for cls in ['font-bold', 'font-semibold']:
        try:
            heading = driver.find_element(
                By.XPATH,
                f"//*[contains(@class,'{cls}') and contains(normalize-space(text()),'{keyword}')]"
            )
            rows = heading.find_elements(By.XPATH, "following::tbody[1]/tr")
            if rows:
                return rows
        except Exception:
            continue
    return []


def extract_priority_numbers(driver):
    priorities = []
    for row in find_section_rows(driver, 'Prioritas'):
        cells = row.find_elements(By.TAG_NAME, 'td')
        if len(cells) >= 3:
            priorities.append({
                'number': cells[0].text.strip(),
                'date':   cells[1].text.strip(),
                'country': cells[2].text.strip(),
            })
    return priorities


def extract_inventors(driver):
    inventors = []
    for row in find_section_rows(driver, 'Inventor'):
        cells = row.find_elements(By.TAG_NAME, 'td')
        if len(cells) >= 2:
            inventors.append({
                'name':    cells[0].text.strip(),
                'country': cells[1].text.strip(),
            })
    return inventors


def extract_assignees(driver):
    assignees = []
    for row in find_section_rows(driver, 'Pemegang'):
        cells = row.find_elements(By.TAG_NAME, 'td')
        if len(cells) >= 3:
            assignees.append({
                'name':    cells[0].text.strip(),
                'address': cells[1].text.strip(),
                'country': cells[2].text.strip(),
            })
    return assignees


def extract_detail(driver, url, debug=False):
    print(f"   Loading: {url}")
    driver.get(url)

    if not wait_for_detail_page(driver):
        print("   Timeout — skipping")
        return None

    if debug:
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(0.5)
        slug = url.split('/')[-1][:20]
        shot = os.path.join(PDKI_DIR, f"detail_{slug}_{int(time.time())}.png")
        driver.save_screenshot(shot)
        print(f"   Screenshot: {shot}")

    return {
        'url':                url,
        'title':              extract_title(driver),
        'nomor_permohonan':   extract_field_by_label(driver, 'No. Permohonan', 'No. Paten'),
        'tgl_penerimaan':     extract_field_by_label(driver, 'Tgl. Penerimaan', 'Tgl. Pemberian'),
        'status':             extract_status(driver),
        'priority_numbers':   extract_priority_numbers(driver),
        'inventors':          extract_inventors(driver),
        'assignees':          extract_assignees(driver),
        'abstract':           extract_abstract(driver),
    }


def find_latest_combined_json():
    files = glob.glob(os.path.join(PDKI_DIR, 'combined_results_*.json'))
    return max(files, key=os.path.getmtime) if files else None


def main():
    parser = argparse.ArgumentParser(description="PDKI Detail Extractor")
    parser.add_argument('--input', help="Path to combined_results JSON (default: latest)")
    parser.add_argument('--debug', action='store_true', help="Save a screenshot per detail page")
    args = parser.parse_args()

    input_file = args.input or find_latest_combined_json()
    if not input_file:
        print("No combined_results JSON found. Run PDKI_advanced.py first.")
        return

    print("=" * 60)
    print("PDKI Detail Extractor")
    if args.debug:
        print("  [DEBUG] Per-page screenshots enabled")
    print("=" * 60)
    print(f"Input: {input_file}")

    with open(input_file, encoding='utf-8') as f:
        combined = json.load(f)

    links = combined.get('links', combined.get('patents', []))
    print(f"Links to process: {len(links)}\n")

    driver = setup_driver()
    results = []

    try:
        for i, link in enumerate(links, 1):
            print(f"[{i}/{len(links)}] {link.get('text', '')[:60]}")
            detail = extract_detail(driver, link['url'], debug=args.debug)
            if detail:
                results.append(detail)
                print(f"   Title:      {detail['title']}")
                print(f"   Status:     {detail['status']}")
                print(f"   Inventors:  {len(detail['inventors'])}")
                print(f"   Assignees:  {len(detail['assignees'])}")
                print(f"   Priorities: {len(detail['priority_numbers'])}")
            else:
                print(f"   Failed to extract — skipped")

            if i < len(links):
                time.sleep(2)

    except Exception as e:
        print(f"Fatal error: {e}")
        driver.save_screenshot(os.path.join(PDKI_DIR, f"extractor_error_{int(time.time())}.png"))

    finally:
        driver.quit()

    ts = int(time.time())
    out_file = os.path.join(PDKI_DIR, f"extracted_details_{ts}.json")
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump({
            'source':    input_file,
            'generated': str(datetime.now()),
            'total':     len(results),
            'patents':   results,
        }, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"Done. Extracted {len(results)}/{len(links)} patents.")
    print(f"Saved: {out_file}")


if __name__ == "__main__":
    main()
