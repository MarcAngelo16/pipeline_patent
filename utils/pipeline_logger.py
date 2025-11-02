#!/usr/bin/env python3
"""
Pipeline Logger for Patent Pipeline

Centralized logging system for tracking pipeline execution,
progress, errors, and generating summary reports.
"""

from datetime import datetime
from typing import List, Dict


class PipelineLogger:
    """Centralized logging for patent pipeline execution"""

    def __init__(self, keyword: str):
        self.keyword = keyword
        self.start_time = datetime.now()
        self.log_messages: List[str] = []
        self.errors: List[Dict] = []
        self.progress_stats = {
            "main_patents_processed": 0,
            "main_patents_total": 0,
            "family_patents_processed": 0,
            "family_patents_total": 0
        }

    def log_stage(self, stage_name: str, message: str):
        """Log a pipeline stage with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {stage_name}: {message}"
        self.log_messages.append(formatted_message)
        print(f"🔄 {formatted_message}")

    def log_progress(self, current: int, total: int, item_type: str, item_name: str = ""):
        """Log progress with progress indicator"""
        percentage = (current / total * 100) if total > 0 else 0
        timestamp = datetime.now().strftime("%H:%M:%S")

        progress_bar = self._generate_progress_bar(current, total)
        item_info = f" - {item_name}" if item_name else ""

        message = f"[{timestamp}] Progress: {item_type} {current}/{total} ({percentage:.1f}%) {progress_bar}{item_info}"
        self.log_messages.append(message)
        print(f"📊 {message}")

        # Update internal stats
        if "main" in item_type.lower():
            self.progress_stats["main_patents_processed"] = current
            self.progress_stats["main_patents_total"] = total
        elif "family" in item_type.lower():
            self.progress_stats["family_patents_processed"] += 1

    def log_error(self, error_message: str, patent_id: str = "", stage: str = ""):
        """Log error with context information"""
        timestamp = datetime.now().strftime("%H:%M:%S")

        error_entry = {
            "timestamp": timestamp,
            "patent_id": patent_id,
            "stage": stage,
            "error": error_message
        }

        self.errors.append(error_entry)

        formatted_message = f"[{timestamp}] ERROR"
        if patent_id:
            formatted_message += f" ({patent_id})"
        if stage:
            formatted_message += f" [{stage}]"
        formatted_message += f": {error_message}"

        self.log_messages.append(formatted_message)
        print(f"❌ {formatted_message}")

    def log_success(self, message: str, details: str = ""):
        """Log successful operation"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        full_message = f"[{timestamp}] SUCCESS: {message}"
        if details:
            full_message += f" - {details}"

        self.log_messages.append(full_message)
        print(f"✅ {full_message}")

    def log_family_processing(self, parent_patent: str, countries: List[str],
                            max_per_country: int):
        """Log start of family patent processing"""
        countries_str = ", ".join(countries)
        self.log_stage("FAMILY_PROCESSING",
                      f"Processing families for {parent_patent} "
                      f"(Countries: {countries_str}, Max per country: {max_per_country})")

    def log_country_results(self, country: str, found: int, selected: int):
        """Log results for country-specific patent family search"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        message = f"[{timestamp}] {country}: Found {found} patents, selected {selected}"
        self.log_messages.append(message)
        print(f"🌍 {message}")

    def create_summary_report(self) -> Dict:
        """Generate comprehensive pipeline summary"""
        end_time = datetime.now()
        duration = end_time - self.start_time

        summary = {
            "execution_summary": {
                "keyword": self.keyword,
                "start_time": self.start_time.strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": end_time.strftime("%Y-%m-%d %H:%M:%S"),
                "duration_minutes": round(duration.total_seconds() / 60, 2),
                "total_errors": len(self.errors)
            },
            "processing_stats": {
                **self.progress_stats,
                "success_rate": self._calculate_success_rate()
            },
            "errors": self.errors,
            "execution_log": self.log_messages
        }

        return summary

    def get_log_messages(self) -> List[str]:
        """Get all log messages for file output"""
        return self.log_messages.copy()

    def _generate_progress_bar(self, current: int, total: int, width: int = 20) -> str:
        """Generate ASCII progress bar"""
        if total == 0:
            return "[" + " " * width + "]"

        filled = int(width * current / total)
        bar = "█" * filled + "░" * (width - filled)
        return f"[{bar}]"

    def _calculate_success_rate(self) -> float:
        """Calculate overall success rate"""
        total_processed = (self.progress_stats["main_patents_processed"] +
                         self.progress_stats["family_patents_processed"])

        if total_processed == 0:
            return 0.0

        errors = len(self.errors)
        success_rate = ((total_processed - errors) / total_processed) * 100
        return round(success_rate, 1)


def test_pipeline_logger():
    """Test PipelineLogger functionality"""
    print("=== TESTING PIPELINE LOGGER ===")

    logger = PipelineLogger("golimumab")

    # Test different log types
    logger.log_stage("INITIALIZATION", "Starting patent pipeline")
    logger.log_progress(5, 28, "Main Patents", "WO-2024-A1")
    logger.log_family_processing("WO-2024-A1", ["US", "EP"], 3)
    logger.log_country_results("US", 15, 3)
    logger.log_error("API timeout", "US-123-A1", "extraction")
    logger.log_success("Pipeline completed", "113 patents processed")

    # Generate summary
    summary = logger.create_summary_report()
    print(f"\nSummary: {summary['execution_summary']}")
    print(f"Errors: {len(summary['errors'])}")


if __name__ == "__main__":
    test_pipeline_logger()