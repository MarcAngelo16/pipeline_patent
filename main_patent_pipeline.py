#!/usr/bin/env python3
"""
Main Patent Pipeline

Orchestrates the complete patent extraction workflow:
1. Fetch patents from PubChem (by keyword) or DrugBank (by ID)
2. Extract metadata for each main patent via PubChem JSON API
3. Process patent families for specified countries (nested processing)
4. Generate URLs for family patents
5. Deduplicate and create consolidated output

Usage:
    PubChem (default):
        python main_patent_pipeline.py golimumab
        python main_patent_pipeline.py golimumab --max-families 3 --countries US EP

    DrugBank:
        python main_patent_pipeline.py --source drugbank --drugbank-id DB05541
        python main_patent_pipeline.py --source drugbank --drugbank-id DB05541 --countries US EP
"""

import sys
import os
import argparse
import json
import re
from pathlib import Path
from typing import List, Dict, Set

# Auto-detect project base directory
BASE_DIR = Path(__file__).parent.absolute()

# Add project paths (relative to base directory)
sys.path.append(str(BASE_DIR / 'pubchem_fetcher'))
sys.path.append(str(BASE_DIR / 'pubchem_extract'))
sys.path.append(str(BASE_DIR / 'googlepatent_extract'))
sys.path.append(str(BASE_DIR / 'drugbank_extract'))
sys.path.append(str(BASE_DIR / 'utils'))

from pubchem_patent_fetcher import main as fetch_pubchem_patents
from pubchem_json_extractor import PubChemPatentExtractor
from pipeline_logger import PipelineLogger
from file_manager import FileManager
from patent_url_generator import PatentURLGenerator
from google_patents_clean_extractor import setup_chrome_driver, extract_patent_data
from google_sheets_integration.google_sheets_exporter import GoogleSheetsExporter
from drugbank_patent_fetcher import DrugBankPatentFetcher


