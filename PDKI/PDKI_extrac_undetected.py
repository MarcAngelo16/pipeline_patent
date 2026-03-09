#!/usr/bin/env python3
"""
PDKI Extract Undetected - Search and extract patent links using undetected-chromedriver
"""

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException
import time
import json
import os
from datetime import datetime

PDKI_DIR = os.path.dirname(os.path.abspath(__file__))
SEARCH_URL = "https://pdki-indonesia.dgip.go.id/search"


def setup_driver():
    """Setup undetected Chrome driver with real profile to avoid reCAPTCHA"""
    # Point to the VNC display where Chrome can render
    os.environ['DISPLAY'] = ':99'

    options = uc.ChromeOptions()

    # Reuse the profile that has reCAPTCHA trust signals (manually verified working)
    options.add_argument("--user-data-dir=/root/chrome-profile")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=en-US")

    driver = uc.Chrome(options=options, version_main=145)
    return driver


def wait_for_page_load(driver):
    """Wait until the search form is present and page is fully loaded"""
    print("   Waiting for page to load...")
    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.TAG_NAME, "form"))
        )
        time.sleep(3)  # Extra settle time
        page_len = len(driver.page_source)
        print(f"   Page loaded ({page_len:,} chars)")
        return page_len > 30000
    except TimeoutException:
        print("   Timeout waiting for form")
        return False


def setup_search_form(driver, search_term="insulin", category="patent"):
    """Fill in the search form"""
    print(f"Setting up search: '{search_term}' / '{category}'")

    category_map = {
        'patent': 'Paten',
        'trademark': 'Merek',
        'design': 'Desain Industri',
        'copyright': 'Hak Cipta'
    }

    # Set category dropdown
    try:
        select_el = driver.find_element(By.CSS_SELECTOR, "select[aria-hidden='true']")
        Select(select_el).select_by_visible_text(category_map.get(category, 'Paten'))
        print(f"   Category set: {category_map.get(category, 'Paten')}")
    except Exception as e:
        print(f"   Could not set category: {e}")

    time.sleep(1)

    # Fill search input
    try:
        search_input = driver.find_element(By.CSS_SELECTOR, "input[type='text'], input:not([type])")
        search_input.clear()
        search_input.send_keys(search_term)
        print(f"   Search term entered: '{search_term}'")
    except Exception as e:
        print(f"   Could not fill search input: {e}")
        return False

    time.sleep(1)
    return True


def submit_search(driver):
    """Submit the search form and wait for results"""
    print("Submitting search...")

    timestamp = int(time.time())
    before_shot = os.path.join(PDKI_DIR, f"undetected_before_{timestamp}.png")
    driver.save_screenshot(before_shot)
    print(f"   Screenshot saved: {before_shot}")

    try:
        form = driver.find_element(By.TAG_NAME, "form")
        form.submit()
        print("   Form submitted, waiting for results...")
        time.sleep(15)

        page_len = len(driver.page_source)
        print(f"   Results page size: {page_len:,} chars")

        after_shot = os.path.join(PDKI_DIR, f"undetected_after_{timestamp}.png")
        driver.save_screenshot(after_shot)
        print(f"   Screenshot saved: {after_shot}")

        return page_len > 30000

    except Exception as e:
        print(f"   Submit failed: {e}")
        return False


def set_pagination_100(driver):
    """Change results per page to 100"""
    print("Setting pagination to 100...")

    try:
        buttons = driver.find_elements(By.CSS_SELECTOR, "button[role='combobox']")
        dropdown_btn = None

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
            print("   Pagination dropdown not found")
            return False

        if current_val == '100':
            print("   Already at 100")
            return True

        print(f"   Current: {current_val}, clicking dropdown...")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", dropdown_btn)
        time.sleep(1)
        dropdown_btn.click()
        time.sleep(2)

        # Find the 100 option
        option_100 = None
        for selector in ["div[role='option']", "button"]:
            try:
                for opt in driver.find_elements(By.CSS_SELECTOR, selector):
                    if opt.text.strip() == '100' and opt.is_displayed():
                        option_100 = opt
                        break
            except Exception:
                continue
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
    """Extract patent result links from the results page"""
    print("Extracting links...")
    all_links = []

    patterns = [
        "a[href*='/link/']",
        "a[href*='pdki-indonesia.dgip.go.id/link/']",
        "a[href*='detail']",
        "a[href*='patent']",
    ]

    for pattern in patterns:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, pattern)
            print(f"   Pattern '{pattern}': {len(elements)} elements")
            for el in elements:
                href = el.get_attribute('href')
                text = el.text.strip()
                if href and ('/link/' in href or 'detail' in href):
                    if not any(l['url'] == href for l in all_links):
                        all_links.append({'url': href, 'text': text[:100] or 'No text', 'pattern': pattern})
        except Exception:
            continue

    print(f"   Total unique links: {len(all_links)}")
    return all_links


def save_results(search_term, category, links):
    """Save results to JSON and text files"""
    timestamp = int(time.time())

    data = {
        'search_term': search_term,
        'category': category,
        'timestamp': timestamp,
        'total_links': len(links),
        'links': links
    }

    json_file = os.path.join(PDKI_DIR, f"undetected_results_{timestamp}.json")
    txt_file = os.path.join(PDKI_DIR, f"undetected_links_{timestamp}.txt")

    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    with open(txt_file, 'w', encoding='utf-8') as f:
        f.write(f"PDKI Undetected Extraction\n")
        f.write(f"Generated: {datetime.now()}\n")
        f.write(f"Search: {search_term} | Category: {category}\n")
        f.write(f"Total Links: {len(links)}\n")
        f.write("=" * 50 + "\n\n")
        for i, link in enumerate(links, 1):
            f.write(f"{i}. {link['url']}\n")
            f.write(f"   Text: {link['text']}\n\n")

    print(f"\nResults saved:")
    print(f"   JSON: {json_file}")
    print(f"   TXT:  {txt_file}")


def main():
    print("=" * 60)
    print("PDKI Extract - undetected-chromedriver")
    print("NOTE: Run with DISPLAY=:1 (VNC) for non-headless mode")
    print("=" * 60)

    SEARCH_TERM = "insulin"
    CATEGORY = "patent"

    driver = setup_driver()

    try:
        print(f"\nLoading {SEARCH_URL} ...")
        driver.get(SEARCH_URL)

        if not wait_for_page_load(driver):
            print("Page failed to load properly, check screenshot")
            return

        # Small dwell time before interacting (looks more human)
        time.sleep(2)

        if not setup_search_form(driver, SEARCH_TERM, CATEGORY):
            print("Failed to fill search form")
            return

        if not submit_search(driver):
            print("Search submission failed or got CAPTCHA — check screenshots")
            return

        set_pagination_100(driver)

        links = extract_links(driver)

        save_results(SEARCH_TERM, CATEGORY, links)

        print(f"\nDone. Links extracted: {len(links)}")

    except Exception as e:
        print(f"Fatal error: {e}")
        ts = int(time.time())
        driver.save_screenshot(os.path.join(PDKI_DIR, f"undetected_error_{ts}.png"))

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
