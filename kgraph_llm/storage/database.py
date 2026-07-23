from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
BASE_SCHEMA_PATH = PACKAGE_ROOT / "storage" / "sql" / "schema.sql"


class Database:
    """Owns database setup, guarded reads, and minimal audit metadata."""

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser().resolve()

    def initialize(self, *, reset: bool = False) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if reset and self.path.exists():
            self.path.unlink()
        from ..ministries.registry import active_ministries

        with sqlite3.connect(self.path) as connection:
            connection.executescript(BASE_SCHEMA_PATH.read_text(encoding="utf-8"))
            self._migrate_legacy_health_hospital(connection)
            for ministry in active_ministries():
                for script in ministry.bootstrap_scripts:
                    connection.executescript(script.read_text(encoding="utf-8"))

    @staticmethod
    def _migrate_legacy_health_hospital(connection: sqlite3.Connection) -> None:
        """Upgrade the mutable compatibility identity before health seeds run."""
        table_exists = connection.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = 'hospital'
            """
        ).fetchone()
        if table_exists is None:
            return

        columns = {
            str(row[1]) for row in connection.execute("PRAGMA table_info(hospital)")
        }
        if "master_facility_id" not in columns:
            connection.execute(
                """
                ALTER TABLE hospital
                ADD COLUMN master_facility_id INTEGER
                    REFERENCES master_facility(facility_id)
                """
            )
        if "effective_from" in columns:
            connection.execute("ALTER TABLE hospital DROP COLUMN effective_from")
        if "effective_to" in columns:
            connection.execute("ALTER TABLE hospital DROP COLUMN effective_to")

    def exists(self) -> bool:
        return self.path.exists()

    def read_connection(self, allowed_read_objects: set[str] | None = None) -> sqlite3.Connection:
        connection = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        denied = {
            sqlite3.SQLITE_INSERT,
            sqlite3.SQLITE_UPDATE,
            sqlite3.SQLITE_DELETE,
            sqlite3.SQLITE_CREATE_INDEX,
            sqlite3.SQLITE_CREATE_TABLE,
            sqlite3.SQLITE_CREATE_TEMP_INDEX,
            sqlite3.SQLITE_CREATE_TEMP_TABLE,
            sqlite3.SQLITE_CREATE_TEMP_TRIGGER,
            sqlite3.SQLITE_CREATE_TEMP_VIEW,
            sqlite3.SQLITE_CREATE_TRIGGER,
            sqlite3.SQLITE_CREATE_VIEW,
            sqlite3.SQLITE_DROP_INDEX,
            sqlite3.SQLITE_DROP_TABLE,
            sqlite3.SQLITE_DROP_TEMP_INDEX,
            sqlite3.SQLITE_DROP_TEMP_TABLE,
            sqlite3.SQLITE_DROP_TEMP_TRIGGER,
            sqlite3.SQLITE_DROP_TEMP_VIEW,
            sqlite3.SQLITE_DROP_TRIGGER,
            sqlite3.SQLITE_DROP_VIEW,
            sqlite3.SQLITE_ALTER_TABLE,
            sqlite3.SQLITE_ATTACH,
            sqlite3.SQLITE_DETACH,
        }

        def authorize(action: int, arg1: str, _arg2: str, _db: str, source: str) -> int:
            if action in denied:
                return sqlite3.SQLITE_DENY
            if action == sqlite3.SQLITE_READ and allowed_read_objects is not None:
                # Reads inside an approved view identify that view in `source`.
                if arg1 not in allowed_read_objects and source not in allowed_read_objects:
                    return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        connection.set_authorizer(authorize)
        return connection

    def execute_read(
        self,
        sql: str,
        parameters: Iterable[Any],
        *,
        allowed_read_objects: set[str],
        row_limit: int = 100,
        vm_step_limit: int = 2_500_000,
    ) -> tuple[dict[str, Any], ...]:
        wrapped = f"SELECT * FROM ({sql}) AS governed_result LIMIT ?"
        steps = 0

        def progress() -> int:
            nonlocal steps
            steps += 1_000
            return 1 if steps > vm_step_limit else 0

        with self.read_connection(allowed_read_objects) as connection:
            connection.set_progress_handler(progress, 1_000)
            cursor = connection.execute(wrapped, (*parameters, row_limit))
            return tuple(dict(row) for row in cursor.fetchall())

    def record_audit(
        self,
        *,
        question: str,
        question_spec: dict[str, Any],
        sql: str | None,
        status: str,
        row_count: int,
        provider: str,
        provenance: dict[str, Any] | None = None,
    ) -> None:
        question_hash = hashlib.sha256(question.encode("utf-8")).hexdigest()
        with sqlite3.connect(self.path) as connection:
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(audit_execution)")
            }
            if "provenance_json" not in columns:
                connection.execute(
                    "ALTER TABLE audit_execution ADD COLUMN provenance_json TEXT NOT NULL DEFAULT '{}'"
                )
            connection.execute(
                """
                INSERT INTO audit_execution
                    (question_sha256, question_spec_json, generated_sql, status,
                     row_count, llm_provider, provenance_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    question_hash,
                    json.dumps(question_spec, sort_keys=True),
                    sql,
                    status,
                    row_count,
                    provider,
                    json.dumps(provenance or {}, sort_keys=True),
                ),
            )
