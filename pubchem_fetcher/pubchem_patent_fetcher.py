#!/usr/bin/env python3
"""
PubChem Patent Data Fetcher
Uses discovered API endpoints to download patent data for drug compounds
"""

import requests
import json
import csv
import time
from urllib.parse import quote, unquote
from datetime import datetime
from pathlib import Path
import pandas as pd

class PubChemPatentFetcher:
    def __init__(self):
        self.base_url = "https://pubchem.ncbi.nlm.nih.gov"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })

    def build_patent_search_query(self, compound_name, limit=10000000):
        """Build the search query for patent data"""
        # Split compound_name by spaces to create separate AND conditions
        # This matches PubChem's behavior for multi-word searches
        keywords = compound_name.strip().split()

        # Create AND conditions for each keyword
        ands_conditions = [{"*": keyword} for keyword in keywords]

        query = {
            "download": "*",
            "collection": "patent",
            "order": ["relevancescore,desc"],
            "start": 1,
            "limit": limit,
            "downloadfilename": f"PubChem_patent_text_{compound_name}",
            "where": {
                "ands": ands_conditions
            }
        }
        return query

    def generate_google_patents_url(self, pub_number):
        """
        Generate Google Patents URL from publication number
        Removes hyphens and adds proper prefix/suffix

        Example: WO-2024184281-A1 -> https://patents.google.com/patent/WO2024184281A1/en
        """
        if not pub_number or not isinstance(pub_number, str):
            return ""

        # Remove hyphens and normalize
        cleaned_number = pub_number.replace("-", "").strip()
        cleaned_number = cleaned_number.replace(" ", "").replace("_", "")

        if not cleaned_number:
            return ""

        return f"https://patents.google.com/patent/{cleaned_number}/en"

    def generate_pubchem_patent_url(self, pub_number):
        """
        Generate PubChem patent URL from publication number
        Uses publication number directly with hyphens

        Example: WO-2024184281-A1 -> https://pubchem.ncbi.nlm.nih.gov/patent/WO-2024184281-A1
        """
        if not pub_number or not isinstance(pub_number, str):
            return ""

        # Use publication number directly for PubChem
        cleaned_number = pub_number.strip()

        if not cleaned_number:
            return ""

        return f"https://pubchem.ncbi.nlm.nih.gov/patent/{cleaned_number}"

    def fetch_patent_summary_csv(self, compound_name):
        """Fetch patent summary data in CSV format"""
        print(f"🔍 Fetching patent summary for: {compound_name}")

        try:
            # Build query
            query = self.build_patent_search_query(compound_name)
            query_json = json.dumps(query, separators=(',', ':'))

            # Build URL
            url = f"{self.base_url}/sdq/sdqagent.cgi"
            params = {
                'infmt': 'json',
                'outfmt': 'csv',
                'query': query_json,
                'showcolumnDisplayname': '1'
            }

            print(f"📡 Making request to: {url}")
            print(f"   Query: {compound_name}")

            response = self.session.get(url, params=params, timeout=30)

            print(f"📊 Response: {response.status_code} ({len(response.text)} chars)")

            if response.status_code == 200 and len(response.text) > 100:
                print("✅ Successfully retrieved patent data")
                return response.text
            else:
                print(f"⚠️  Unexpected response: {response.status_code}")
                print(f"   Content: {response.text[:200]}...")
                return None

        except Exception as e:
            print(f"❌ Error fetching patent data: {e}")
            return None

    def fetch_patent_summary_json(self, compound_name):
        """Fetch patent summary data in JSON format"""
        print(f"🔍 Fetching patent summary (JSON) for: {compound_name}")

        try:
            # Build query
            query = self.build_patent_search_query(compound_name)
            query_json = json.dumps(query, separators=(',', ':'))

            # Build URL
            url = f"{self.base_url}/sdq/sdqagent.cgi"
            params = {
                'infmt': 'json',
                'outfmt': 'json',
                'query': query_json,
                'showcolumnDisplayname': '1'
            }

            print(f"📡 Making request to: {url}")

            response = self.session.get(url, params=params, timeout=30)

            print(f"📊 Response: {response.status_code} ({len(response.text)} chars)")

            if response.status_code == 200:
                try:
                    data = response.json()
                    print("✅ Successfully retrieved patent JSON data")
                    return data
                except json.JSONDecodeError:
                    print("⚠️  Response is not valid JSON")
                    print(f"   Content: {response.text[:200]}...")
                    return None
            else:
                print(f"⚠️  Unexpected response: {response.status_code}")
                return None

        except Exception as e:
            print(f"❌ Error fetching patent data: {e}")
            return None

    def parse_json_patent_data(self, json_data):
        """Parse JSON patent data from PubChem"""
        try:
            print(f"📊 Processing JSON response...")

            # Handle different possible JSON structures
            patents = []

            if isinstance(json_data, list):
                print(f"   Found list with {len(json_data)} items")
                patents_list = json_data
            elif isinstance(json_data, dict):
                # Check for common data containers
                if 'data' in json_data:
                    patents_list = json_data['data']
                elif 'results' in json_data:
                    patents_list = json_data['results']
                elif 'records' in json_data:
                    patents_list = json_data['records']
                else:
                    # Assume the dict itself is a single patent
                    patents_list = [json_data]
                print(f"   Found dict with {len(patents_list)} patent records")
            else:
                print("⚠️  Unexpected JSON structure")
                return []

            # Process each patent record
            for idx, patent_record in enumerate(patents_list):
                if not isinstance(patent_record, dict):
                    continue

                # Extract patent information with exact field names from PubChem
                pub_number = patent_record.get('publicationnumber', '')
                patent_info = {
                    'source': 'PubChem',
                    'publication_number': pub_number,
                    'title': patent_record.get('title', ''),
                    'abstract': patent_record.get('abstract', ''),
                    'priority_date': patent_record.get('prioritydate', ''),
                    'grant_date': patent_record.get('grantdate', ''),
                    'inventors': patent_record.get('inventors', []),
                    'assignees': patent_record.get('assignees', ''),
                    'classification': patent_record.get('classification', []),
                    'family': patent_record.get('family', ''),
                    'cids': patent_record.get('cids', []),
                    'sids': patent_record.get('sids', []),
                    'google_patent': self.generate_google_patents_url(pub_number),
                    'pubchem_patent': self.generate_pubchem_patent_url(pub_number)
                }

                # Add any additional fields from the raw data
                for key, value in patent_record.items():
                    if key not in patent_info:
                        patent_info[f'raw_{key}'] = value

                patents.append(patent_info)

            print(f"   ✅ Processed {len(patents)} patent records")
            if patents:
                print(f"   Example fields: {list(patents[0].keys())}")

            return patents

        except Exception as e:
            print(f"❌ Error parsing JSON data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def parse_csv_patent_data(self, csv_content):
        """Parse CSV patent data and extract relevant fields"""
        try:
            # Parse CSV content
            lines = csv_content.strip().split('\n')
            if len(lines) < 2:
                print("⚠️  No patent data found in CSV")
                return []

            # Use pandas to handle CSV parsing
            from io import StringIO
            df = pd.read_csv(StringIO(csv_content))

            print(f"📊 Parsed {len(df)} patent records")
            print(f"   Columns: {list(df.columns)}")

            # Show first few columns for debugging
            if len(df.columns) > 0:
                print(f"   First 10 columns: {list(df.columns)[:10]}")

            # Map PubChem field names to our expected structure
            field_mapping = {
                # Try different possible field names PubChem might use
                'publication_number': ['publicationnumber', 'publication_number', 'patent_number', 'Publication Number'],
                'title': ['title', 'Title', 'patent_title'],
                'abstract': ['abstract', 'Abstract', 'description'],
                'priority_date': ['prioritydate', 'priority_date', 'Priority Date'],
                'grant_date': ['grantdate', 'grant_date', 'Grant Date'],
                'inventors': ['inventors', 'Inventors', 'inventor'],
                'assignees': ['assignees', 'Assignees', 'applicant'],
                'classification': ['classification', 'Classification', 'class'],
                'family': ['family', 'Family', 'patent_family'],
                'cids': ['cids', 'CIDs', 'compound_ids'],
                'sids': ['sids', 'SIDs', 'substance_ids']
            }

            # Extract relevant patent information
            patents = []
            for idx, row in df.iterrows():
                patent_info = {'source': 'PubChem'}

                # Map each field using the mapping
                for target_field, possible_names in field_mapping.items():
                    value = ''
                    for name in possible_names:
                        if name in df.columns:
                            value = str(row.get(name, '')) if pd.notna(row.get(name, '')) else ''
                            break
                    patent_info[target_field] = value

                # Add any additional columns that might be useful
                for col in df.columns:
                    if col.lower() not in [name.lower() for names in field_mapping.values() for name in names]:
                        # Add unmapped columns with original names
                        patent_info[f"raw_{col.lower().replace(' ', '_')}"] = str(row.get(col, '')) if pd.notna(row.get(col, '')) else ''

                patents.append(patent_info)

            # Show example of first patent for debugging
            if patents:
                print(f"   Example patent fields: {list(patents[0].keys())}")

            return patents

        except Exception as e:
            print(f"❌ Error parsing CSV data: {e}")
            import traceback
            traceback.print_exc()
            return []

    def save_patent_data(self, patents, compound_name, output_format='csv'):
        """Save patent data to file"""
        if not patents:
            print("⚠️  No patent data to save")
            return None

        # Auto-detect the pubchem_fetcher directory
        output_dir = Path(__file__).parent
        timestamp = int(time.time())

        if output_format.lower() == 'csv':
            filename = output_dir / f"pubchem_patents_{compound_name}_{timestamp}.csv"

            try:
                df = pd.DataFrame(patents)
                df.to_csv(filename, index=False)
                print(f"💾 Saved {len(patents)} patents to: {filename}")
                return str(filename)
            except Exception as e:
                print(f"❌ Error saving CSV: {e}")
                return None

        elif output_format.lower() == 'json':
            filename = output_dir / f"pubchem_patents_{compound_name}_{timestamp}.json"

            try:
                with open(filename, 'w') as f:
                    json.dump(patents, f, indent=2)
                print(f"💾 Saved {len(patents)} patents to: {filename}")
                return str(filename)
            except Exception as e:
                print(f"❌ Error saving JSON: {e}")
                return None

        return None

    def fetch_patents_for_compound(self, compound_name, output_format='json', save_raw=False):
        """Main method to fetch and save patent data for a compound"""
        print("=" * 60)
        print(f"🏭 PUBCHEM PATENT FETCHER - {compound_name.upper()}")
        print("=" * 60)

        # Try JSON format first (preferred format)
        json_data = self.fetch_patent_summary_json(compound_name)

        if json_data:
            # Save raw response for debugging if requested
            if save_raw:
                timestamp = int(time.time())
                output_dir = Path(__file__).parent
                raw_filename = output_dir / f"pubchem_raw_response_{compound_name}_{timestamp}.json"
                try:
                    with open(raw_filename, 'w', encoding='utf-8') as f:
                        json.dump(json_data, f, indent=2)
                    print(f"💾 Raw JSON response saved to: {raw_filename}")
                except Exception as e:
                    print(f"⚠️  Could not save raw response: {e}")

            # Parse the JSON data
            patents = self.parse_json_patent_data(json_data)

            if patents:
                # Save the data (always as JSON now)
                filename = self.save_patent_data(patents, compound_name, output_format)

                # Summary
                print("\n📋 PATENT SUMMARY:")
                print(f"   Compound: {compound_name}")
                print(f"   Patents found: {len(patents)}")
                print(f"   Output file: {filename}")
                print(f"   Source: PubChem Patent Database")

                return {
                    'compound': compound_name,
                    'patent_count': len(patents),
                    'patents': patents,
                    'output_file': filename,
                    'source': 'PubChem'
                }
            else:
                print("⚠️  No parseable patent data found")
                return None
        else:
            print("❌ Failed to fetch patent data")
            return None

def main():
    """Command line interface for the PubChem patent fetcher"""
    import argparse

    parser = argparse.ArgumentParser(description='Fetch patent data from PubChem for a given compound')
    parser.add_argument('compound', help='Compound name to search for (e.g., golimumab, insulin)')
    parser.add_argument('--format', choices=['csv', 'json'], default='json',
                       help='Output format (default: json)')
    parser.add_argument('--save-raw', action='store_true',
                       help='Save raw API response for debugging')

    args = parser.parse_args()

    fetcher = PubChemPatentFetcher()

    # Fetch patents with specified compound and format
    result = fetcher.fetch_patents_for_compound(args.compound, output_format=args.format, save_raw=args.save_raw)

    if result:
        print(f"\n✅ SUCCESS: Found {result['patent_count']} patents for {result['compound']}")
        print(f"📁 Saved to: {result['output_file']}")
    else:
        print("\n❌ FAILED: No patent data retrieved")

if __name__ == "__main__":
    main()