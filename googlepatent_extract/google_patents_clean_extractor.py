#!/usr/bin/env python3
"""
Google Patents Clean Extractor

Structure-based extraction following systematic web analysis.
No hardcoded names, no complex fallbacks, no duplicates.

Based on HTML structure analysis:
- Abstract: Always available with .abstract selector
- Inventors: "Inventor" dt followed by multiple dd elements
- Assignees: "Current Assignee" dt followed by single dd element
- Claims: Available with .claims selector or null if missing
"""

import sys
import time
import json
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException


def setup_chrome_driver():
    """Set up Chrome driver with stealth options"""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    # Anti-detection features
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    service = Service('/usr/local/bin/chromedriver')
    driver = webdriver.Chrome(service=service, options=chrome_options)

    # Hide webdriver property
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    return driver


def extract_abstract(driver):
    """Extract patent abstract - always available with .abstract selector"""
    try:
        abstract_element = driver.find_element(By.CSS_SELECTOR, ".abstract")
        text = abstract_element.text.strip()
        if text:
            print(f"✓ Abstract extracted: {len(text)} characters")
            return text
        else:
            print("⚠ Abstract element found but empty")
            return ""
    except NoSuchElementException:
        print("✗ Abstract not found")
        return ""
    except Exception as e:
        print(f"✗ Abstract extraction error: {e}")
        return ""


def extract_inventors(driver):
    """Extract inventors using dt/dd structure analysis"""
    try:
        # Look for "Inventor" dt element
        inventor_dt = driver.find_elements(By.XPATH, "//dt[contains(text(), 'Inventor')]")

        if not inventor_dt:
            print("✗ No Inventor section found")
            return []

        # Get all following sibling elements until next dt
        dt = inventor_dt[0]  # Use first Inventor dt found
        inventors = []

        # Get all following siblings
        all_siblings = dt.find_elements(By.XPATH, "following-sibling::*")

        for sibling in all_siblings:
            # Stop when we reach the next dt (different section)
            if sibling.tag_name == 'dt':
                break

            # Process dd elements (each contains one inventor)
            if sibling.tag_name == 'dd':
                inventor_name = sibling.text.strip()
                if inventor_name and len(inventor_name) > 1:
                    inventors.append(inventor_name)

        if inventors:
            print(f"✓ Inventors extracted: {len(inventors)} found")
            for i, name in enumerate(inventors):
                print(f"   [{i+1}] {name}")
            return inventors
        else:
            print("⚠ Inventor section found but no names extracted")
            return []

    except Exception as e:
        print(f"✗ Inventor extraction error: {e}")
        return []


def extract_assignees(driver):
    """Extract assignees using dt/dd structure analysis"""
    try:
        # Look for "Current Assignee" or "Assignee" - check span inside dt first
        assignee_patterns = [
            "//dt//span[contains(text(), 'Current Assignee')]",  # Target span inside dt
            "//dt[contains(text(), 'Current Assignee')]",       # Fallback to dt
            "//dt//span[contains(text(), 'Assignee')]",         # Span with Assignee
            "//dt[contains(text(), 'Assignee')]"                # Fallback
        ]

        for pattern in assignee_patterns:
            assignee_elements = driver.find_elements(By.XPATH, pattern)

            if assignee_elements:
                try:
                    # Get the dt element (either the element itself or its parent)
                    element = assignee_elements[0]
                    if element.tag_name == 'span':
                        # If we found a span, get its parent dt
                        dt = element.find_element(By.XPATH, "..")
                    else:
                        dt = element

                    # Get the first following dd element
                    dd = dt.find_element(By.XPATH, "following-sibling::dd[1]")
                    assignee_name = dd.text.strip()

                    if assignee_name and len(assignee_name) > 1:
                        print(f"✓ Assignee extracted: {assignee_name}")
                        return [assignee_name]  # Return as list for consistency
                    else:
                        print("⚠ Assignee section found but empty")
                        return []

                except NoSuchElementException:
                    print("⚠ Assignee element found but no following dd")
                    continue

        print("✗ No Assignee section found")
        return []

    except Exception as e:
        print(f"✗ Assignee extraction error: {e}")
        return []


def extract_claims(driver):
    """Extract patent claims - available with .claims selector or null if missing"""
    try:
        claims_element = driver.find_element(By.CSS_SELECTOR, ".claims")
        text = claims_element.text.strip()

        if text:
            print(f"✓ Claims extracted: {len(text)} characters")

            # Try to parse individual claims by number
            import re
            claim_matches = re.split(r'\n\s*(\d+\.\s)', text)

            if len(claim_matches) > 1:
                # Successfully split into numbered claims
                claims_list = []
                for i in range(1, len(claim_matches), 2):
                    if i + 1 < len(claim_matches):
                        claim_num = claim_matches[i].strip()
                        claim_text = claim_matches[i + 1].strip()
                        claims_list.append(f"{claim_num}{claim_text}")

                if claims_list:
                    print(f"   Parsed into {len(claims_list)} individual claims")
                    return claims_list

            # Fallback: return full text as single claim
            print("   Returned as single text block")
            return [text]
        else:
            print("⚠ Claims element found but empty")
            return None

    except NoSuchElementException:
        print("✗ Claims not found")
        return None
    except Exception as e:
        print(f"✗ Claims extraction error: {e}")
        return None


