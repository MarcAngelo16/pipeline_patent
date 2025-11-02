#!/usr/bin/env python3
"""
PubChem Patent JSON API Extractor

Extracts patent metadata using PubChem's JSON API instead of web scraping.
Much more reliable and faster than HTML parsing.

API Pattern: https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/patent/{PATENT_ID}/JSON/

Target Fields:
- Title, Abstract, Inventor, Assignee
- Priority Date, Filing Date, Publication Date
- Country, Patent Family

Test Patents:
- WO-2024184281-A1 (complete, newer patent)
- LU-92099-I2 (complete with patent family, older patent)
"""

import sys
import time
import json
import requests
from datetime import datetime
from pathlib import Path


class PubChemPatentExtractor:
    def __init__(self):
        self.base_url = "https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/patent"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        })

    def build_api_url(self, patent_id):
        """Build PubChem JSON API URL for patent"""
        # Clean up patent ID (remove any spaces or special chars)
        clean_id = patent_id.strip()
        return f"{self.base_url}/{clean_id}/JSON/"

    def fetch_patent_json(self, patent_id):
        """Fetch patent JSON data from PubChem API"""
        try:
            url = self.build_api_url(patent_id)
            print(f"🔗 API URL: {url}")

            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            # Parse JSON response
            patent_data = response.json()
            print(f"✅ JSON fetched successfully ({len(response.text)} chars)")

            return patent_data, None

        except requests.exceptions.RequestException as e:
            error_msg = f"API request failed: {str(e)}"
            print(f"❌ {error_msg}")
            return None, error_msg
        except json.JSONDecodeError as e:
            error_msg = f"JSON parsing failed: {str(e)}"
            print(f"❌ {error_msg}")
            return None, error_msg
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            print(f"❌ {error_msg}")
            return None, error_msg

    def extract_from_sections(self, sections, target_heading):
        """Extract data from sections by TOCHeading"""
        for section in sections:
            if section.get("TOCHeading") == target_heading:
                # Get Information array
                info_list = section.get("Information", [])
                if info_list:
                    return section, info_list[0]  # Return section and first info item
                else:
                    return section, None  # Return section even if no Information array
        return None, None

    def extract_string_value(self, info_item):
        """Extract string value from StringWithMarkup structure"""
        if not info_item:
            return ""

        value = info_item.get("Value", {})

        # Handle StringWithMarkup array
        if "StringWithMarkup" in value:
            markup_list = value["StringWithMarkup"]
            if markup_list and isinstance(markup_list, list):
                return markup_list[0].get("String", "")

        return ""

    def extract_date_value(self, info_item):
        """Extract date value from DateISO8601 structure"""
        if not info_item:
            return ""

        value = info_item.get("Value", {})

        # Handle DateISO8601 array
        if "DateISO8601" in value:
            date_list = value["DateISO8601"]
            if date_list and isinstance(date_list, list):
                return date_list[0]

        return ""

    def extract_multiple_strings(self, info_item):
        """Extract multiple strings from StringWithMarkup array (for inventors, patent family)"""
        if not info_item:
            return []

        value = info_item.get("Value", {})

        # Handle StringWithMarkup array
        if "StringWithMarkup" in value:
            markup_list = value["StringWithMarkup"]
            if markup_list and isinstance(markup_list, list):
                return [item.get("String", "") for item in markup_list if item.get("String")]

        return []

    def extract_inventors(self, sections):
        """Extract all inventors from Inventor section"""
        inventor_section, inventor_info = self.extract_from_sections(sections, "Inventor")
        if not inventor_info:
            return []

        # Use extract_multiple_strings to get all inventors from StringWithMarkup array
        return self.extract_multiple_strings(inventor_info)

    def extract_patent_family(self, sections):
        """Extract patent family members"""
        family_section, family_info = self.extract_from_sections(sections, "Patent Family")
        if not family_info:
            return []

        return self.extract_multiple_strings(family_info)

    def parse_patent_data(self, patent_json):
        """Parse patent JSON and extract target fields"""
        try:
            record = patent_json.get("Record", {})
            sections = record.get("Section", [])

            # Extract basic info from record level
            patent_data = {
                "patent_id": record.get("RecordAccession", ""),
                "title": record.get("RecordTitle", ""),
                "extraction_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            print(f"📄 Title: {patent_data['title']}")

            # Extract Abstract
            abstract_section, abstract_info = self.extract_from_sections(sections, "Abstract")
            patent_data["abstract_pubchem"] = self.extract_string_value(abstract_info)
            print(f"📝 Abstract: {len(patent_data['abstract_pubchem'])} chars")

            # Extract Inventors
            patent_data["inventors_pubchem"] = self.extract_inventors(sections)
            print(f"👥 Inventors: {len(patent_data['inventors_pubchem'])} found")
            for inventor in patent_data["inventors_pubchem"]:
                print(f"   • {inventor}")

            # Extract Assignee
            assignee_section, assignee_info = self.extract_from_sections(sections, "Assignee")
            patent_data["assignee_pubchem"] = self.extract_string_value(assignee_info)
            print(f"🏢 Assignee: {patent_data['assignee_pubchem']}")

            # Extract Dates from Important Dates section
            dates_section, _ = self.extract_from_sections(sections, "Important Dates")
            if dates_section and "Section" in dates_section:
                date_subsections = dates_section["Section"]

                # Priority Date
                priority_section, priority_info = self.extract_from_sections(date_subsections, "Priority Date")
                patent_data["priority_date_pubchem"] = self.extract_date_value(priority_info)

                # Filing Date
                filing_section, filing_info = self.extract_from_sections(date_subsections, "Filing Date")
                patent_data["filing_date_pubchem"] = self.extract_date_value(filing_info)

                # Publication Date
                publication_section, publication_info = self.extract_from_sections(date_subsections, "Publication Date")
                patent_data["publication_date_pubchem"] = self.extract_date_value(publication_info)
            else:
                patent_data["priority_date_pubchem"] = ""
                patent_data["filing_date_pubchem"] = ""
                patent_data["publication_date_pubchem"] = ""

            print(f"📅 Priority Date: {patent_data['priority_date_pubchem']}")
            print(f"📅 Filing Date: {patent_data['filing_date_pubchem']}")
            print(f"📅 Publication Date: {patent_data['publication_date_pubchem']}")

            # Extract Country
            country_section, country_info = self.extract_from_sections(sections, "Country")
            patent_data["country"] = self.extract_string_value(country_info)
            print(f"🌍 Country: {patent_data['country']}")

            # Extract Patent Family
            patent_data["patent_family_pubchem"] = self.extract_patent_family(sections)
            print(f"👨‍👩‍👧‍👦 Patent Family: {len(patent_data['patent_family_pubchem'])} members")
            if patent_data["patent_family_pubchem"]:
                for i, family_member in enumerate(patent_data["patent_family_pubchem"][:5]):  # Show first 5
                    print(f"   • {family_member}")
                if len(patent_data["patent_family_pubchem"]) > 5:
                    print(f"   ... and {len(patent_data['patent_family_pubchem']) - 5} more")

            patent_data["error"] = None
            return patent_data

        except Exception as e:
            error_msg = f"Data parsing error: {str(e)}"
            print(f"❌ {error_msg}")
            return {
                "patent_id": "",
                "error": error_msg,
                "extraction_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

    def extract_patent_metadata(self, patent_id):
        """Main extraction function for a single patent"""
        print(f"\n{'='*60}")
        print(f"EXTRACTING: {patent_id}")
        print(f"{'='*60}")

        # Fetch JSON data
        patent_json, error = self.fetch_patent_json(patent_id)
        if error:
            return {
                "patent_id": patent_id,
                "error": error,
                "extraction_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

        # Parse and extract data
        patent_data = self.parse_patent_data(patent_json)

        return patent_data


def main():
    """Main function to test PubChem JSON extraction"""
    # Test patents
    test_patents = [
        "WO-2024184281-A1",  # Complete newer patent
        "LU-92099-I2"        # Complete older patent with family
    ]

    # Allow custom patent from command line
    if len(sys.argv) > 1:
        test_patents = [sys.argv[1]]

    print("PUBCHEM PATENT JSON API EXTRACTOR")
    print("Fast and reliable patent metadata extraction using JSON API")
    print()

    extractor = PubChemPatentExtractor()

    for i, patent_id in enumerate(test_patents, 1):
        result = extractor.extract_patent_metadata(patent_id)

        # Save results to JSON file (auto-detect pubchem_extract directory)
        output_dir = Path(__file__).parent
        output_file = output_dir / f"extracted_{patent_id.replace('/', '_').replace('-', '_')}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Results saved to: {output_file}")

        # Print summary
        print(f"\n📊 EXTRACTION SUMMARY:")
        if result.get("error"):
            print(f"❌ Error: {result['error']}")
        else:
            fields_summary = [
                ("Title", "✓" if result.get("title") else "✗"),
                ("Abstract", "✓" if result.get("abstract") else "✗"),
                ("Inventors", f"✓ ({len(result.get('inventors', []))})" if result.get("inventors") else "✗"),
                ("Assignee", "✓" if result.get("assignee") else "✗"),
                ("Priority Date", "✓" if result.get("priority_date") else "✗"),
                ("Filing Date", "✓" if result.get("filing_date") else "✗"),
                ("Publication Date", "✓" if result.get("publication_date") else "✗"),
                ("Country", "✓" if result.get("country") else "✗"),
                ("Patent Family", f"✓ ({len(result.get('patent_family', []))})" if result.get("patent_family") else "✗"),
            ]

            for field, status in fields_summary:
                print(f"   {field}: {status}")

        if i < len(test_patents):
            print("\n" + "-"*60)


if __name__ == "__main__":
    main()