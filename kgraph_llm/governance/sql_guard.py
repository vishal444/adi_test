from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterable


class UnsafeSQL(ValueError):
    pass


class SQLGuard:
    """A deliberately narrow safety gate for model-proposed SQLite queries."""

    FORBIDDEN = re.compile(
        r"\b(insert|update|delete|replace|drop|alter|create|attach|detach|pragma|"
        r"vacuum|reindex|analyze|load_extension|begin|commit|rollback|savepoint|release)\b",
        re.IGNORECASE,
    )
    TABLE_REF = re.compile(r"\b(?:from|join)\s+([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE)
    CTE_REF = re.compile(r"(?:\bwith|,)\s*([A-Za-z_][A-Za-z0-9_]*)\s+as\s*\(", re.IGNORECASE)
    FROM_CLAUSE = re.compile(
        r"\bfrom\b(.*?)(?=\bwhere\b|\bgroup\s+by\b|\border\s+by\b|\bhaving\b|"
        r"\blimit\b|\bunion\b|$)",
        re.IGNORECASE | re.DOTALL,
    )

    def __init__(self, allowed_datasets: Iterable[str]):
        self.allowed_datasets = set(allowed_datasets)

    def validate(
        self,
        sql: str,
        parameters: Iterable[object],
        connection: sqlite3.Connection,
    ) -> str:
        statement = sql.strip()
        if statement.endswith(";"):
            statement = statement[:-1].rstrip()
        if not statement:
            raise UnsafeSQL("The generated SQL is empty.")
        if ";" in statement:
            raise UnsafeSQL("Only one SQL statement is allowed.")
        if "--" in statement or "/*" in statement or "*/" in statement:
            raise UnsafeSQL("SQL comments are not allowed.")
        if any(character in statement for character in ('"', "'", "`", "[", "]")):
            raise UnsafeSQL("Quoted identifiers and literal values are not allowed; bind values as parameters.")
        if not re.match(r"^(select|with)\b", statement, re.IGNORECASE):
            raise UnsafeSQL("Only SELECT or WITH queries are allowed.")
        if self.FORBIDDEN.search(statement):
            raise UnsafeSQL("The query contains a forbidden SQL operation.")
        if any("," in match.group(1) for match in self.FROM_CLAUSE.finditer(statement)):
            raise UnsafeSQL("Comma joins are not allowed; use an explicit JOIN clause.")

        ctes = set(self.CTE_REF.findall(statement))
        referenced = set(self.TABLE_REF.findall(statement)) - ctes
        disallowed = referenced - self.allowed_datasets
        if disallowed:
            raise UnsafeSQL(f"Query references unapproved datasets: {sorted(disallowed)}")
        if not referenced:
            raise UnsafeSQL("Query must use at least one approved dataset.")

        try:
            connection.execute(f"EXPLAIN QUERY PLAN {statement}", tuple(parameters)).fetchall()
        except sqlite3.Error as exc:
            raise UnsafeSQL(f"SQL failed pre-execution validation: {exc}") from exc
        return statement

    def runtime_read_sources(self, sql: str) -> set[str]:
        """Objects the SQLite authorizer may observe for an already validated query."""
        return self.allowed_datasets | set(self.CTE_REF.findall(sql))
