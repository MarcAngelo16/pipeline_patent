#!/usr/bin/env python3
"""
Google Patents Web Structure Analyzer

Systematically analyze the HTML structure of different patent pages
to understand how data is organized before writing extraction logic.
"""

import sys
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By


def setup_chrome_driver():
    """Set up Chrome driver"""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    service = Service('/usr/local/bin/chromedriver')
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver


def analyze_patent_structure(driver, url, patent_name):
    """Analyze the structure of a patent page"""
    print(f"\n{'='*60}")
    print(f"ANALYZING: {patent_name}")
    print(f"URL: {url}")
    print(f"{'='*60}")

    driver.get(url)
    time.sleep(3)

    # 1. Check overall page structure
    print("\n1. MAIN SECTIONS:")
    main_sections = [
        "header", "main", "article", "section",
        ".patent-result", ".content", "#content"
    ]

    for selector in main_sections:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                print(f"   ✓ {selector}: {len(elements)} found")
        except:
            pass

    # 2. Look for definition lists (dt/dd pairs) - common pattern
    print("\n2. DEFINITION LISTS (dt/dd patterns):")
    dt_elements = driver.find_elements(By.CSS_SELECTOR, "dt")
    print(f"   Found {len(dt_elements)} dt elements:")

    for i, dt in enumerate(dt_elements[:10]):  # Show first 10
        try:
            dt_text = dt.text.strip()
            # Get corresponding dd
            try:
                dd = dt.find_element(By.XPATH, "following-sibling::dd[1]")
                dd_text = dd.text.strip()[:80]  # First 80 chars
                print(f"   [{i}] DT: '{dt_text}' -> DD: '{dd_text}...'")
            except:
                print(f"   [{i}] DT: '{dt_text}' -> DD: [not found]")
        except:
            pass

    # 3. Look for specific metadata we care about
    print("\n3. TARGET METADATA AVAILABILITY:")

    # Abstract
    abstract_indicators = [
        "#abstract", ".abstract", "[data-section='abstract']"
    ]
    abstract_found = False
    for selector in abstract_indicators:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements and elements[0].text.strip():
                print(f"   ✓ ABSTRACT: Found with {selector}")
                print(f"     Preview: {elements[0].text[:100]}...")
                abstract_found = True
                break
        except:
            pass
    if not abstract_found:
        print("   ✗ ABSTRACT: Not found")

    # Inventors
    inventor_found = False
    inventor_dt = driver.find_elements(By.XPATH, "//dt[contains(text(), 'Inventor')]")
    if inventor_dt:
        print(f"   ✓ INVENTOR SECTION: Found {len(inventor_dt)} dt elements")
        for dt in inventor_dt[:1]:  # Check first one
            siblings = dt.find_elements(By.XPATH, "following-sibling::dd")
            print(f"     Has {len(siblings)} following dd elements:")
            for j, dd in enumerate(siblings[:3]):  # Show first 3
                print(f"       DD[{j}]: '{dd.text.strip()}'")
        inventor_found = True
    if not inventor_found:
        print("   ✗ INVENTOR SECTION: Not found")

    # Assignees
    assignee_found = False
    assignee_patterns = [
        "//dt[contains(text(), 'Current Assignee')]",
        "//dt[contains(text(), 'Assignee')]"
    ]
    for pattern in assignee_patterns:
        assignee_dt = driver.find_elements(By.XPATH, pattern)
        if assignee_dt:
            print(f"   ✓ ASSIGNEE SECTION: Found with '{pattern}'")
            for dt in assignee_dt[:1]:
                try:
                    dd = dt.find_element(By.XPATH, "following-sibling::dd[1]")
                    print(f"     Content: '{dd.text.strip()}'")
                except:
                    print("     Content: [no following dd]")
            assignee_found = True
            break
    if not assignee_found:
        print("   ✗ ASSIGNEE SECTION: Not found")

    # Claims
    claims_indicators = [
        "#claims", ".claims", "[data-section='claims']"
    ]
    claims_found = False
    for selector in claims_indicators:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements and elements[0].text.strip():
                text = elements[0].text.strip()
                print(f"   ✓ CLAIMS: Found with {selector}")
                print(f"     Length: {len(text)} characters")
                print(f"     Preview: {text[:100]}...")
                claims_found = True
                break
        except:
            pass
    if not claims_found:
        print("   ✗ CLAIMS: Not found")

    # 4. Check for common containers
    print("\n4. COMMON CONTAINER PATTERNS:")
    container_patterns = [
        ".metadata", ".patent-metadata", ".patent-info",
        ".application-timeline", ".style-scope.patent-result"
    ]

    for pattern in container_patterns:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, pattern)
            if elements:
                print(f"   ✓ {pattern}: {len(elements)} found")
                if elements[0].text.strip():
                    print(f"     Sample content: {elements[0].text[:150]}...")
        except:
            pass


def main():
    """Analyze multiple patent pages to understand structure patterns"""

    # Test different types of patents
    test_patents = [
        {
            "name": "US Patent (Complete)",
            "url": "https://patents.google.com/patent/US20090175859A1"
        },
        {
            "name": "Luxembourg Patent (Incomplete)",
            "url": "https://patents.google.com/patent/LU92099I2/en"
        },
        {
            "name": "Chinese Patent (Test)",
            "url": "https://patents.google.com/patent/CN104689302A/en"
        }
    ]

    # Allow custom URL from command line
    if len(sys.argv) > 1:
        test_patents = [{
            "name": "Custom Patent",
            "url": sys.argv[1]
        }]

    driver = setup_chrome_driver()

    try:
        print("GOOGLE PATENTS WEB STRUCTURE ANALYSIS")
        print("Goal: Understand HTML structure before writing extraction logic")

        for patent in test_patents:
            analyze_patent_structure(driver, patent["url"], patent["name"])

        print(f"\n{'='*60}")
        print("ANALYSIS COMPLETE")
        print("Next: Design extraction logic based on observed patterns")
        print(f"{'='*60}")

    except Exception as e:
        print(f"Analysis failed: {e}")

    finally:
        driver.quit()


if __name__ == "__main__":
    main()