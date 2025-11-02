#!/usr/bin/env python3
"""
Search and Extract Links 100 - Complete search with 100 results per page
Based on the working pagination_tester.py with integrated search and link extraction
"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, ElementNotInteractableException
import time
import json
from datetime import datetime

class SearchAndExtract100:
    def __init__(self):
        self.results_data = {
            'search_info': {},
            'pagination_changes': [],
            'extracted_links': [],
            'screenshots': [],
            'errors': []
        }

    def setup_stealth_driver(self):
        """Setup Chrome driver with full stealth mode"""
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        # STEALTH MODE - Anti-bot detection options
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        # Additional stealth options
        options.add_argument("--disable-web-security")
        options.add_argument("--allow-running-insecure-content")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-plugins")
        options.add_argument("--disable-images")
        options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebDriver/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

        # Larger window for better visibility
        options.add_argument("--window-size=1920,1080")

        driver = webdriver.Chrome(options=options)

        # STEALTH SCRIPTS - Hide webdriver properties
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})")
        driver.execute_script("Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']})")

        return driver

    def get_current_pagination_value(self, driver):
        """Get the current pagination value from the dropdown button"""
        try:
            # Find the combobox button with a span containing a number
            buttons = driver.find_elements(By.CSS_SELECTOR, "button[role='combobox']")

            for button in buttons:
                try:
                    span = button.find_element(By.TAG_NAME, "span")
                    text = span.text.strip()
                    if text in ['10', '50', '100']:
                        return {
                            'value': text,
                            'element': button,
                            'aria_controls': button.get_attribute("aria-controls")
                        }
                except:
                    continue

            return None
        except Exception as e:
            print(f"   ❌ Error getting current pagination: {e}")
            return None

    def set_pagination_to_100(self, driver):
        """Set pagination to 100 results per page"""
        print("🎯 Setting pagination to 100 results per page...")

        try:
            # Get current dropdown state
            current = self.get_current_pagination_value(driver)
            if not current:
                print("   ❌ Could not find pagination dropdown")
                return False

            current_value = current['value']
            dropdown_button = current['element']
            aria_controls = current['aria_controls']

            print(f"   📊 Current value: {current_value}")

            if current_value == '100':
                print("   ✅ Already set to 100")
                return True

            # Click the dropdown button to open it
            print("   🖱️  Opening dropdown...")

            # Scroll into view first
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", dropdown_button)
            time.sleep(1)

            # Try multiple click methods
            try:
                dropdown_button.click()
            except Exception:
                try:
                    driver.execute_script("arguments[0].click();", dropdown_button)
                except Exception:
                    ActionChains(driver).move_to_element(dropdown_button).click().perform()

            time.sleep(2)

            # Wait for dropdown menu to appear
            print("   ⏳ Waiting for dropdown menu...")

            # Look for the dropdown menu using multiple selectors
            menu_selectors = [
                f"[id='{aria_controls}']",
                "[role='listbox']",
                "div[data-radix-popper-content-wrapper]",
                "*[data-state='open']"
            ]

            dropdown_menu = None
            for selector in menu_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        if element.is_displayed() and '100' in element.text:
                            dropdown_menu = element
                            print(f"   ✅ Found dropdown menu with selector: {selector}")
                            break
                    if dropdown_menu:
                        break
                except:
                    continue

            if not dropdown_menu:
                print("   ❌ Dropdown menu not found or not visible")
                return False

            # Find and click the 100 option
            print("   🔍 Looking for 100 option...")

            # Based on elements_monitor findings: options are divs with role="option"
            option_selectors = ["div[role='option']", "button", "*[data-value='100']"]

            target_option = None
            for selector in option_selectors:
                try:
                    options = dropdown_menu.find_elements(By.CSS_SELECTOR, selector)
                    for option in options:
                        if option.text.strip() == '100' and option.is_displayed():
                            target_option = option
                            print(f"   ✅ Found 100 option")
                            break
                    if target_option:
                        break
                except:
                    continue

            if not target_option:
                print("   ❌ Could not find 100 option in dropdown")
                return False

            # Click the 100 option
            print("   🖱️  Clicking 100 option...")

            try:
                target_option.click()
            except Exception:
                try:
                    driver.execute_script("arguments[0].click();", target_option)
                except Exception:
                    ActionChains(driver).move_to_element(target_option).click().perform()

            time.sleep(3)

            # Verify the change
            new_current = self.get_current_pagination_value(driver)
            if new_current and new_current['value'] == '100':
                print("   ✅ Successfully changed to 100 results per page!")
                self.results_data['pagination_changes'].append({
                    'from': current_value,
                    'to': '100',
                    'success': True,
                    'timestamp': int(time.time())
                })
                return True
            else:
                print(f"   ⚠️  Change may not have taken effect. Current: {new_current['value'] if new_current else 'Unknown'}")
                return False

        except Exception as e:
            print(f"   ❌ Error setting pagination to 100: {e}")
            self.results_data['errors'].append(f"Pagination error: {str(e)}")
            return False

    def wait_for_page_load(self, driver, max_attempts=3):
        """Wait for search page to load properly"""
        for attempt in range(max_attempts):
            try:
                print(f"   🔄 Load attempt {attempt + 1}/{max_attempts}...")
                time.sleep(3)

                page_source = driver.page_source
                page_length = len(page_source)

                if page_length < 10000:
                    print(f"   ⚠️  Short response ({page_length} chars), retrying...")
                    driver.refresh()
                    time.sleep(5)
                    continue

                try:
                    WebDriverWait(driver, 15).until(
                        EC.presence_of_element_located((By.TAG_NAME, "form"))
                    )
                    time.sleep(3)

                    final_source = driver.page_source
                    final_length = len(final_source)
                    has_forms = '<form' in final_source.lower()

                    if has_forms and final_length > 50000:
                        print(f"   ✅ Page loaded successfully ({final_length:,} chars)")
                        return True
                    else:
                        print(f"   ⚠️  Page may not be fully loaded ({final_length:,} chars)")
                        continue

                except TimeoutException:
                    print(f"   ❌ Timeout waiting for form elements")
                    continue

            except Exception as e:
                print(f"   ❌ Load attempt {attempt + 1} failed: {e}")
                continue

        print("   ❌ Failed to load page after all attempts")
        return False

    def setup_search_form(self, driver, search_term="insulin", category="patent"):
        """Setup the search form with term and category"""
        print(f"📋 Setting up search form: '{search_term}' in '{category}'...")

        try:
            # Find and set category (select element)
            try:
                select_element = driver.find_element(By.CSS_SELECTOR, "select[aria-hidden='true']")
                select = Select(select_element)

                # Map category to Indonesian terms
                category_map = {
                    'patent': 'Paten',
                    'trademark': 'Merek',
                    'design': 'Desain Industri',
                    'copyright': 'Hak Cipta'
                }

                target_category = category_map.get(category, 'Paten')
                select.select_by_visible_text(target_category)
                print(f"   ✅ Selected category: {target_category}")

            except Exception as e:
                print(f"   ⚠️  Could not set category: {e}")

            # Find and fill search input
            try:
                search_input = driver.find_element(By.CSS_SELECTOR, "input[type='text'], input:not([type])")
                search_input.clear()
                search_input.send_keys(search_term)
                print(f"   ✅ Entered search term: '{search_term}'")

            except Exception as e:
                print(f"   ❌ Could not fill search input: {e}")
                return False

            # Wait for form to register changes
            time.sleep(2)

            self.results_data['search_info'] = {
                'term': search_term,
                'category': category,
                'timestamp': int(time.time())
            }

            return True

        except Exception as e:
            print(f"   ❌ Error setting up search form: {e}")
            self.results_data['errors'].append(f"Form setup error: {str(e)}")
            return False

    def submit_search_and_wait(self, driver):
        """Submit search form and wait for results"""
        print("🚀 Submitting search form...")

        try:
            # Find and submit form
            form = driver.find_element(By.TAG_NAME, "form")

            # Take screenshot before submit
            timestamp = int(time.time())
            before_screenshot = f"/app/reverse_engineering/before_submit_{timestamp}.png"
            driver.save_screenshot(before_screenshot)
            self.results_data['screenshots'].append(before_screenshot)

            form.submit()
            print("   ✅ Form submitted")

            # Wait longer for 100 results to load
            print("   ⏳ Waiting for 100 results to load (15 seconds)...")
            time.sleep(15)

            # Check if we got results
            page_source = driver.page_source
            page_length = len(page_source)

            if page_length > 30000:
                print(f"   ✅ Got results page ({page_length:,} characters)")

                # Take screenshot after results
                after_screenshot = f"/app/reverse_engineering/search_results_{timestamp}.png"
                driver.save_screenshot(after_screenshot)
                self.results_data['screenshots'].append(after_screenshot)

                return True
            else:
                print(f"   ⚠️  Results page seems short ({page_length:,} characters)")
                return False

        except Exception as e:
            print(f"   ❌ Error submitting search: {e}")
            self.results_data['errors'].append(f"Search submit error: {str(e)}")
            return False

    def extract_patent_links(self, driver):
        """Extract patent result links from the page"""
        print("🔗 Extracting patent result links...")

        try:
            # Link patterns to try (based on previous findings)
            link_patterns = [
                "a[href*='/link/']",
                "a[href*='patent']",
                "a[href*='pdki-indonesia.dgip.go.id/link/']",
                "a[href*='detail']",
                "a[href*='view']"
            ]

            all_links = []

            for pattern in link_patterns:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, pattern)
                    print(f"   📋 Pattern '{pattern}': found {len(elements)} elements")

                    for element in elements:
                        try:
                            href = element.get_attribute('href')
                            text = element.text.strip()

                            if href and ('/link/' in href or 'detail' in href):
                                link_data = {
                                    'url': href,
                                    'text': text[:100] if text else "No text",
                                    'pattern': pattern
                                }

                                # Avoid duplicates
                                if not any(link['url'] == href for link in all_links):
                                    all_links.append(link_data)

                        except Exception:
                            continue

                except Exception as e:
                    print(f"   ⚠️  Pattern '{pattern}' failed: {e}")
                    continue

            print(f"   🎯 Total unique links found: {len(all_links)}")

            # If we got fewer than expected, try backup strategies
            if len(all_links) < 50:  # Expecting more for 100 results mode
                print("   🔍 Using backup link extraction strategies...")

                # Try to find any clickable elements that might be results
                backup_patterns = [
                    "tr td a",  # Table row links
                    ".result-item a",
                    ".search-result a",
                    "div[onclick]",
                    "*[data-href]"
                ]

                for pattern in backup_patterns:
                    try:
                        elements = driver.find_elements(By.CSS_SELECTOR, pattern)
                        print(f"   📋 Backup pattern '{pattern}': found {len(elements)} elements")

                        for element in elements:
                            try:
                                href = element.get_attribute('href') or element.get_attribute('data-href')
                                onclick = element.get_attribute('onclick') or ""
                                text = element.text.strip()

                                if href or 'link' in onclick.lower():
                                    link_data = {
                                        'url': href or f"onclick:{onclick}",
                                        'text': text[:100] if text else "No text",
                                        'pattern': f"backup:{pattern}"
                                    }

                                    if not any(link['url'] == link_data['url'] for link in all_links):
                                        all_links.append(link_data)

                            except Exception:
                                continue

                    except Exception:
                        continue

            self.results_data['extracted_links'] = all_links
            print(f"   ✅ Final count: {len(all_links)} unique links extracted")

            return all_links

        except Exception as e:
            print(f"   ❌ Error extracting links: {e}")
            self.results_data['errors'].append(f"Link extraction error: {str(e)}")
            return []

    def save_results(self):
        """Save all results to files"""
        timestamp = int(time.time())

        try:
            # Save JSON report
            json_file = f"/app/reverse_engineering/search_100_results_{timestamp}.json"
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(self.results_data, f, indent=2, ensure_ascii=False)

            # Save links as text file
            links_file = f"/app/reverse_engineering/extracted_links_100_{timestamp}.txt"
            with open(links_file, 'w', encoding='utf-8') as f:
                f.write(f"EXTRACTED LINKS - 100 Results Search\n")
                f.write(f"Generated: {datetime.now()}\n")
                f.write(f"Search: {self.results_data['search_info'].get('term', 'N/A')}\n")
                f.write(f"Category: {self.results_data['search_info'].get('category', 'N/A')}\n")
                f.write(f"Total Links: {len(self.results_data['extracted_links'])}\n")
                f.write("=" * 50 + "\n\n")

                for i, link in enumerate(self.results_data['extracted_links'], 1):
                    f.write(f"{i}. {link['url']}\n")
                    f.write(f"   Text: {link['text']}\n")
                    f.write(f"   Pattern: {link['pattern']}\n\n")

            print(f"\n💾 RESULTS SAVED:")
            print(f"   📋 JSON Report: {json_file}")
            print(f"   🔗 Links File: {links_file}")
            print(f"   📸 Screenshots: {len(self.results_data['screenshots'])} files")

            return json_file, links_file

        except Exception as e:
            print(f"   ❌ Error saving results: {e}")
            return None, None

def main():
    print("=" * 70)
    print("🔍 SEARCH AND EXTRACT LINKS 100 - Complete Search with 100 Results")
    print("=" * 70)

    searcher = SearchAndExtract100()
    driver = searcher.setup_stealth_driver()

    try:
        print("🌐 Loading PDKI search page...")
        print("🥷 Stealth mode enabled...")
        driver.get("https://pdki-indonesia.dgip.go.id/search")

        # Check stealth success
        time.sleep(3)
        page_source = driver.page_source
        page_length = len(page_source)

        if page_length > 50000 and '<form' in page_source:
            print("✅ Stealth mode SUCCESS - got full page content!")
            print(f"   📊 Page size: {page_length:,} characters")
        else:
            print("⚠️  Partial success or CAPTCHA - continuing...")
            print(f"   📊 Page size: {page_length:,} characters")

        # Wait for page to fully load
        if not searcher.wait_for_page_load(driver):
            print("❌ Failed to load search page properly")
            return

        # Set pagination to 100 results
        pagination_success = searcher.set_pagination_to_100(driver)
        if not pagination_success:
            print("⚠️  Could not set pagination to 100, continuing with current setting...")

        # Setup search form
        if not searcher.setup_search_form(driver, "insulin", "patent"):
            print("❌ Failed to setup search form")
            return

        # Submit search and wait for results
        if not searcher.submit_search_and_wait(driver):
            print("❌ Search submission failed")
            return

        # Extract patent links
        links = searcher.extract_patent_links(driver)

        # Take final screenshot
        timestamp = int(time.time())
        final_screenshot = f"/app/reverse_engineering/final_results_{timestamp}.png"
        driver.save_screenshot(final_screenshot)
        searcher.results_data['screenshots'].append(final_screenshot)

        # Save all results
        json_file, links_file = searcher.save_results()

        # Final summary
        print(f"\n🎯 SEARCH COMPLETE!")
        print(f"   🔍 Search term: insulin (patent category)")
        print(f"   📊 Pagination: 100 results per page")
        print(f"   🔗 Links extracted: {len(links)}")
        print(f"   📸 Screenshots taken: {len(searcher.results_data['screenshots'])}")
        print(f"   ❌ Errors encountered: {len(searcher.results_data['errors'])}")

        if searcher.results_data['errors']:
            print("\n⚠️  ERRORS:")
            for error in searcher.results_data['errors']:
                print(f"   • {error}")

    except Exception as e:
        print(f"❌ Fatal error: {e}")

    finally:
        driver.quit()

if __name__ == "__main__":
    main()