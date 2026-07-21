PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS audit_execution (
    execution_id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    question_sha256 TEXT NOT NULL,
    question_spec_json TEXT NOT NULL,
    generated_sql TEXT,
    status TEXT NOT NULL,
    row_count INTEGER NOT NULL,
    llm_provider TEXT NOT NULL
);

