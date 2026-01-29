#!/usr/bin/env python3
"""
Google Patents URL Generator
Converts patent publication numbers to Google Patents URLs
"""

import json
import re
from typing import List, Dict, Union

class GooglePatentsURLGenerator:
    def __init__(self):
        self.base_url = "https://patents.google.com/patent/"
        self.url_suffix = "/en"

    def clean_publication_number(self, pub_number: str) -> str:
        """
        Clean publication number for Google Patents URL
        Removes hyphens and normalizes format

        Examples:
        WO-2024184281-A1 -> WO2024184281A1
        US-123456-B2 -> US123456B2
        EP-1234567-A1 -> EP1234567A1
        """
        if not pub_number or not isinstance(pub_number, str):
            return ""

        # Remove hyphens and any extra whitespace
        cleaned = pub_number.replace("-", "").strip()

        # Remove any other common separators
        cleaned = cleaned.replace(" ", "").replace("_", "")

        return cleaned

    def generate_google_patents_url(self, pub_number: str) -> str:
        """
        Generate Google Patents URL from publication number

        Args:
            pub_number: Patent publication number (e.g., "WO-2024184281-A1")

        Returns:
            Google Patents URL (e.g., "https://patents.google.com/patent/WO2024184281A1/en")
        """
        cleaned_number = self.clean_publication_number(pub_number)

        if not cleaned_number:
            return ""

        return f"{self.base_url}{cleaned_number}{self.url_suffix}"

    def generate_pubchem_patent_url(self, pub_number: str) -> str:
        """
        Generate PubChem patent URL from publication number
        Uses publication number directly with hyphens

        Args:
            pub_number: Patent publication number (e.g., "WO-2024184281-A1")

        Returns:
            PubChem Patents URL (e.g., "https://pubchem.ncbi.nlm.nih.gov/patent/WO-2024184281-A1")
        """
        if not pub_number or not isinstance(pub_number, str):
            return ""

        # Use publication number directly for PubChem
        cleaned_number = pub_number.strip()

        if not cleaned_number:
            return ""

        return f"https://pubchem.ncbi.nlm.nih.gov/patent/{cleaned_number}"

    def add_patent_urls_to_data(self, patent_data: List[Dict]) -> List[Dict]:
        """
        Add Google Patents and PubChem patent URLs to existing patent data

        Args:
            patent_data: List of patent dictionaries

        Returns:
            Updated patent data with google_patent and pubchem_patent fields
        """
        updated_data = []

        for patent in patent_data:
            if not isinstance(patent, dict):
                updated_data.append(patent)
                continue

            # Create a copy to avoid modifying original
            updated_patent = patent.copy()

            # Look for publication number in different possible field names
            pub_number = ""
            possible_fields = [
                'publication_number',
                'publicationnumber',
                'patent_number',
                'raw_publicationnumber'
            ]

            for field in possible_fields:
                if field in patent and patent[field]:
                    pub_number = str(patent[field])
                    break

            # Generate both URLs
            if pub_number:
                google_url = self.generate_google_patents_url(pub_number)
                pubchem_url = self.generate_pubchem_patent_url(pub_number)
                updated_patent['google_patent'] = google_url
                updated_patent['pubchem_patent'] = pubchem_url
                print(f"   📍 {pub_number}")
                print(f"      Google: {google_url}")
                print(f"      PubChem: {pubchem_url}")
            else:
                updated_patent['google_patent'] = ""
                updated_patent['pubchem_patent'] = ""
                print(f"   ⚠️  No publication number found for patent")

            updated_data.append(updated_patent)

        return updated_data

    def process_patent_file(self, input_file: str, output_file: str = None):
        """
        Process a JSON patent file and add Google Patents URLs

        Args:
            input_file: Path to input JSON file with patent data
            output_file: Path to output file (optional, defaults to input_file with _with_google_urls suffix)
        """
        print(f"🔗 Processing patent file: {input_file}")

        try:
            # Read input file
            with open(input_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            print(f"📊 Loaded {len(data)} patents")

            # Add Google Patents and PubChem URLs
            updated_data = self.add_patent_urls_to_data(data)

            # Determine output file name - keep in same directory as input file
            if not output_file:
                import os
                base_dir = os.path.dirname(input_file)
                base_name = os.path.basename(input_file)

                if base_name.endswith('.json'):
                    output_filename = base_name.replace('.json', '_with_google_urls.json')
                else:
                    output_filename = f"{base_name}_with_google_urls.json"

                output_file = os.path.join(base_dir, output_filename)

            # Save updated data
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(updated_data, f, indent=2, ensure_ascii=False)

            print(f"💾 Saved updated data to: {output_file}")
            print(f"✅ Added Google Patents and PubChem URLs to {len(updated_data)} patents")

            return output_file

        except FileNotFoundError:
            print(f"❌ File not found: {input_file}")
            return None
        except json.JSONDecodeError:
            print(f"❌ Invalid JSON in file: {input_file}")
            return None
        except Exception as e:
            print(f"❌ Error processing file: {e}")
            return None

    def test_url_generation(self):
        """Test URL generation with sample publication numbers"""
        test_cases = [
            "WO-2024184281-A1",
            "US-10123456-B2",
            "EP-1234567-A1",
            "CN-108123456-A",
            "WO2024184281A1",  # Already clean
            "",  # Empty
            None  # None
        ]

        print("🧪 Testing URL generation:")
        print("=" * 80)

        for pub_number in test_cases:
            google_url = self.generate_google_patents_url(pub_number) if pub_number else ""
            pubchem_url = self.generate_pubchem_patent_url(pub_number) if pub_number else ""

            print(f"📋 {pub_number or 'None':<20}")
            print(f"   Google:  {google_url}")
            print(f"   PubChem: {pubchem_url}")
            print()

        print("=" * 80)

def main():
    """Command line interface for Google Patents URL generator"""
    import argparse

    parser = argparse.ArgumentParser(description='Add Google Patents and PubChem URLs to patent data')
    parser.add_argument('input_file', help='Input JSON file with patent data')
    parser.add_argument('-o', '--output', help='Output file (optional)')
    parser.add_argument('--test', action='store_true', help='Run URL generation tests')

    args = parser.parse_args()

    generator = GooglePatentsURLGenerator()

    if args.test:
        generator.test_url_generation()
        return

    # Process the file
    output_file = generator.process_patent_file(args.input_file, args.output)

    if output_file:
        print(f"\n✅ SUCCESS: Google Patents and PubChem URLs added")
        print(f"📁 Output file: {output_file}")
    else:
        print("\n❌ FAILED: Could not process file")

if __name__ == "__main__":
    main()