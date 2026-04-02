#!/usr/bin/env python3
"""
Analysis Database
Manages SQLite database for Patent Analysis feature:
  - patent_analyses: source patent metadata + AI search plan
  - search_batches:  PDKI batch run records
  - pdki_results:    deduplicated PDKI patent results
"""

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import logging

logger = logging.getLogger(__name__)


class AnalysisDB:
    def __init__(self, db_path: Optional[str] = None):
        """Initialize database connection. Defaults to utils/analysis.db."""
        if db_path is None:
            db_path = Path(__file__).parent / "analysis.db"
        self.db_path = str(db_path)
        self._init_database()

    # ─────────────────────────────────────────────────────────────────────────
    # Schema
    # ─────────────────────────────────────────────────────────────────────────

    def _init_database(self):
        """Create all tables if they don't exist."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.executescript("""
                CREATE TABLE IF NOT EXISTS patent_analyses (
                    id            TEXT PRIMARY KEY,
                    google_patent_id TEXT NOT NULL,
                    patent_data   TEXT,
                    search_plan   TEXT,
                    status        TEXT DEFAULT 'extracting',
                    error_message TEXT,
                    created_at    DATETIME,
                    updated_at    DATETIME
                );

                CREATE TABLE IF NOT EXISTS search_batches (
                    id            TEXT PRIMARY KEY,
                    analysis_id   TEXT NOT NULL,
                    batch_config  TEXT NOT NULL,
                    status        TEXT DEFAULT 'pending',
                    hit_count     INTEGER DEFAULT 0,
                    error_message TEXT,
                    created_at    DATETIME,
                    completed_at  DATETIME,
                    FOREIGN KEY (analysis_id) REFERENCES patent_analyses(id)
                );

                CREATE TABLE IF NOT EXISTS pdki_results (
                    id            TEXT PRIMARY KEY,
                    analysis_id   TEXT NOT NULL,
                    url           TEXT NOT NULL,
                    text          TEXT,
                    detail        TEXT,
                    found_by      TEXT,
                    category      TEXT,
                    created_at    DATETIME,
                    UNIQUE(analysis_id, url),
                    FOREIGN KEY (analysis_id) REFERENCES patent_analyses(id)
                );

                CREATE INDEX IF NOT EXISTS idx_analyses_updated
                    ON patent_analyses(updated_at);
                CREATE INDEX IF NOT EXISTS idx_batches_analysis
                    ON search_batches(analysis_id);
                CREATE INDEX IF NOT EXISTS idx_results_analysis
                    ON pdki_results(analysis_id);
            """)

            conn.commit()

            # Migrate: add new columns if they don't exist (safe on re-init)
            for alter_sql in [
                "ALTER TABLE patent_analyses ADD COLUMN sheet_url TEXT",
                "ALTER TABLE pdki_results ADD COLUMN reasoning TEXT",
                "ALTER TABLE pdki_results ADD COLUMN score INTEGER",
            ]:
                try:
                    cursor.execute(alter_sql)
                    conn.commit()
                except Exception:
                    pass  # Column already exists

            conn.close()
            logger.info(f"AnalysisDB initialised: {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialise AnalysisDB: {e}")
            raise

    # ─────────────────────────────────────────────────────────────────────────
    # patent_analyses helpers
    # ─────────────────────────────────────────────────────────────────────────

    def create_analysis(self, google_patent_id: str) -> str:
        """Insert a new analysis row with status='extracting'. Returns uuid."""
        analysis_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """INSERT INTO patent_analyses
                   (id, google_patent_id, status, created_at, updated_at)
                   VALUES (?, ?, 'extracting', ?, ?)""",
                (analysis_id, google_patent_id, now, now),
            )
            conn.commit()
        finally:
            conn.close()
        logger.info(f"Created analysis {analysis_id} for {google_patent_id}")
        return analysis_id

    def update_analysis_ready(
        self, analysis_id: str, patent_data: dict, search_plan: list
    ):
        """Mark analysis as ready and store extracted data + AI plan."""
        now = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """UPDATE patent_analyses
                   SET patent_data=?, search_plan=?, status='ready',
                       error_message=NULL, updated_at=?
                   WHERE id=?""",
                (
                    json.dumps(patent_data, ensure_ascii=False),
                    json.dumps(search_plan, ensure_ascii=False),
                    now,
                    analysis_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def update_analysis_error(self, analysis_id: str, error: str):
        """Mark analysis as error and store the error message."""
        now = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """UPDATE patent_analyses
                   SET status='error', error_message=?, updated_at=?
                   WHERE id=?""",
                (error, now, analysis_id),
            )
            conn.commit()
        finally:
            conn.close()

    def update_search_plan(self, analysis_id: str, search_plan: list):
        """Update search_plan only (user edited it)."""
        now = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """UPDATE patent_analyses
                   SET search_plan=?, updated_at=?
                   WHERE id=?""",
                (json.dumps(search_plan, ensure_ascii=False), now, analysis_id),
            )
            conn.commit()
        finally:
            conn.close()

    def get_analysis(self, analysis_id: str) -> Optional[Dict]:
        """Return a single analysis row with JSON fields parsed."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT * FROM patent_analyses WHERE id=?", (analysis_id,)
            ).fetchone()
        finally:
            conn.close()

        if not row:
            return None
        return self._parse_analysis_row(dict(row))

    def list_analyses(self) -> List[Dict]:
        """Return all analyses ordered by updated_at desc, with total_results count."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """SELECT a.*,
                          COUNT(r.id) AS total_results
                   FROM patent_analyses a
                   LEFT JOIN pdki_results r ON r.analysis_id = a.id
                   GROUP BY a.id
                   ORDER BY a.updated_at DESC"""
            ).fetchall()
        finally:
            conn.close()

        result = []
        for row in rows:
            d = self._parse_analysis_row(dict(row))
            result.append(d)
        return result

    def _parse_analysis_row(self, row: dict) -> dict:
        for field in ("patent_data", "search_plan"):
            if row.get(field):
                try:
                    row[field] = json.loads(row[field])
                except (json.JSONDecodeError, TypeError):
                    pass
        return row

    # ─────────────────────────────────────────────────────────────────────────
    # search_batches helpers
    # ─────────────────────────────────────────────────────────────────────────

    def create_batch(self, analysis_id: str, batch_config: dict) -> str:
        """Insert a new batch row with status='pending'. Returns uuid."""
        batch_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """INSERT INTO search_batches
                   (id, analysis_id, batch_config, status, hit_count, created_at)
                   VALUES (?, ?, ?, 'pending', 0, ?)""",
                (batch_id, analysis_id, json.dumps(batch_config, ensure_ascii=False), now),
            )
            conn.commit()
        finally:
            conn.close()
        logger.info(f"Created batch {batch_id} for analysis {analysis_id}")
        return batch_id

    def update_batch_status(
        self,
        batch_id: str,
        status: str,
        hit_count: Optional[int] = None,
        error: Optional[str] = None,
    ):
        """Update batch status; sets completed_at when status is completed/failed."""
        now = datetime.now().isoformat()
        terminal = status in ("completed", "failed")

        fields = ["status=?"]
        params: list = [status]

        if hit_count is not None:
            fields.append("hit_count=?")
            params.append(hit_count)

        if error is not None:
            fields.append("error_message=?")
            params.append(error)

        if terminal:
            fields.append("completed_at=?")
            params.append(now)

        params.append(batch_id)
        sql = f"UPDATE search_batches SET {', '.join(fields)} WHERE id=?"

        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(sql, params)
            conn.commit()
        finally:
            conn.close()

    def get_batch(self, batch_id: str) -> Optional[Dict]:
        """Return a single batch row with batch_config parsed."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT * FROM search_batches WHERE id=?", (batch_id,)
            ).fetchone()
        finally:
            conn.close()

        if not row:
            return None
        return self._parse_batch_row(dict(row))

    def list_batches(self, analysis_id: str) -> List[Dict]:
        """Return all batches for an analysis, newest first."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """SELECT * FROM search_batches
                   WHERE analysis_id=?
                   ORDER BY created_at DESC""",
                (analysis_id,),
            ).fetchall()
        finally:
            conn.close()

        return [self._parse_batch_row(dict(r)) for r in rows]

    def _parse_batch_row(self, row: dict) -> dict:
        if row.get("batch_config"):
            try:
                row["batch_config"] = json.loads(row["batch_config"])
            except (json.JSONDecodeError, TypeError):
                pass
        return row

    # ─────────────────────────────────────────────────────────────────────────
    # pdki_results helpers
    # ─────────────────────────────────────────────────────────────────────────

    def upsert_results(self, analysis_id: str, results: List[Dict]) -> Dict:
        """
        Insert new URLs; for duplicate URLs append tags to found_by.

        Each item in results must have:
          url   : str
          text  : str  (link label)
          tag   : str  (e.g. "title:valbenazine")
          detail: dict | None

        Returns {"new": int, "duplicates": int}.
        """
        now = datetime.now().isoformat()
        new_count = 0
        dup_count = 0

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            for item in results:
                url = item["url"]
                tag = item.get("tag", "")
                text = item.get("text", "")
                detail = item.get("detail")
                detail_json = json.dumps(detail, ensure_ascii=False) if detail else None

                existing = conn.execute(
                    "SELECT id, found_by FROM pdki_results WHERE analysis_id=? AND url=?",
                    (analysis_id, url),
                ).fetchone()

                if existing:
                    # Append tag if not already present
                    try:
                        found_by: list = json.loads(existing["found_by"] or "[]")
                    except (json.JSONDecodeError, TypeError):
                        found_by = []

                    if tag and tag not in found_by:
                        found_by.append(tag)
                        conn.execute(
                            "UPDATE pdki_results SET found_by=? WHERE id=?",
                            (json.dumps(found_by, ensure_ascii=False), existing["id"]),
                        )
                    dup_count += 1
                else:
                    found_by = [tag] if tag else []
                    conn.execute(
                        """INSERT INTO pdki_results
                           (id, analysis_id, url, text, detail, found_by, category, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, NULL, ?)""",
                        (
                            str(uuid.uuid4()),
                            analysis_id,
                            url,
                            text,
                            detail_json,
                            json.dumps(found_by, ensure_ascii=False),
                            now,
                        ),
                    )
                    new_count += 1

            # Bump analysis updated_at
            conn.execute(
                "UPDATE patent_analyses SET updated_at=? WHERE id=?",
                (now, analysis_id),
            )
            conn.commit()
        finally:
            conn.close()

        logger.info(
            f"upsert_results analysis={analysis_id}: new={new_count} dups={dup_count}"
        )
        return {"new": new_count, "duplicates": dup_count}

    def get_results(self, analysis_id: str) -> List[Dict]:
        """Return all results for an analysis with JSON fields parsed."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT * FROM pdki_results WHERE analysis_id=? ORDER BY created_at",
                (analysis_id,),
            ).fetchall()
        finally:
            conn.close()

        results = []
        for row in rows:
            d = dict(row)
            for field in ("detail", "found_by"):
                if d.get(field):
                    try:
                        d[field] = json.loads(d[field])
                    except (json.JSONDecodeError, TypeError):
                        pass
            results.append(d)
        return results

    def delete_analysis(self, analysis_id: str) -> bool:
        """Delete an analysis and all its batches and results. Returns True if found."""
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT id FROM patent_analyses WHERE id=?", (analysis_id,)
            ).fetchone()
            if not row:
                return False
            conn.execute("DELETE FROM pdki_results    WHERE analysis_id=?", (analysis_id,))
            conn.execute("DELETE FROM search_batches  WHERE analysis_id=?", (analysis_id,))
            conn.execute("DELETE FROM patent_analyses WHERE id=?",          (analysis_id,))
            conn.commit()
        finally:
            conn.close()
        logger.info(f"Deleted analysis {analysis_id} and all associated data")
        return True

    def update_analysis_sheet_url(self, analysis_id: str, sheet_url: str):
        """Store the Google Sheet URL for an analysis."""
        now = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "UPDATE patent_analyses SET sheet_url=?, updated_at=? WHERE id=?",
                (sheet_url, now, analysis_id),
            )
            conn.commit()
        finally:
            conn.close()

    def update_result_category(
        self,
        result_id: str,
        category: str,
        reasoning: Optional[str] = None,
        score: Optional[int] = None,
    ):
        """Update category (and optionally reasoning/score) for a single PDKI result."""
        fields = ["category=?"]
        params: list = [category]
        if reasoning is not None:
            fields.append("reasoning=?")
            params.append(reasoning)
        if score is not None:
            fields.append("score=?")
            params.append(score)
        params.append(result_id)
        sql = f"UPDATE pdki_results SET {', '.join(fields)} WHERE id=?"
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(sql, params)
            conn.commit()
        finally:
            conn.close()

    def get_uncategorized_results(self, analysis_id: str) -> List[Dict]:
        """Return results for an analysis where category IS NULL."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT * FROM pdki_results WHERE analysis_id=? AND category IS NULL ORDER BY created_at",
                (analysis_id,),
            ).fetchall()
        finally:
            conn.close()

        results = []
        for row in rows:
            d = dict(row)
            for field in ("detail", "found_by"):
                if d.get(field):
                    try:
                        d[field] = json.loads(d[field])
                    except (json.JSONDecodeError, TypeError):
                        pass
            results.append(d)
        return results

    def has_running_batch(self, analysis_id: str) -> bool:
        """Return True if any batch for this analysis is currently running."""
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT id FROM search_batches WHERE analysis_id=? AND status IN ('pending','running')",
                (analysis_id,),
            ).fetchone()
        finally:
            conn.close()
        return row is not None

    def get_stats(self, analysis_id: str) -> Dict:
        """Return analysis stats: total, analyzed, unanalyzed, relevant, not_relevant, uncertain."""
        conn = sqlite3.connect(self.db_path)
        try:
            total = conn.execute(
                "SELECT COUNT(*) FROM pdki_results WHERE analysis_id=?",
                (analysis_id,),
            ).fetchone()[0]

            relevant = conn.execute(
                "SELECT COUNT(*) FROM pdki_results WHERE analysis_id=? AND category='relevant'",
                (analysis_id,),
            ).fetchone()[0]

            not_relevant = conn.execute(
                "SELECT COUNT(*) FROM pdki_results WHERE analysis_id=? AND category='not_relevant'",
                (analysis_id,),
            ).fetchone()[0]

            uncertain = conn.execute(
                "SELECT COUNT(*) FROM pdki_results WHERE analysis_id=? AND category='uncertain'",
                (analysis_id,),
            ).fetchone()[0]
        finally:
            conn.close()

        analyzed = relevant + not_relevant + uncertain
        unanalyzed = total - analyzed

        return {
            "total": total,
            "analyzed": analyzed,
            "unanalyzed": unanalyzed,
            "relevant": relevant,
            "not_relevant": not_relevant,
            "uncertain": uncertain,
        }