class PatentPipeline:
    """Main patent pipeline orchestrator"""

    def __init__(self, keyword: str = None, drugbank_id: str = None, source: str = "pubchem",
                 max_families: int = 3, target_countries: List[str] = None,
                 max_main_patents: int = None, export_to_sheets: bool = False,
                 progress_callback=None):
        self.source = source  # "pubchem" or "drugbank"
        self.keyword = keyword
        self.drugbank_id = drugbank_id
        self.max_families = max_families
        self.target_countries = target_countries or ['US']
        self.max_main_patents = max_main_patents  # None = get all results
        self.export_to_sheets = export_to_sheets
        self.progress_callback = progress_callback  # Callback for real-time progress updates

        # Validate input based on source
        if source == "pubchem" and not keyword:
            raise ValueError("keyword is required when source is 'pubchem'")
        if source == "drugbank" and not drugbank_id:
            raise ValueError("drugbank_id is required when source is 'drugbank'")

        # Initialize components
        search_term = keyword if source == "pubchem" else drugbank_id
        self.logger = PipelineLogger(search_term)
        self.file_manager = FileManager()
        self.url_generator = PatentURLGenerator()
        self.pubchem_extractor = PubChemPatentExtractor()
        self.drugbank_fetcher = None  # Initialized when needed for DrugBank

        # Initialize Google Sheets exporter if needed
        self.sheets_exporter = None
        self.sheets_url = None
        if self.export_to_sheets:
            try:
                # Use OAuth by default (personal Google account with premium storage)
                self.sheets_exporter = GoogleSheetsExporter(use_oauth=True)
                self.logger.log_stage("SHEETS_INIT", "Google Sheets exporter initialized (OAuth)")
            except Exception as e:
                self.logger.log_error(f"Failed to initialize Google Sheets: {str(e)}", stage="SHEETS_INIT")
                self.export_to_sheets = False

        # Pipeline data
        self.all_patents: List[Dict] = []
        self.duplicates_removed = 0
        self.drug_name = None  # Will be set for DrugBank sources

    def _report_progress(self, phase: str, current: int, total: int, patent_id: str = ""):
        """Report progress to callback if available"""
        if self.progress_callback:
            percentage = (current / total * 100) if total > 0 else 0

            message = f"{phase}: {current}/{total} ({percentage:.1f}%)"
            if patent_id:
                message += f" - {patent_id}"

            self.progress_callback(int(percentage), message)

    def run_pipeline(self) -> str:
        """Execute the complete patent pipeline"""
        try:
            search_term = self.keyword if self.source == "pubchem" else self.drugbank_id
            self.logger.log_stage("PIPELINE_START",
                                f"Starting pipeline from {self.source.upper()}: '{search_term}'")
            self.logger.log_stage("CONFIG",
                                f"Source: {self.source}, "
                                f"Countries: {self.target_countries}, "
                                f"Max families per country: {self.max_families}")

            # Step 1: Setup
            self.file_manager.ensure_output_directories()

            # Step 2: Fetch main patents from selected source
            main_patents = self._fetch_main_patents()
            if not main_patents:
                raise Exception(f"No patents found from {self.source} fetcher")

            # Step 3: Process main patents (nested with families)
            self._process_all_patents(main_patents)

            # Step 4: Process Google Patents data for all patents
            self._process_google_patents()

            # Step 5: Generate final output
            output_file = self._create_final_output()

            self.logger.log_success("PIPELINE_COMPLETE",
                                   f"Processed {len(self.all_patents)} total patents")

            return output_file

        except Exception as e:
            self.logger.log_error(f"Pipeline failed: {str(e)}", stage="PIPELINE")
            raise

    def _fetch_main_patents(self) -> List[Dict]:
        """Fetch patents from selected source (PubChem or DrugBank)"""
        if self.source == "drugbank":
            return self._fetch_drugbank_patents()
        else:
            return self._fetch_pubchem_patents()

    def _fetch_pubchem_patents(self) -> List[Dict]:
        """Fetch patents from PubChem using the existing fetcher"""
        self.logger.log_stage("PUBCHEM_FETCH",
                             f"Fetching patents for keyword: '{self.keyword}'")

        try:
            # Use existing PubChem fetcher
            import subprocess
            import glob

            fetcher_path = BASE_DIR / 'pubchem_fetcher' / 'pubchem_patent_fetcher.py'
            cmd = ["python", str(fetcher_path), self.keyword, "--format", "json"]

            result = subprocess.run(cmd, capture_output=True, text=True,
                                  cwd=str(BASE_DIR / 'pubchem_fetcher'))

            if result.returncode != 0:
                raise Exception(f"PubChem fetcher failed: {result.stderr}")

            # Find the generated JSON file
            expected_file = BASE_DIR / 'pubchem_fetcher' / f'pubchem_patents_{self.keyword}.json'

            # If simple name doesn't exist, try with timestamp pattern as fallback
            if not expected_file.exists():
                pattern = str(BASE_DIR / 'pubchem_fetcher' / f'pubchem_patents_{self.keyword}_*.json')
                files = glob.glob(pattern)
                if files:
                    expected_file = max(files, key=os.path.getctime)
                else:
                    raise Exception(f"No output file found for keyword: {self.keyword}")

            latest_file = expected_file

            patents = self.file_manager.load_pubchem_patents(latest_file)

            # Limit patents if max_main_patents is specified
            if self.max_main_patents is not None and len(patents) > self.max_main_patents:
                self.logger.log_stage("PUBCHEM_FETCH",
                                     f"Limiting from {len(patents)} to {self.max_main_patents} main patents")
                patents = patents[:self.max_main_patents]

            self.logger.log_success("PUBCHEM_FETCH",
                                   f"Fetched {len(patents)} main patents from {latest_file}")
            return patents

        except Exception as e:
            self.logger.log_error(f"Failed to fetch main patents: {str(e)}",
                                stage="PUBCHEM_FETCH")
            raise

    def _fetch_drugbank_patents(self) -> List[Dict]:
        """Fetch patents from DrugBank using the DrugBank ID"""
        self.logger.log_stage("DRUGBANK_FETCH",
                             f"Fetching patents for DrugBank ID: '{self.drugbank_id}'")

        try:
            # Initialize DrugBank fetcher
            self.drugbank_fetcher = DrugBankPatentFetcher(headless=True, verbose=False)

            # Fetch patents from DrugBank
            result = self.drugbank_fetcher.fetch_patents_by_id(self.drugbank_id)

            # Close the browser
            self.drugbank_fetcher.close()

            if result.get('error'):
                raise Exception(f"DrugBank fetch failed: {result['error']}")

            # Extract drug name from result
            self.drug_name = result.get('drug_name', self.drugbank_id)
            self.logger.log_stage("DRUGBANK_FETCH",
                                 f"Drug name extracted: '{self.drug_name}'")

            drugbank_patents = result.get('patents', [])

            if not drugbank_patents:
                self.logger.log_stage("DRUGBANK_FETCH",
                                     "No patents found for this DrugBank ID")
                return []

            # Convert DrugBank patent format to pipeline format
            converted_patents = []
            for patent in drugbank_patents:
                converted_patent = {
                    'publication_number': patent['patent_id'],
                    'google_patent': patent.get('google_patent_url', ''),
                    'pubchem_patent': '',  # DrugBank doesn't have PubChem links
                    'drugbank_url': patent.get('drugbank_url', ''),
                    'approved_date': patent.get('approved_date', ''),
                    'expires_date': patent.get('expires_date', ''),
                    'country': patent.get('country', ''),
                    'pediatric_extension': patent.get('pediatric_extension', ''),
                    'source': 'DrugBank'
                }
                converted_patents.append(converted_patent)

            self.logger.log_success("DRUGBANK_FETCH",
                                   f"Fetched {len(converted_patents)} patents from DrugBank")
            return converted_patents

        except Exception as e:
            self.logger.log_error(f"Failed to fetch DrugBank patents: {str(e)}",
                                stage="DRUGBANK_FETCH")
            if self.drugbank_fetcher:
                self.drugbank_fetcher.close()
            raise

    def _process_all_patents(self, main_patents: List[Dict]):
        """Process all main patents and their families (nested approach)"""
        self.logger.log_stage("PROCESSING_START",
                             f"Processing {len(main_patents)} main patents")

        total_main = len(main_patents)

        for i, main_patent in enumerate(main_patents, 1):
            patent_id = main_patent.get('publication_number', 'Unknown')
            self.logger.log_progress(i, total_main, "Main Patents", patent_id)

            # Report progress - Phase 1
            self._report_progress("Phase 1: Retrieving patents from PubChem", i, total_main, patent_id)

            try:
                # Process main patent
                main_data = self._process_main_patent(main_patent)
                if main_data:
                    self._add_patent_if_unique(main_data)

                    # Process family patents for this main patent
                    self._process_family_patents(main_data)

            except Exception as e:
                self.logger.log_error(f"Failed to process main patent: {str(e)}",
                                    patent_id, "MAIN_PROCESSING")

    def _process_main_patent(self, main_patent: Dict) -> Dict:
        """Process a single main patent"""
        patent_id = main_patent.get('publication_number', '')

        try:
            # Extract metadata using PubChem JSON API
            patent_data = self.pubchem_extractor.extract_patent_metadata(patent_id)

            # Add pipeline-specific fields based on source
            if self.source == "drugbank":
                patent_data['extraction_from'] = f"DrugBank ID: {self.drugbank_id}"
                # Add DrugBank-specific fields
                if 'drugbank_url' in main_patent:
                    patent_data['drugbank_url'] = main_patent['drugbank_url']
                if 'approved_date' in main_patent:
                    patent_data['approved_date_drugbank'] = main_patent['approved_date']
                if 'expires_date' in main_patent:
                    patent_data['expires_date_drugbank'] = main_patent['expires_date']
                if 'pediatric_extension' in main_patent:
                    patent_data['pediatric_extension'] = main_patent['pediatric_extension']
            else:
                patent_data['extraction_from'] = f"Pubchem keyword: {self.keyword}"

            # Add URLs from original fetcher (if available)
            if 'google_patent' in main_patent:
                patent_data['google_patent'] = main_patent['google_patent']
            if 'pubchem_patent' in main_patent:
                patent_data['pubchem_patent'] = main_patent['pubchem_patent']

            return patent_data

        except Exception as e:
            self.logger.log_error(f"Main patent extraction failed: {str(e)}",
                                patent_id, "MAIN_EXTRACTION")
            return None

    def _process_family_patents(self, main_patent: Dict):
        """Process patent family for specified countries"""
        # Skip family processing if max_families is 0
        if self.max_families == 0:
            return

        patent_id = main_patent.get('patent_id', '')
        patent_family = main_patent.get('patent_family_pubchem', [])

        if not patent_family:
            return

        self.logger.log_family_processing(patent_id, self.target_countries,
                                        self.max_families)

        for country in self.target_countries:
            try:
                # Find patents for this country
                country_patents = self._find_country_patents(patent_family, country)
                selected_patents = country_patents[:self.max_families]

                self.logger.log_country_results(country, len(country_patents),
                                               len(selected_patents))

                # Process each selected family patent
                for family_patent_id in selected_patents:
                    self._process_family_patent(family_patent_id, patent_id)

            except Exception as e:
                self.logger.log_error(f"Family processing failed for {country}: {str(e)}",
                                    patent_id, f"FAMILY_{country}")

    def _find_country_patents(self, patent_family: List[str], country: str) -> List[str]:
        """Find patents from specified country in patent family"""
        country_pattern = rf"^{country}[-\s]"
        country_patents = []

        for family_patent in patent_family:
            if re.match(country_pattern, family_patent, re.IGNORECASE):
                country_patents.append(family_patent)

        return country_patents

    def _process_family_patent(self, family_patent_id: str, parent_patent_id: str):
        """Process a single family patent"""
        try:
            # Extract metadata
            family_data = self.pubchem_extractor.extract_patent_metadata(family_patent_id)

            if not family_data or family_data.get('error'):
                self.logger.log_error("Family patent extraction failed",
                                    family_patent_id, "FAMILY_EXTRACTION")
                return

            # Add family-specific fields
            family_data['extraction_from'] = f"patent family from {parent_patent_id}"

            # Generate URLs for family patent
            urls = self.url_generator.generate_both_urls(family_patent_id)
            family_data.update(urls)

            # Handle family's own patent family field
            if family_data.get('patent_family_pubchem'):
                family_data['patent_family_pubchem'] = (
                    f"patent family extracted from {parent_patent_id}, "
                    f"eventhough there is patent family"
                )
            else:
                family_data['patent_family_pubchem'] = (
                    f"patent family extracted from {parent_patent_id}, "
                    f"patent family is empty"
                )

            # Add to collection
            self._add_patent_if_unique(family_data)

        except Exception as e:
            self.logger.log_error(f"Family patent processing failed: {str(e)}",
                                family_patent_id, "FAMILY_PROCESSING")

    def _add_patent_if_unique(self, patent_data: Dict):
        """Add patent to collection if not duplicate"""
        patent_id = patent_data.get('patent_id', '')

        if self.file_manager.is_duplicate_patent(patent_id):
            self.duplicates_removed += 1
            self.logger.log_stage("DEDUPLICATION", f"Removed duplicate: {patent_id}")
        else:
            self.file_manager.mark_patent_as_processed(patent_id)
            self.all_patents.append(patent_data)

    def _process_google_patents(self):
        """Process Google Patents data for all collected patents"""
        if not self.all_patents:
            return

        self.logger.log_stage("GOOGLE_PATENTS_START",
                             f"Processing Google Patents data for {len(self.all_patents)} patents")

        # Setup Chrome driver once for all patents
        driver = None
        try:
            driver = setup_chrome_driver()

            total_patents = len(self.all_patents)

            for i, patent in enumerate(self.all_patents, 1):
                patent_id = patent.get('patent_id', 'Unknown')
                google_url = patent.get('google_patent', '')

                self.logger.log_progress(i, total_patents, "Google Patents", patent_id)

                # Report progress - Phase 2
                self._report_progress("Phase 2: Retrieving Google Patents", i, total_patents, patent_id)

                if not google_url:
                    self.logger.log_error("No Google Patents URL available", patent_id, "GOOGLE_PATENTS")
                    patent['abstract_google'] = ""
                    patent['inventors_google'] = []
                    patent['assignees_google'] = []
                    patent['claims'] = []
                    continue

                try:
                    # Extract Google Patents data
                    google_data = extract_patent_data(driver, google_url)

                    if google_data.get('error'):
                        self.logger.log_error(f"Google Patents extraction failed: {google_data['error']}",
                                            patent_id, "GOOGLE_PATENTS")
                        patent['abstract_google'] = ""
                        patent['inventors_google'] = []
                        patent['assignees_google'] = []
                        patent['claims'] = []
                    else:
                        # Add Google Patents data to patent object
                        patent['abstract_google'] = google_data.get('abstract', '')
                        patent['inventors_google'] = google_data.get('inventors', [])
                        patent['assignees_google'] = google_data.get('assignees', [])
                        patent['claims'] = google_data.get('claims', []) or []

                        # Log successful extraction
                        stats = []
                        if patent['abstract_google']: stats.append(f"abstract ({len(patent['abstract_google'])} chars)")
                        if patent['inventors_google']: stats.append(f"{len(patent['inventors_google'])} inventors")
                        if patent['assignees_google']: stats.append(f"{len(patent['assignees_google'])} assignees")
                        if patent['claims']: stats.append(f"{len(patent['claims'])} claims")

                        if stats:
                            self.logger.log_success("GOOGLE_EXTRACTION",
                                                   f"{patent_id}: {', '.join(stats)}")

                except Exception as e:
                    self.logger.log_error(f"Google Patents processing failed: {str(e)}",
                                        patent_id, "GOOGLE_PATENTS")
                    patent['abstract_google'] = ""
                    patent['inventors_google'] = []
                    patent['assignees_google'] = []
                    patent['claims'] = []

        except Exception as e:
            self.logger.log_error(f"Failed to setup Chrome driver: {str(e)}", stage="GOOGLE_PATENTS")
            # Add empty Google Patents fields to all patents
            for patent in self.all_patents:
                patent['abstract_google'] = ""
                patent['inventors_google'] = []
                patent['assignees_google'] = []
                patent['claims'] = []
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass

        self.logger.log_stage("GOOGLE_PATENTS_COMPLETE",
                             f"Completed Google Patents processing for {len(self.all_patents)} patents")

    def _create_final_output(self) -> str:
        """Create final consolidated output file and export to Google Sheets if enabled"""
        self.logger.log_stage("OUTPUT_GENERATION",
                             f"Creating consolidated output with {len(self.all_patents)} patents")

        search_term = self.keyword if self.source == "pubchem" else self.drugbank_id

        pipeline_info = {
            "source": self.source,
            "keyword": self.keyword if self.source == "pubchem" else None,
            "drugbank_id": self.drugbank_id if self.source == "drugbank" else None,
            "execution_time": self.logger.start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_patents": len(self.all_patents),
            "countries": self.target_countries,
            "max_families_per_country": self.max_families,
            "main_patents": len([p for p in self.all_patents
                               if ("keyword" in p.get('extraction_from', '') or
                                   "DrugBank ID" in p.get('extraction_from', ''))]),
            "family_patents": len([p for p in self.all_patents
                                 if "family" in p.get('extraction_from', '')]),
            "duplicates_removed": self.duplicates_removed,
            **self.logger.create_summary_report()["processing_stats"]
        }

        # Save consolidated file
        output_file = self.file_manager.save_consolidated_patents(
            search_term, self.all_patents, pipeline_info)

        # Export to Google Sheets if enabled
        if self.export_to_sheets and self.sheets_exporter:
            try:
                self.logger.log_stage("SHEETS_EXPORT", "Exporting to Google Sheets...")

                # Prepare data for Google Sheets
                sheets_data = {
                    "pipeline_info": pipeline_info,
                    "patents": self.all_patents
                }

                # Use drug_name for DrugBank, keyword for PubChem
                display_name = self.drug_name if self.source == "drugbank" and self.drug_name else search_term

                self.sheets_url = self.sheets_exporter.export_pipeline_results(
                    display_name, sheets_data, source=self.source)

                self.logger.log_success("SHEETS_EXPORT",
                                       f"Successfully exported to Google Sheets: {self.sheets_url}")
            except Exception as e:
                self.logger.log_error(f"Failed to export to Google Sheets: {str(e)}",
                                    stage="SHEETS_EXPORT")

        # Save execution log
        self.file_manager.save_pipeline_log(search_term, self.logger.get_log_messages())

        return output_file


