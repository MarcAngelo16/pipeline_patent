#!/usr/bin/env python3
"""
Test Stealth Mode - DrugBank Cloudflare Bypass
Tests if our stealth configuration can bypass Cloudflare protection
"""

import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options


def test_stealth_access():
    """Test if stealth mode can access DrugBank"""

    print("="*60)
    print("TESTING STEALTH MODE - DRUGBANK CLOUDFLARE BYPASS")
    print("="*60)

    # Setup Chrome with stealth options
    print("\n1️⃣  Setting up Chrome with stealth configuration...")

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")

    # STEALTH MODE - Anti-bot detection
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    # User agent
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    service = Service('/usr/local/bin/chromedriver')
    driver = webdriver.Chrome(service=service, options=chrome_options)

    # Additional stealth scripts
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    print("   ✅ Chrome driver initialized")

    try:
        # Test 1: Access search page
        print("\n2️⃣  Testing access to DrugBank search page...")
        test_url = "https://go.drugbank.com/drugs"

        driver.get(test_url)
        print(f"   🌐 Navigated to: {test_url}")

        # Wait a bit for page to load
        print("   ⏳ Waiting 5 seconds for page to load...")
        time.sleep(5)

        # Check page content
        page_source = driver.page_source
        page_length = len(page_source)
        page_title = driver.title

        print(f"\n3️⃣  Analyzing response...")
        print(f"   📄 Page title: {page_title}")
        print(f"   📊 Page size: {page_length:,} characters")

        # Check for Cloudflare indicators
        cloudflare_indicators = [
            "Just a moment",
            "Checking your browser",
            "Cloudflare",
            "Ray ID",
            "challenge-platform"
        ]

        blocked = False
        for indicator in cloudflare_indicators:
            if indicator in page_source:
                print(f"   ❌ Found Cloudflare indicator: '{indicator}'")
                blocked = True
                break

        # Check for success indicators
        success_indicators = [
            "DrugBank",
            "search",
            "query",
            '<input',
            '<form'
        ]

        success_count = 0
        for indicator in success_indicators:
            if indicator.lower() in page_source.lower():
                success_count += 1

        print(f"   ✅ Found {success_count}/{len(success_indicators)} success indicators")

        # Take screenshot
        screenshot_path = "/app/patent_pipeline/drugbank_extract/stealth_test_screenshot.png"
        driver.save_screenshot(screenshot_path)
        print(f"   📸 Screenshot saved: {screenshot_path}")

        # Save page source for inspection
        html_path = "/app/patent_pipeline/drugbank_extract/stealth_test_page.html"
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(page_source)
        print(f"   💾 Page HTML saved: {html_path}")

        # Verdict
        print(f"\n{'='*60}")
        print("VERDICT:")
        print(f"{'='*60}")

        if blocked:
            print("❌ STEALTH MODE FAILED - Cloudflare is blocking us")
            print("   The page shows Cloudflare challenge")
            return False
        elif success_count >= 3:
            print("✅ STEALTH MODE SUCCESS - We bypassed Cloudflare!")
            print("   The page loaded with actual content")
            return True
        else:
            print("⚠️  UNCLEAR - Page loaded but content is suspicious")
            print(f"   Only found {success_count} success indicators")
            print("   Check the saved HTML file for details")
            return None

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        driver.quit()
        print("\n🔒 Browser closed")


if __name__ == "__main__":
    result = test_stealth_access()

    if result is True:
        print("\n🎉 GREAT NEWS! Stealth mode works - we can proceed with implementation")
    elif result is False:
        print("\n😞 BAD NEWS: Stealth mode doesn't work - we need a different approach")
    else:
        print("\n🤔 INCONCLUSIVE: Manual inspection needed")
