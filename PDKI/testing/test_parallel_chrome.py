#!/usr/bin/env python3
"""
Test: Can 2 Chrome instances open simultaneously and access PDKI?
Each instance gets its own copy of the working Chrome profile to preserve
cookies/session for captcha bypass.
"""

import os
import time
import shutil
import tempfile
import threading

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

PDKI_URL = "https://pdki-indonesia.dgip.go.id/search"
SOURCE_PROFILE = "/root/chrome-profile"


def setup_driver(profile_dir: str) -> uc.Chrome:
    os.environ['DISPLAY'] = ':99'
    options = uc.ChromeOptions()
    options.add_argument(f"--user-data-dir={profile_dir}")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=en-US")
    return uc.Chrome(options=options, version_main=145)


def copy_profile(dest: str):
    """Copy source profile to dest, skipping Chrome singleton/lock files."""
    ignore = shutil.ignore_patterns("SingletonCookie", "SingletonSocket", "SingletonLock")
    if os.path.exists(dest):
        shutil.rmtree(dest)
    shutil.copytree(SOURCE_PROFILE, dest, ignore=ignore)
    print(f"  [profile] Copied to {dest}")


def run_instance(instance_id: int, profile_dir: str, results: dict):
    """Open Chrome, go to PDKI, check if search inputs are visible."""
    driver = None
    try:
        print(f"[{instance_id}] Starting Chrome with profile: {profile_dir}")
        driver = setup_driver(profile_dir)

        print(f"[{instance_id}] Navigating to PDKI...")
        driver.get(PDKI_URL)

        # Wait for the advanced search input to appear (same check as production code)
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input.input-advance"))
        )
        time.sleep(2)

        page_len = len(driver.page_source)
        print(f"[{instance_id}] SUCCESS — page loaded ({page_len:,} chars)")
        results[instance_id] = {"status": "success", "page_chars": page_len}
        print(f"[{instance_id}] Waiting 10s for observation...")
        time.sleep(10)

    except TimeoutException:
        print(f"[{instance_id}] FAILED — timed out waiting for search inputs (possible captcha?)")
        results[instance_id] = {"status": "timeout"}
    except Exception as exc:
        print(f"[{instance_id}] FAILED — {exc}")
        results[instance_id] = {"status": "error", "error": str(exc)}
    finally:
        if driver:
            driver.quit()
            print(f"[{instance_id}] Chrome closed")


def main():
    num_instances = 2
    profile_dirs = [f"/tmp/chrome-profile-test-{i}" for i in range(1, num_instances + 1)]

    # Step 1: Copy profiles
    print("=== Copying Chrome profiles ===")
    for p in profile_dirs:
        copy_profile(p)

    # Step 2: Launch instances in parallel threads
    print(f"\n=== Launching {num_instances} Chrome instances in parallel ===")
    results = {}
    threads = []

    for i, profile_dir in enumerate(profile_dirs, 1):
        t = threading.Thread(target=run_instance, args=(i, profile_dir, results))
        threads.append(t)

    for t in threads:
        t.start()
        time.sleep(5)  # stagger starts to avoid chromedriver symlink race condition

    for t in threads:
        t.join()

    # Step 3: Report
    print("\n=== Results ===")
    for i in range(1, num_instances + 1):
        r = results.get(i, {"status": "unknown"})
        status = r["status"]
        if status == "success":
            print(f"  Instance {i}: OK ({r['page_chars']:,} chars)")
        elif status == "timeout":
            print(f"  Instance {i}: TIMEOUT — captcha likely triggered")
        else:
            print(f"  Instance {i}: ERROR — {r.get('error', '?')}")

    # Step 4: Cleanup temp profiles
    print("\n=== Cleaning up temp profiles ===")
    for p in profile_dirs:
        shutil.rmtree(p, ignore_errors=True)
        print(f"  Removed {p}")


if __name__ == "__main__":
    main()
