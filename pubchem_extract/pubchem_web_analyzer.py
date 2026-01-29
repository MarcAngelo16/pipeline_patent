#!/usr/bin/env python3
"""
PubChem Patent Web Structure Analyzer

Systematically analyze the HTML structure of PubChem patent pages
to understand how patent metadata is organized.

Target Keywords:
- Inventor
- Assignee
- Priority Date
- Filing Date
- Publication Date
- Patent Family
- Country

Test URL: https://pubchem.ncbi.nlm.nih.gov/patent/WO-2024184281-A1
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
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    service = Service('/usr/local/bin/chromedriver')
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver


def analyze_pubchem_patent_structure(driver, url, patent_name):
    """Analyze the structure of a PubChem patent page"""
    print(f"\n{'='*70}")
    print(f"ANALYZING: {patent_name}")
    print(f"URL: {url}")
    print(f"{'='*70}")

    driver.get(url)
    time.sleep(3)

    # 1. Check overall page structure
    print("\n1. MAIN SECTIONS:")
    main_sections = [
        "header", "main", "article", "section", "div",
        "#content", ".content", ".patent-details", ".patent-info"
    ]

    for selector in main_sections:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                print(f"   ✓ {selector}: {len(elements)} found")
        except:
            pass

    # 2. Look for target keywords in any text content
    print("\n2. TARGET KEYWORD SEARCH:")
    target_keywords = [
        "Inventor", "Assignee", "Priority Date", "Filing Date",
        "Publication Date", "Patent Family", "Country"
    ]

    for keyword in target_keywords:
        print(f"\n   🔍 SEARCHING FOR: '{keyword}'")

        # Search in any element containing the keyword
        xpath_patterns = [
            f"//*[contains(text(), '{keyword}')]",
            f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{keyword.lower()}')]"
        ]

        found_elements = []
        for pattern in xpath_patterns:
            try:
                elements = driver.find_elements(By.XPATH, pattern)
                found_elements.extend(elements)
            except:
                continue

        if found_elements:
            print(f"      ✓ Found {len(found_elements)} elements containing '{keyword}':")

            # Show unique elements (avoid duplicates)
            seen_texts = set()
            for i, elem in enumerate(found_elements[:5]):  # Limit to first 5
                try:
                    elem_text = elem.text.strip()
                    if elem_text and elem_text not in seen_texts and len(elem_text) < 300:
                        seen_texts.add(elem_text)
                        print(f"         [{len(seen_texts)}] Tag: {elem.tag_name}")
                        print(f"             Text: '{elem_text}'")
                        print(f"             Class: '{elem.get_attribute('class')}'")
                        print(f"             ID: '{elem.get_attribute('id')}'")

                        # Check if this element has a following sibling with data
                        try:
                            parent = elem.find_element(By.XPATH, "..")
                            next_sibling = parent.find_element(By.XPATH, "following-sibling::*[1]")
                            if next_sibling.text.strip():
                                print(f"             Next sibling: '{next_sibling.text.strip()[:100]}'")
                        except:
                            pass
                        print()

                except Exception as e:
                    continue
        else:
            print(f"      ✗ No elements found containing '{keyword}'")

    # 3. Look for common metadata patterns
    print("\n3. COMMON METADATA PATTERNS:")

    # Table structures
    print("\n   📊 TABLE STRUCTURES:")
    tables = driver.find_elements(By.CSS_SELECTOR, "table")
    print(f"      Found {len(tables)} tables")

    for i, table in enumerate(tables[:3]):  # Check first 3 tables
        try:
            rows = table.find_elements(By.CSS_SELECTOR, "tr")
            print(f"      Table {i+1}: {len(rows)} rows")

            # Show first few rows that might contain our keywords
            for j, row in enumerate(rows[:5]):
                row_text = row.text.strip()
                if any(keyword.lower() in row_text.lower() for keyword in target_keywords):
                    print(f"         Row {j+1}: {row_text[:150]}...")

        except Exception as e:
            continue

    # Definition lists (dt/dd pairs)
    print("\n   📝 DEFINITION LISTS:")
    dt_elements = driver.find_elements(By.CSS_SELECTOR, "dt")
    print(f"      Found {len(dt_elements)} dt elements")

    for i, dt in enumerate(dt_elements[:10]):  # Show first 10
        try:
            dt_text = dt.text.strip()
            if any(keyword.lower() in dt_text.lower() for keyword in target_keywords):
                try:
                    dd = dt.find_element(By.XPATH, "following-sibling::dd[1]")
                    dd_text = dd.text.strip()[:100]
                    print(f"      DT: '{dt_text}' -> DD: '{dd_text}...'")
                except:
                    print(f"      DT: '{dt_text}' -> DD: [not found]")
        except:
            pass

    # Form structures
    print("\n   📋 FORM STRUCTURES:")
    labels = driver.find_elements(By.CSS_SELECTOR, "label")
    print(f"      Found {len(labels)} label elements")

    for label in labels[:10]:
        try:
            label_text = label.text.strip()
            if any(keyword.lower() in label_text.lower() for keyword in target_keywords):
                print(f"      Label: '{label_text}'")
                # Try to find associated input/value
                try:
                    for_attr = label.get_attribute('for')
                    if for_attr:
                        input_elem = driver.find_element(By.ID, for_attr)
                        print(f"             Input value: '{input_elem.get_attribute('value')}'")
                except:
                    pass
        except:
            pass

    # 4. Check for specific PubChem containers
    print("\n4. PUBCHEM-SPECIFIC CONTAINERS:")
    pubchem_patterns = [
        ".patent-detail", ".patent-metadata", ".patent-info",
        "#patent-summary", ".summary", "#main-content",
        ".record-info", ".compound-info"
    ]

    for pattern in pubchem_patterns:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, pattern)
            if elements:
                print(f"   ✓ {pattern}: {len(elements)} found")

                # Check if any contain our keywords
                for elem in elements[:2]:
                    elem_text = elem.text.strip()
                    matching_keywords = [kw for kw in target_keywords if kw.lower() in elem_text.lower()]
                    if matching_keywords:
                        print(f"      Contains keywords: {matching_keywords}")
                        print(f"      Sample content: {elem_text[:200]}...")
        except:
            pass

    # 5. Look for any JSON data or structured data
    print("\n5. STRUCTURED DATA SEARCH:")

    # Check for JSON-LD or other structured data
    json_scripts = driver.find_elements(By.CSS_SELECTOR, "script[type='application/ld+json']")
    if json_scripts:
        print(f"   ✓ Found {len(json_scripts)} JSON-LD scripts")
        for i, script in enumerate(json_scripts[:2]):
            content = script.get_attribute('innerHTML')
            if content:
                print(f"      Script {i+1}: {content[:200]}...")

    # Check for data attributes
    data_elements = driver.find_elements(By.CSS_SELECTOR, "[data-*]")
    if data_elements:
        print(f"   ✓ Found {len(data_elements)} elements with data attributes")

        # Show elements with data attributes that might be relevant
        for elem in data_elements[:5]:
            attrs = driver.execute_script("""
                var items = {};
                for (index = 0; index < arguments[0].attributes.length; ++index) {
                    if (arguments[0].attributes[index].name.startsWith('data-')) {
                        items[arguments[0].attributes[index].name] = arguments[0].attributes[index].value;
                    }
                }
                return items;
            """, elem)

            if attrs:
                print(f"      Element data attributes: {attrs}")


def main():
    """Analyze PubChem patent page structure"""

    # Test URL
    test_patent = {
        "name": "WO-2024184281-A1 (Golimumab)",
        "url": "https://pubchem.ncbi.nlm.nih.gov/patent/WO-2024184281-A1"
    }

    # Allow custom URL from command line
    if len(sys.argv) > 1:
        test_patent = {
            "name": "Custom Patent",
            "url": sys.argv[1]
        }

    driver = setup_chrome_driver()

    try:
        print("PUBCHEM PATENT WEB STRUCTURE ANALYSIS")
        print("Goal: Understand HTML structure for patent metadata extraction")
        print("Target Keywords: Inventor, Assignee, Priority Date, Filing Date, Publication Date, Patent Family, Country")

        analyze_pubchem_patent_structure(driver, test_patent["url"], test_patent["name"])

        print(f"\n{'='*70}")
        print("ANALYSIS COMPLETE")
        print("Next: Design extraction logic based on observed patterns")
        print(f"{'='*70}")

    except Exception as e:
        print(f"Analysis failed: {e}")

    finally:
        driver.quit()


if __name__ == "__main__":
    main()