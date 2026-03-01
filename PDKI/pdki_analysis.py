#!/usr/bin/env python3
"""
PDKI Analysis - Debug script to understand what triggers CAPTCHA
Based on search_and_extract_links100.py with detailed diagnostics at each step
"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, ElementNotInteractableException
from selenium_stealth import stealth
import time
import json
import os
from datetime import datetime

PDKI_DIR = os.path.dirname(os.path.abspath(__file__))

def dump_page(driver, label):
    """Save screenshot + HTML + diagnostics at any stage"""
    timestamp = int(time.time())
    print(f"\n{'='*60}")
    print(f"🔬 DUMP: {label}")
    print(f"{'='*60}")

    # Current URL and title
    print(f"   🌐 URL:   {driver.current_url}")
    print(f"   📄 Title: {driver.title}")

    # Page size
    source = driver.page_source
    print(f"   📊 Size:  {len(source):,} chars")

    # CAPTCHA / block detection
    source_lower = source.lower()
    flags = []
    if 'captcha'        in source_lower: flags.append('CAPTCHA')
    if 'cloudflare'     in source_lower: flags.append('Cloudflare')
    if 'just a moment'  in source_lower: flags.append('CF JS Challenge')
    if 'recaptcha'      in source_lower: flags.append('reCAPTCHA')
    if 'hcaptcha'       in source_lower: flags.append('hCaptcha')
    if 'access denied'  in source_lower: flags.append('Access Denied')
    if 'robot'          in source_lower: flags.append('Anti-robot msg')
    if 'verify'         in source_lower: flags.append('Verify prompt')
    if 'blocked'        in source_lower: flags.append('Blocked msg')
    if 'error'          in source_lower: flags.append('Error msg')

    if flags:
        print(f"   🚨 Detected: {', '.join(flags)}")
    else:
        print(f"   ✅ No CAPTCHA/block signals detected")

    # Check if actual results are present
    if 'paten' in source_lower and ('hasil' in source_lower or 'result' in source_lower):
        print(f"   ✅ Results content detected")

    # Screenshot
    shot = os.path.join(PDKI_DIR, f"analysis_{label}_{timestamp}.png")
    driver.save_screenshot(shot)
    print(f"   📸 Screenshot: {shot}")

    # Save HTML
    html = os.path.join(PDKI_DIR, f"analysis_{label}_{timestamp}.html")
    with open(html, 'w', encoding='utf-8') as f:
        f.write(source)
    print(f"   💾 HTML: {html}")


def setup_driver():
    """Selenium driver with stealth — based on working config"""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(options=options)

    stealth(driver,
        languages=["id-ID", "id", "en-US", "en"],
        vendor="Google Inc.",
        platform="Win32",
        webgl_vendor="Intel Inc.",
        renderer="Intel Iris OpenGL Engine",
        fix_hairline=True,
    )

    return driver


def main():
    print("=" * 70)
    print("🔍 PDKI ANALYSIS - Diagnosing CAPTCHA trigger point")
    print("=" * 70)

    driver = setup_driver()

    try:
        # ── STAGE 1: Initial page load ──────────────────────────────────────
        print("\n📌 STAGE 1: Loading search page")
        driver.get("https://pdki-indonesia.dgip.go.id/search")
        time.sleep(4)
        dump_page(driver, "1_page_load")

        # ── STAGE 2: After waiting longer ───────────────────────────────────
        print("\n📌 STAGE 2: Waiting 5 more seconds")
        time.sleep(5)
        dump_page(driver, "2_after_wait")

        # ── STAGE 3: After typing in search box ─────────────────────────────
        print("\n📌 STAGE 3: Typing search term")
        try:
            search_input = driver.find_element(By.CSS_SELECTOR, "input[type='text'], input:not([type])")
            search_input.clear()
            time.sleep(1)
            search_input.send_keys("insulin")
            print("   ✅ Typed 'insulin'")
            time.sleep(2)
        except Exception as e:
            print(f"   ❌ Could not type: {e}")
        dump_page(driver, "3_after_typing")

        # ── STAGE 4: Immediately after clicking submit ───────────────────────
        print("\n📌 STAGE 4: Clicking submit button")
        try:
            btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            btn.click()
            print("   ✅ Clicked submit")
        except Exception:
            try:
                btn = driver.find_element(By.CSS_SELECTOR, "form button")
                btn.click()
                print("   ✅ Clicked form button")
            except Exception as e:
                print(f"   ❌ Could not click button: {e}")

        time.sleep(2)
        dump_page(driver, "4_after_click_2s")

        # ── STAGE 5: 5 seconds after submit ─────────────────────────────────
        print("\n📌 STAGE 5: 5 seconds after submit")
        time.sleep(3)
        dump_page(driver, "5_after_click_5s")

        # ── STAGE 6: 10 seconds after submit ────────────────────────────────
        print("\n📌 STAGE 6: 10 seconds after submit")
        time.sleep(5)
        dump_page(driver, "6_after_click_10s")

        # ── STAGE 7: 15 seconds after submit ────────────────────────────────
        print("\n📌 STAGE 7: 15 seconds after submit")
        time.sleep(5)
        dump_page(driver, "7_after_click_15s")

        print("\n✅ Analysis complete. Check the HTML files to see exactly what PDKI returns at each stage.")
        print(f"   Files saved in: {PDKI_DIR}")

    except Exception as e:
        print(f"❌ Fatal error: {e}")
        dump_page(driver, "fatal_error")

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
