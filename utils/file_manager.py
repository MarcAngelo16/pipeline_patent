#!/usr/bin/env python3
"""
File Manager for Patent Pipeline

Handles all file operations including:
- Saving consolidated patent files
- Loading PubChem fetcher results
- Creating output directories
- Patent deduplication tracking
"""

import os
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Set


class FileManager:
    """Manage all file operations for the patent pipeline"""

    def __init__(self, base_output_dir=None):
        # Auto-detect output directory if not specified
        if base_output_dir is None:
            # FileManager is in utils/, so go up one level to patent_pipeline/ then to output/
            base_output_dir = Path(__file__).parent.parent / 'output'

        self.base_output_dir = str(base_output_dir) if isinstance(base_output_dir, Path) else base_output_dir
        self.processed_patents: Set[str] = set()  # Track for deduplication

    def ensure_output_directories(self):
        """Create necessary output directories"""
        dirs = [
            self.base_output_dir,
            os.path.join(self.base_output_dir, "pipeline_logs")
        ]

        for dir_path in dirs:
            os.makedirs(dir_path, exist_ok=True)

        print(f"📁 Output directories ready at: {self.base_output_dir}")

    def generate_output_filename(self, keyword: str) -> str:
        """Generate filename for consolidated patent file"""
        filename = f"{keyword}_patents.json"
        return os.path.join(self.base_output_dir, filename)

    def load_pubchem_patents(self, json_file_path: str) -> List[Dict]:
        """Load patents from PubChem fetcher JSON output"""
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Handle both array format and single object format
            if isinstance(data, list):
                patents = data
            elif isinstance(data, dict) and "patents" in data:
                patents = data["patents"]
            else:
                # Assume single patent object
                patents = [data]

            print(f"📂 Loaded {len(patents)} patents from: {json_file_path}")
            return patents

        except FileNotFoundError:
            print(f"❌ File not found: {json_file_path}")
            return []
        except json.JSONDecodeError as e:
            print(f"❌ JSON parsing error in {json_file_path}: {str(e)}")
            return []
        except Exception as e:
            print(f"❌ Error loading patents: {str(e)}")
            return []

    def is_duplicate_patent(self, patent_id: str) -> bool:
        """Check if patent has already been processed (for deduplication)"""
        return patent_id in self.processed_patents

    def mark_patent_as_processed(self, patent_id: str):
        """Mark patent as processed for deduplication"""
        self.processed_patents.add(patent_id)

    def save_consolidated_patents(self, keyword: str, all_patents: List[Dict],
                                pipeline_info: Dict) -> str:
        """Save all patents to single consolidated JSON file"""
        try:
            output_file = self.generate_output_filename(keyword)

            # Create consolidated structure
            consolidated_data = {
                "pipeline_info": {
                    "keyword": keyword,
                    "execution_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "total_patents": len(all_patents),
                    "duplicates_removed": pipeline_info.get("duplicates_removed", 0),
                    **pipeline_info  # Include additional pipeline info
                },
                "patents": all_patents
            }

            # Save to file
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(consolidated_data, f, indent=2, ensure_ascii=False)

            file_size = os.path.getsize(output_file) / 1024  # KB
            print(f"💾 Saved {len(all_patents)} patents to: {output_file}")
            print(f"📄 File size: {file_size:.1f} KB")

            return output_file

        except Exception as e:
            error_msg = f"Error saving consolidated patents: {str(e)}"
            print(f"❌ {error_msg}")
            raise Exception(error_msg)

    def save_pipeline_log(self, keyword: str, log_messages: List[str]) -> str:
        """Save pipeline execution log"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d")
            log_filename = f"{keyword}_pipeline_{timestamp}.log"
            log_file = os.path.join(self.base_output_dir, "pipeline_logs", log_filename)

            with open(log_file, 'w', encoding='utf-8') as f:
                f.write(f"PATENT PIPELINE LOG - {keyword.upper()}\n")
                f.write(f"Execution Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("="*60 + "\n\n")

                for message in log_messages:
                    f.write(f"{message}\n")

            print(f"📋 Pipeline log saved to: {log_file}")
            return log_file

        except Exception as e:
            print(f"❌ Error saving pipeline log: {str(e)}")
            return ""

    def get_patent_count_summary(self) -> Dict[str, int]:
        """Get summary of processed patents"""
        return {
            "total_processed": len(self.processed_patents),
            "unique_patents": len(self.processed_patents)
        }


def test_file_manager():
    """Test FileManager functionality"""
    print("=== TESTING FILE MANAGER ===")

    # Auto-detect base directory and create test subdirectory
    test_dir = Path(__file__).parent.parent / 'output' / 'test'
    fm = FileManager(test_dir)
    fm.ensure_output_directories()

    # Test filename generation
    filename = fm.generate_output_filename("golimumab")
    print(f"Generated filename: {filename}")

    # Test deduplication tracking
    patent_ids = ["WO-123-A1", "US-456-A1", "WO-123-A1"]  # One duplicate

    for pid in patent_ids:
        if fm.is_duplicate_patent(pid):
            print(f"Duplicate detected: {pid}")
        else:
            fm.mark_patent_as_processed(pid)
            print(f"New patent added: {pid}")

    summary = fm.get_patent_count_summary()
    print(f"Patent count summary: {summary}")


if __name__ == "__main__":
    test_file_manager()