def extract_patent_title(driver):
    """Extract patent title for verification"""
    try:
        # Look for h1 elements, prioritizing ones with patent-result class
        title_selectors = [
            "h1.patent-result",  # Most specific
            "h1[itemprop='title']",
            ".patent-title",
            "h1"  # General fallback
        ]

        for selector in title_selectors:
            try:
                title_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for title_element in title_elements:
                    title = title_element.text.strip()
                    # Filter out generic page titles, but keep patent-specific titles
                    if title and title.lower() not in ["patents", ""]:
                        # Additional check: if it's just "Patents" but found via h1, skip it
                        if title == "Patents" and selector == "h1":
                            continue
                        print(f"✓ Title extracted: {title[:80]}{'...' if len(title) > 80 else ''}")
                        return title
            except NoSuchElementException:
                continue

        print("⚠ No patent title found")
        return ""
    except Exception as e:
        print(f"✗ Title extraction error: {e}")
        return ""


def extract_patent_data(driver, url):
    """Main extraction function using structure-based approach"""
    try:
        print(f"Loading URL: {url}")
        driver.get(url)

        # Wait for page to load
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(3)  # Allow dynamic content to load

        print("\n--- Extraction Results ---")

        # Extract all fields using structure-based approach
        patent_data = {
            "url": url,
            "extraction_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "title": extract_patent_title(driver),
            "abstract": extract_abstract(driver),
            "inventors": extract_inventors(driver),
            "assignees": extract_assignees(driver),
            "claims": extract_claims(driver),
            "error": None
        }

        return patent_data

    except TimeoutException:
        error_msg = "Page load timeout"
        print(f"Error: {error_msg}")
        return {"url": url, "error": error_msg}
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        print(f"Error: {error_msg}")
        return {"url": url, "error": error_msg}


def print_extraction_summary(result):
    """Print a clean summary of extraction results"""
    print("\n" + "="*50)
    print("EXTRACTION SUMMARY")
    print("="*50)

    if result.get("error"):
        print(f"❌ Error: {result['error']}")
        return

    print(f"🔗 URL: {result['url']}")

    # Title
    if result.get("title"):
        print(f"📄 Title: {result['title']}")

    # Abstract
    if result.get("abstract"):
        print(f"📝 Abstract: ✓ ({len(result['abstract'])} chars)")
        print(f"   Preview: {result['abstract'][:100]}...")
    else:
        print("📝 Abstract: ✗")

    # Inventors
    inventors = result.get("inventors", [])
    if inventors:
        print(f"👥 Inventors: ✓ ({len(inventors)} found)")
        for inventor in inventors:
            print(f"   • {inventor}")
    else:
        print("👥 Inventors: ✗")

    # Assignees
    assignees = result.get("assignees", [])
    if assignees:
        print(f"🏢 Assignees: ✓ ({len(assignees)} found)")
        for assignee in assignees:
            print(f"   • {assignee}")
    else:
        print("🏢 Assignees: ✗")

    # Claims
    claims = result.get("claims")
    if claims:
        if isinstance(claims, list):
            print(f"⚖️  Claims: ✓ ({len(claims)} claims)")
        else:
            print("⚖️  Claims: ✓ (single block)")
    else:
        print("⚖️  Claims: ✗")


def main():
    """Main function to test clean patent extraction"""
    # Default test cases
    test_urls = [
        "https://patents.google.com/patent/US20090175859A1",  # Complete patent
        "https://patents.google.com/patent/LU92099I2/en",     # Minimal patent
        "https://patents.google.com/patent/CN104689302A/en"   # Chinese patent
    ]

    # Allow custom URL from command line
    if len(sys.argv) > 1:
        test_urls = [sys.argv[1]]

    print("GOOGLE PATENTS CLEAN EXTRACTOR")
    print("Structure-based extraction with no hardcoded patterns")
    print()

    driver = None
    try:
        driver = setup_chrome_driver()

        for i, url in enumerate(test_urls, 1):
            print(f"\n{'#'*60}")
            print(f"TEST {i}: EXTRACTING PATENT DATA")
            print(f"{'#'*60}")

            result = extract_patent_data(driver, url)

            # Save results to JSON file (auto-detect googlepatent_extract directory)
            filename = f"clean_extraction_{i}.json"
            output_dir = Path(__file__).parent
            output_file = output_dir / filename
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)

            print(f"\n💾 Results saved to: {filename}")

            # Print summary
            print_extraction_summary(result)

    except Exception as e:
        print(f"Failed to initialize scraper: {e}")

    finally:
        if driver:
            driver.quit()


if __name__ == "__main__":
    main()