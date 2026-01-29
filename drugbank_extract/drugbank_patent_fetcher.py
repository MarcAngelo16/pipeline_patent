#!/usr/bin/env python3
"""
DrugBank Patent Fetcher

Fetches patent information from DrugBank using DrugBank IDs.
Handles Cloudflare protection using Selenium stealth mode.

Usage:
    from drugbank_patent_fetcher import DrugBankPatentFetcher

    fetcher = DrugBankPatentFetcher(verbose=True, save_screenshot=True)
    result = fetcher.fetch_patents_by_id("DB05541")
    fetcher.close()

Command line usage:
    python drugbank_patent_fetcher.py DB05541
    python drugbank_patent_fetcher.py DB05541 --screenshot
"""

import time
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup


class DrugBankPatentFetcher:
    """Fetches patent information from DrugBank using DrugBank IDs"""

    def __init__(self, headless=True, verbose=False, save_screenshot=False):
        """
        Initialize the DrugBank patent fetcher

        Args:
            headless: Run browser in headless mode (default: True)
            verbose: Print detailed logs (default: False)
            save_screenshot: Save screenshot of drug page (default: False)
        """
        self.base_url = "https://go.drugbank.com"
        self.driver = None
        self.headless = headless
        self.verbose = verbose
        self.save_screenshot = save_screenshot

    def log(self, message):
        """Print log messages if verbose mode is enabled"""
        if self.verbose:
            print(message)

    def setup_stealth_driver(self):
        """Set up Chrome driver with stealth mode to bypass Cloudflare"""
        chrome_options = Options()

        if self.headless:
            chrome_options.add_argument("--headless")

        # Basic Chrome options
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")

        # Stealth mode - Anti-bot detection
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        # User agent to appear as regular browser
        chrome_options.add_argument(
            "user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        service = Service('/usr/local/bin/chromedriver')
        self.driver = webdriver.Chrome(service=service, options=chrome_options)

        # Additional stealth scripts
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        self.log("Chrome driver initialized with stealth mode")

    def extract_drug_name(self, soup: BeautifulSoup, drugbank_id: str) -> str:
        """
        Extract the generic drug name from DrugBank page

        Args:
            soup: BeautifulSoup object of the page
            drugbank_id: DrugBank ID (fallback if name not found)

        Returns:
            Generic drug name (e.g., "Brivaracetam") or drugbank_id if not found
        """
        try:
            # Strategy 1: Look for <h1> with class "title"
            h1_title = soup.find('h1', class_='title')
            if h1_title:
                # Get text and clean it (remove drugbank ID if present)
                name = h1_title.get_text(strip=True)
                # Remove DrugBank ID from name if it's there (e.g., "Brivaracetam DB05541")
                name = name.split(drugbank_id)[0].strip()
                if name:
                    self.log(f"   Drug name found (h1.title): {name}")
                    return name

            # Strategy 2: Look for any <h1> tag at the top
            h1_tag = soup.find('h1')
            if h1_tag:
                name = h1_tag.get_text(strip=True)
                # Clean up: remove DrugBank ID and extra text
                name = name.split(drugbank_id)[0].strip()
                # Remove parentheses content like "(approved)"
                if '(' in name:
                    name = name.split('(')[0].strip()
                if name:
                    self.log(f"   Drug name found (h1): {name}")
                    return name

            # Strategy 3: Look for meta tags with drug name
            meta_title = soup.find('meta', property='og:title')
            if meta_title and meta_title.get('content'):
                name = meta_title['content']
                name = name.split(drugbank_id)[0].strip()
                if name:
                    self.log(f"   Drug name found (meta): {name}")
                    return name

            # Strategy 4: Look for title tag
            title_tag = soup.find('title')
            if title_tag:
                # Title usually like "Brivaracetam | DrugBank Online"
                name = title_tag.get_text(strip=True)
                if '|' in name:
                    name = name.split('|')[0].strip()
                if name and name.lower() != 'drugbank online':
                    self.log(f"   Drug name found (title): {name}")
                    return name

            self.log(f"   [WARNING] Could not extract drug name, using DrugBank ID: {drugbank_id}")
            return drugbank_id

        except Exception as e:
            self.log(f"   [WARNING] Error extracting drug name: {e}")
            return drugbank_id

    def _extract_patents_from_soup(self, soup: BeautifulSoup, drugbank_id: str, drug_url: str) -> List[Dict]:
        """
        Internal method: Extract patent information from parsed BeautifulSoup object

        Args:
            soup: BeautifulSoup object of the drug page
            drugbank_id: DrugBank ID
            drug_url: URL of the drug page

        Returns:
            List of patent dictionaries
        """
        try:
            # Save screenshot if enabled
            if self.save_screenshot:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                screenshot_path = f"/app/patent_pipeline/drugbank_extract/drugbank_{drugbank_id}_{timestamp}.png"
                self.driver.save_screenshot(screenshot_path)
                self.log(f"   Screenshot saved: {screenshot_path}")

            # Find the patents table
            patents_table = soup.find('table', {'id': 'patents'})

            if not patents_table:
                self.log("   [WARNING] No patents table found on page")
                return []

            # Extract patent rows
            patents = []
            tbody = patents_table.find('tbody')

            if not tbody:
                self.log("   [WARNING] Patents table has no body")
                return []

            rows = tbody.find_all('tr')
            self.log(f"   Found {len(rows)} patent(s)")

            for row in rows:
                cols = row.find_all('td')

                if len(cols) < 5:
                    continue

                # Extract patent number and Google Patents link
                patent_link = cols[0].find('a')
                if patent_link:
                    patent_id = patent_link.text.strip()
                    google_patent_url = patent_link.get('href', '')
                else:
                    patent_id = cols[0].text.strip()
                    google_patent_url = ''

                # Extract other fields
                pediatric_extension = cols[1].text.strip()
                approved_date = cols[2].text.strip()
                expires_date = cols[3].text.strip()

                # Extract country code (hidden in span)
                country_span = cols[4].find('span', {'hidden': 'hidden'})
                country = country_span.text.strip() if country_span else ''

                patent_data = {
                    'patent_id': patent_id,
                    'google_patent_url': google_patent_url,
                    'pediatric_extension': pediatric_extension,
                    'approved_date': approved_date,
                    'expires_date': expires_date,
                    'country': country,
                    'source': 'DrugBank',
                    'drugbank_id': drugbank_id,
                    'drugbank_url': drug_url
                }

                patents.append(patent_data)
                self.log(f"   [{patent_id}] {country} - Approved: {approved_date}, Expires: {expires_date}")

            return patents

        except Exception as e:
            self.log(f"   [ERROR] Error extracting patents: {e}")
            import traceback
            traceback.print_exc()
            return []

    def extract_patents_from_page(self, drugbank_id: str) -> List[Dict]:
        """
        Extract patent information from a DrugBank drug page
        (Legacy method - kept for backward compatibility)

        Args:
            drugbank_id: DrugBank ID (e.g., "DB05541")

        Returns:
            List of patent dictionaries with fields:
            - patent_id: Patent number (e.g., "US6911461")
            - google_patent_url: Link to Google Patents
            - pediatric_extension: Yes/No
            - approved_date: Approval date
            - expires_date: Expiration date
            - country: Country/region code
            - source: "DrugBank"
            - drugbank_id: DrugBank ID
            - drugbank_url: URL to drug page
        """
        self.log(f"\nExtracting patents for DrugBank ID: {drugbank_id}")

        drug_url = f"{self.base_url}/drugs/{drugbank_id}"

        try:
            # Navigate to drug page
            self.driver.get(drug_url)
            self.log(f"   Loaded: {drug_url}")

            # Wait for page to load
            time.sleep(5)

            # Get page source and parse with BeautifulSoup
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')

            # Check if Cloudflare blocked us
            if "Just a moment" in page_source or "Checking your browser" in page_source:
                self.log("   [WARNING] Cloudflare challenge detected, waiting longer...")
                time.sleep(10)
                page_source = self.driver.page_source
                soup = BeautifulSoup(page_source, 'html.parser')

            # Use the internal method to extract patents
            return self._extract_patents_from_soup(soup, drugbank_id, drug_url)

        except Exception as e:
            self.log(f"   [ERROR] Error extracting patents: {e}")
            import traceback
            traceback.print_exc()
            return []

    def fetch_patents_by_id(self, drugbank_id: str) -> Dict:
        """
        Fetch patents for a drug by DrugBank ID

        Args:
            drugbank_id: DrugBank ID (e.g., "DB05541")

        Returns:
            Dictionary with:
            - drugbank_id: DrugBank ID
            - drug_name: Generic drug name (e.g., "Brivaracetam")
            - patents: List of patent data
            - total_patents: Count of patents
            - timestamp: Extraction timestamp
            - error: Error message if failed (None if successful)
        """
        self.log(f"\n{'='*60}")
        self.log(f"DRUGBANK PATENT FETCHER")
        self.log(f"DrugBank ID: {drugbank_id}")
        self.log(f"{'='*60}")

        try:
            # Setup driver
            if not self.driver:
                self.setup_stealth_driver()

            # Navigate to drug page and get page source
            drug_url = f"{self.base_url}/drugs/{drugbank_id}"
            self.driver.get(drug_url)
            self.log(f"   Loaded: {drug_url}")

            # Wait for page to load
            time.sleep(5)

            # Get page source and parse with BeautifulSoup
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')

            # Check if Cloudflare blocked us
            if "Just a moment" in page_source or "Checking your browser" in page_source:
                self.log("   [WARNING] Cloudflare challenge detected, waiting longer...")
                time.sleep(10)
                page_source = self.driver.page_source
                soup = BeautifulSoup(page_source, 'html.parser')

            # Extract drug name from the page
            drug_name = self.extract_drug_name(soup, drugbank_id)

            # Extract patents from drug page (we'll need to refactor this slightly)
            patents = self._extract_patents_from_soup(soup, drugbank_id, drug_url)

            result = {
                'drugbank_id': drugbank_id,
                'drug_name': drug_name,
                'patents': patents,
                'total_patents': len(patents),
                'timestamp': datetime.now().isoformat(),
                'error': None
            }

            self.log(f"\n{'='*60}")
            self.log(f"EXTRACTION COMPLETE")
            self.log(f"   DrugBank ID: {drugbank_id}")
            self.log(f"   Drug Name: {drug_name}")
            self.log(f"   Patents Found: {len(patents)}")
            self.log(f"{'='*60}\n")

            return result

        except Exception as e:
            self.log(f"\n[ERROR] Fatal error: {e}")
            import traceback
            traceback.print_exc()

            return {
                'drugbank_id': drugbank_id,
                'drug_name': drugbank_id,  # Fallback to ID
                'patents': [],
                'total_patents': 0,
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }

    def close(self):
        """Close the browser driver"""
        if self.driver:
            self.driver.quit()
            self.log("Browser closed")


def main():
    """Example usage"""
    import sys

    # Parse command line arguments
    drugbank_id = "DB05541"  # default
    save_screenshot = False

    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--screenshot":
            save_screenshot = True
        elif not arg.startswith("--"):
            drugbank_id = arg

    # Create fetcher with verbose output
    fetcher = DrugBankPatentFetcher(headless=True, verbose=True, save_screenshot=save_screenshot)

    try:
        # Fetch patents
        result = fetcher.fetch_patents_by_id(drugbank_id)

        # Save results to JSON
        output_dir = Path(__file__).parent
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"drugbank_patents_{drugbank_id}_{timestamp}.json"

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2)

        print(f"\nResults saved to: {output_file}")

        # Print summary
        print(f"\nSUMMARY:")
        print(f"   DrugBank ID: {result['drugbank_id']}")
        print(f"   Total Patents: {result['total_patents']}")

        if result['error']:
            print(f"   Error: {result['error']}")
        elif result['patents']:
            print(f"\n   Patents:")
            for i, patent in enumerate(result['patents'], 1):
                print(f"   {i}. {patent['patent_id']} ({patent['country']})")
                print(f"      Approved: {patent['approved_date']} | Expires: {patent['expires_date']}")
                if patent['google_patent_url']:
                    print(f"      URL: {patent['google_patent_url']}")
        else:
            print("   No patents found for this drug")

    finally:
        fetcher.close()


if __name__ == "__main__":
    main()
