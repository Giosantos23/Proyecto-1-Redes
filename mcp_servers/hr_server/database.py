from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE = PROJECT_ROOT / "data" / "hr.sqlite3"
SCHEMA_FILE = Path(__file__).with_name("schema.sql")
SEED_FILE = Path(__file__).with_name("seed.sql")


class HRDatabase:

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.getenv(
            "HR_DATABASE_URL", f"sqlite:///{DEFAULT_DATABASE}"
        )
        if not self.database_url.startswith("sqlite:///"):
            raise ValueError(
                f"Error en Base de datos."
            )
        self.path = Path(self.database_url.removeprefix("sqlite:///"))
        if not self.path.is_absolute():
            self.path = PROJECT_ROOT / self.path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        schema = SCHEMA_FILE.read_text(encoding="utf-8")
        seed = SEED_FILE.read_text(encoding="utf-8")
        with self.connect() as connection:
            connection.executescript(schema)
            connection.executescript(seed)

    @staticmethod
    def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
        return dict(row) if row is not None else None

    def find_employee(self, employee_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT employee_id, full_name, department, job_title, email,
                        phone, manager_id, employment_status
                   FROM employees WHERE employee_id = ?""",
                (employee_id,),
            ).fetchone()
            return self._row_to_dict(row)

    def search_directory(self, query: str) -> list[dict[str, Any]]:
        pattern = f"%{query.strip()}%"
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT employee_id, full_name, department, job_title, email,
                        phone, manager_id, employment_status
                   FROM employees
                   WHERE full_name LIKE ? OR department LIKE ? OR email LIKE ?
                   ORDER BY full_name""",
                (pattern, pattern, pattern),
            ).fetchall()
            return [dict(row) for row in rows]

    def vacation_balance(self, employee_id: str, year: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT v.employee_id, e.full_name, v.year, v.entitled_days,
                        v.used_days, (v.entitled_days - v.used_days) AS available_days
                   FROM vacation_balances v
                   JOIN employees e ON e.employee_id = v.employee_id
                   WHERE v.employee_id = ? AND v.year = ?""",
                (employee_id, year),
            ).fetchone()
            return self._row_to_dict(row)

    def create_leave_request(
        self,
        employee_id: str,
        start_date: str,
        end_date: str,
        reason: str,
    ) -> dict[str, Any]:
        with self.connect() as connection:
            cursor = connection.execute(
                """INSERT INTO leave_requests
                   (employee_id, start_date, end_date, reason)
                   VALUES (?, ?, ?, ?)""",
                (employee_id, start_date, end_date, reason),
            )
            row = connection.execute(
                """SELECT request_id, employee_id, start_date, end_date,
                        reason, status, created_at
                   FROM leave_requests WHERE request_id = ?""",
                (cursor.lastrowid,),
            ).fetchone()
            return dict(row)