def main():
    """Main entry point with argument parsing"""
    parser = argparse.ArgumentParser(
        description="Patent Pipeline - Extract patents and families from PubChem or DrugBank")

    parser.add_argument("keyword", nargs='?', help="Search keyword for PubChem (e.g., 'golimumab', 'insulin')")
    parser.add_argument("--source", choices=['pubchem', 'drugbank'], default='pubchem',
                       help="Patent data source (default: pubchem)")
    parser.add_argument("--drugbank-id", help="DrugBank ID (e.g., 'DB05541') - required when source=drugbank")
    parser.add_argument("--max-families", type=int, default=3,
                       help="Maximum family patents per country (default: 3)")
    parser.add_argument("--countries", nargs='+', default=['US'],
                       help="Target countries for family patents (default: US)")
    parser.add_argument("--export-sheets", action="store_true",
                       help="Export results to Google Sheets (requires credentials)")

    args = parser.parse_args()

    # Validate arguments based on source
    if args.source == 'pubchem' and not args.keyword:
        parser.error("keyword is required when source is 'pubchem'")
    if args.source == 'drugbank' and not args.drugbank_id:
        parser.error("--drugbank-id is required when source is 'drugbank'")

    try:
        print("PATENT PIPELINE STARTING")
        print(f"   Source: {args.source.upper()}")
        if args.source == 'pubchem':
            print(f"   Keyword: {args.keyword}")
        else:
            print(f"   DrugBank ID: {args.drugbank_id}")
        print(f"   Countries: {', '.join(args.countries)}")
        print(f"   Max families per country: {args.max_families}")
        if args.export_sheets:
            print("   Google Sheets export: ENABLED")
        print()

        # Create and run pipeline
        pipeline = PatentPipeline(
            keyword=args.keyword,
            drugbank_id=args.drugbank_id,
            source=args.source,
            max_families=args.max_families,
            target_countries=args.countries,
            export_to_sheets=args.export_sheets
        )

        output_file = pipeline.run_pipeline()

        print()
        print("PIPELINE COMPLETED SUCCESSFULLY")
        print(f"   Output file: {output_file}")
        print(f"   Total patents: {len(pipeline.all_patents)}")
        if pipeline.duplicates_removed > 0:
            print(f"   Duplicates removed: {pipeline.duplicates_removed}")

        # Show Google Sheets URL if exported
        if args.export_sheets and pipeline.sheets_url:
            print(f"   Google Sheets: {pipeline.sheets_url}")

    except Exception as e:
        print(f"\nPIPELINE FAILED: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()