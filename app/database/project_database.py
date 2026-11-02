"""
Project storage and recent project history management using SQLite.
"""
import os
import sqlite3
import json
from typing import List, Dict, Any, Optional
from app.database.component_database import get_db_path

DEFAULT_PROJ_DB = get_db_path("projects_history.db")


class ProjectDatabase:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path if db_path is not None else get_db_path("projects_history.db")
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS recent_projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    file_path TEXT NOT NULL UNIQUE,
                    requirement TEXT,
                    enclosure_dims TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_opened TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def record_project(self, name: str, file_path: str, requirement: str = "", enclosure_dims: str = ""):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO recent_projects (name, file_path, requirement, enclosure_dims, last_opened)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(file_path) DO UPDATE SET
                    name=excluded.name,
                    requirement=excluded.requirement,
                    enclosure_dims=excluded.enclosure_dims,
                    last_opened=CURRENT_TIMESTAMP
            """, (name, file_path, requirement, enclosure_dims))
            conn.commit()

    def get_recent_projects(self, limit: int = 10) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM recent_projects
                ORDER BY last_opened DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

