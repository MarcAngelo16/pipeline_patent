#!/usr/bin/env python3
"""
Search History Database
Manages SQLite database for storing successful patent searches
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class SearchHistoryDB:
    def __init__(self, db_path: Optional[str] = None):
        """Initialize database connection"""
        if db_path is None:
            # Default to utils directory
            db_path = Path(__file__).parent / "search_history.db"

        self.db_path = str(db_path)
        self._init_database()

    def _init_database(self):
        """Create the search_history table if it doesn't exist"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS search_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    keyword TEXT NOT NULL,
                    google_sheets_url TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create index on timestamp for faster cleanup queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp
                ON search_history(timestamp)
            """)

            conn.commit()
            conn.close()
            logger.info(f"Database initialized: {self.db_path}")

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def add_search(self, keyword: str, google_sheets_url: Optional[str] = None):
        """
        Add a new search record to history

        Args:
            keyword: Search keyword used
            google_sheets_url: Google Sheets URL (if export was successful)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO search_history (keyword, google_sheets_url, timestamp)
                VALUES (?, ?, ?)
            """, (keyword, google_sheets_url, datetime.now()))

            conn.commit()
            conn.close()

            logger.info(f"Added search to history: {keyword}")

        except Exception as e:
            logger.error(f"Failed to add search to history: {e}")
            raise

    def get_history(self, limit: int = 100) -> List[Dict]:
        """
        Get search history, ordered by most recent first

        Args:
            limit: Maximum number of records to return

        Returns:
            List of dictionaries with search history
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Enable column access by name
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, keyword, google_sheets_url, timestamp
                FROM search_history
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))

            rows = cursor.fetchall()
            conn.close()

            # Convert to list of dictionaries
            history = []
            for row in rows:
                history.append({
                    'id': row['id'],
                    'keyword': row['keyword'],
                    'google_sheets_url': row['google_sheets_url'],
                    'timestamp': row['timestamp']
                })

            logger.info(f"Retrieved {len(history)} history records")
            return history

        except Exception as e:
            logger.error(f"Failed to retrieve history: {e}")
            return []

    def cleanup_old_entries(self, months: int = 3):
        """
        Delete entries older than specified months

        Args:
            months: Number of months to keep (default: 3)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Calculate cutoff date
            cutoff_date = datetime.now() - timedelta(days=months * 30)

            cursor.execute("""
                DELETE FROM search_history
                WHERE timestamp < ?
            """, (cutoff_date,))

            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()

            logger.info(f"Cleaned up {deleted_count} old entries (older than {months} months)")
            return deleted_count

        except Exception as e:
            logger.error(f"Failed to cleanup old entries: {e}")
            return 0

    def get_stats(self) -> Dict:
        """Get database statistics"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Total entries
            cursor.execute("SELECT COUNT(*) FROM search_history")
            total = cursor.fetchone()[0]

            # Entries with Google Sheets URLs
            cursor.execute("SELECT COUNT(*) FROM search_history WHERE google_sheets_url IS NOT NULL")
            with_sheets = cursor.fetchone()[0]

            # Oldest entry
            cursor.execute("SELECT MIN(timestamp) FROM search_history")
            oldest = cursor.fetchone()[0]

            # Newest entry
            cursor.execute("SELECT MAX(timestamp) FROM search_history")
            newest = cursor.fetchone()[0]

            conn.close()

            return {
                'total_entries': total,
                'with_google_sheets': with_sheets,
                'oldest_entry': oldest,
                'newest_entry': newest
            }

        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}


# Example usage
if __name__ == "__main__":
    # Test the database
    db = SearchHistoryDB()

    # Add test entries
    db.add_search("golimumab", "https://docs.google.com/spreadsheets/d/test123")
    db.add_search("insulin", "https://docs.google.com/spreadsheets/d/test456")
    db.add_search("lansoprazole inject", None)  # No sheets URL

    # Get history
    history = db.get_history(limit=10)
    print(f"\nSearch History ({len(history)} entries):")
    for entry in history:
        print(f"  - {entry['keyword']} | {entry['timestamp']} | {entry['google_sheets_url']}")

    # Get stats
    stats = db.get_stats()
    print(f"\nDatabase Stats:")
    print(f"  Total entries: {stats['total_entries']}")
    print(f"  With Google Sheets: {stats['with_google_sheets']}")
    print(f"  Oldest: {stats['oldest_entry']}")
    print(f"  Newest: {stats['newest_entry']}")

    # Cleanup old entries (test with 0 months to see it work)
    # db.cleanup_old_entries(months=0)
