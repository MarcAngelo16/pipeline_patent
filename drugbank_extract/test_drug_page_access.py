#!/usr/bin/env python3
"""
Test Drug Page Access - Test if we can access specific drug pages
"""

import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options


def test_drug_page_access(drugbank_id="DB05541"):
    """Test if stealth mode can access a specific drug page"""

    print("="*60)
    print(f"TESTING DRUG PAGE ACCESS - {drugbank_id}")
    print("="*60)

    # Setup Chrome with stealth options
    print("\nStep 1: Setting up Chrome with stealth configuration...")

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")

    # STEALTH MODE
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    service = Service('/usr/local/bin/chromedriver')
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    print("   Chrome driver initialized")

    try:
        # Test: Access drug page directly
        print(f"\nStep 2: Testing access to drug page {drugbank_id}...")
        test_url = f"https://go.drugbank.com/drugs/{drugbank_id}"

        driver.get(test_url)
        print(f"   Navigated to: {test_url}")

        # Wait for page to load
        print("   Waiting 5 seconds for page to load...")
        time.sleep(5)

        # Check page content
        page_source = driver.page_source
        page_length = len(page_source)
        page_title = driver.title

        print(f"\nStep 3: Analyzing response...")
        print(f"   Page title: {page_title}")
        print(f"   Page size: {page_length:,} characters")

        # Check for Cloudflare indicators
        cloudflare_indicators = [
            "Just a moment",
            "Checking your browser",
            "challenge-platform"
        ]

        blocked = False
        for indicator in cloudflare_indicators:
            if indicator in page_source:
                print(f"   [BLOCKED] Found Cloudflare indicator: '{indicator}'")
                blocked = True
                break

        # Check for drug page indicators
        drug_page_indicators = [
            "Brivaracetam",  # Drug name
            "Patents",  # Section we need
            "Pharmacoeconomics",  # Section containing patents
            drugbank_id,  # DrugBank ID should appear
            "patent"  # Should mention patents
        ]

        found_indicators = []
        for indicator in drug_page_indicators:
            if indicator in page_source:
                found_indicators.append(indicator)
                print(f"   [FOUND] '{indicator}'")

        # Check for patents table specifically
        print(f"\nStep 4: Checking for patents table...")
        if 'id="patents"' in page_source:
            print("   Patents table found (id='patents')")

            # Count patent rows
            import re
            patent_links = re.findall(r'patents\.google\.com/patent/([A-Z0-9]+)', page_source)
            print(f"   Found {len(patent_links)} patent links")
            if patent_links:
                print(f"   Patents: {', '.join(patent_links[:5])}")
        else:
            print("   [WARNING] Patents table not found")

        # Take screenshot
        screenshot_path = f"/app/patent_pipeline/drugbank_extract/drug_page_{drugbank_id}_screenshot.png"
        driver.save_screenshot(screenshot_path)
        print(f"\n   Screenshot saved: {screenshot_path}")

        # Save page source
        html_path = f"/app/patent_pipeline/drugbank_extract/drug_page_{drugbank_id}.html"
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(page_source)
        print(f"   Page HTML saved: {html_path}")

        # Verdict
        print(f"\n{'='*60}")
        print("VERDICT:")
        print(f"{'='*60}")

        if blocked:
            print("[FAILED] Cloudflare is blocking drug page access")
            return False
        elif len(found_indicators) >= 3 and 'id="patents"' in page_source:
            print("[SUCCESS] Drug page loaded with patent data")
            print(f"   Found {len(found_indicators)}/{len(drug_page_indicators)} indicators")
            print(f"   Patents table: PRESENT")
            return True
        elif len(found_indicators) >= 2:
            print("[PARTIAL] Page loaded but patents unclear")
            print(f"   Found {len(found_indicators)}/{len(drug_page_indicators)} indicators")
            return None
        else:
            print("[FAILED] Page doesn't look like a drug page")
            return False

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        driver.quit()
        print("\nBrowser closed")


if __name__ == "__main__":
    result = test_drug_page_access("DB05541")

    print("\n" + "="*60)
    if result is True:
        print("[SUCCESS] We can access drug pages AND extract patents")
        print("   Ready to implement full patent extraction")
    elif result is False:
        print("[FAILED] Cannot access drug pages")
        print("   Need alternative approach")
    else:
        print("[UNCLEAR] Check saved files for details")
    print("="*60)
