"""SQLite 数据库服务。

用于持久化保存市场分析报告，并提供历史查询能力。
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


class DatabaseService:
    """数据库操作服务。"""

    def __init__(self, db_path: str = "backend/data/reports.db"):
        self.db_path = Path(db_path)
        self._lock = threading.Lock()
        self._initialized = False

    def init_db(self) -> None:
        """初始化数据库与数据表。"""
        with self._lock:
            if self._initialized:
                return
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with self._get_connection() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS reports (
                        id TEXT PRIMARY KEY,
                        query TEXT NOT NULL,
                        location TEXT,
                        max_results INTEGER NOT NULL,
                        report TEXT NOT NULL,
                        market_insights TEXT NOT NULL,
                        jobs TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_reports_created_at
                    ON reports(created_at DESC)
                    """
                )
                conn.commit()
            self._initialized = True

    def save_report(
        self,
        query: str,
        location: Optional[str],
        max_results: int,
        report: str,
        market_insights: dict[str, Any],
        jobs: list[dict[str, Any]],
    ) -> str:
        """保存报告并返回报告 ID。"""
        report_id = f"r-{uuid.uuid4().hex[:16]}"
        created_at = datetime.now().isoformat(timespec="seconds")
        self.init_db()

        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO reports (id, query, location, max_results, report, market_insights, jobs, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        report_id,
                        query,
                        location or "",
                        int(max_results),
                        report,
                        json.dumps(market_insights, ensure_ascii=False),
                        json.dumps(jobs, ensure_ascii=False),
                        created_at,
                    ),
                )
                conn.commit()

        return report_id

    def list_reports(self, limit: int = 20, offset: int = 0) -> list[dict[str, Any]]:
        """按时间倒序返回报告列表。"""
        self.init_db()
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, query, location, max_results, created_at, market_insights
                FROM reports
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (int(limit), int(offset)),
            ).fetchall()

        reports: list[dict[str, Any]] = []
        for row in rows:
            insights = self._safe_load_json(row[5], default={})
            results_count = 0
            try:
                results_count = int(insights.get("total_jobs", 0))
            except (TypeError, ValueError, AttributeError):
                results_count = 0

            reports.append(
                {
                    "id": row[0],
                    "query": row[1],
                    "location": row[2] or "",
                    "max_results": int(row[3]),
                    "created_at": row[4],
                    "results_count": results_count,
                }
            )

        return reports

    def count_reports(self) -> int:
        """返回报告总数。"""
        self.init_db()
        with self._get_connection() as conn:
            row = conn.execute("SELECT COUNT(1) FROM reports").fetchone()
        return int(row[0]) if row else 0

    def get_report(self, report_id: str) -> Optional[dict[str, Any]]:
        """按 ID 获取完整报告。"""
        self.init_db()
        with self._get_connection() as conn:
            row = conn.execute(
                """
                SELECT id, query, location, max_results, report, market_insights, jobs, created_at
                FROM reports
                WHERE id = ?
                """,
                (report_id,),
            ).fetchone()

        if not row:
            return None

        return {
            "id": row[0],
            "query": row[1],
            "location": row[2] or "",
            "max_results": int(row[3]),
            "report": row[4],
            "market_insights": self._safe_load_json(row[5], default={}),
            "jobs": self._safe_load_json(row[6], default=[]),
            "created_at": row[7],
        }

    def _get_connection(self) -> sqlite3.Connection:
        """创建数据库连接。"""
        return sqlite3.connect(self.db_path)

    @staticmethod
    def _safe_load_json(raw: str, default: Any) -> Any:
        """安全解析 JSON 字符串。"""
        try:
            return json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return default


# 模块级单例，避免重复初始化连接配置
_db_service = DatabaseService()


def get_database_service() -> DatabaseService:
    """获取数据库服务单例。"""
    return _db_service
