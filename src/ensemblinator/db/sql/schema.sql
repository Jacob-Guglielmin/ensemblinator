CREATE TABLE jobs (
    job_id TEXT PRIMARY_KEY,
    file_hash TEXT NOT NULL,
    executable_path TEXT NOT NULL,
    schedules TEXT NOT NULL, -- JSON array of strings
    timeout REAL NOT NULL,
    requirements TEXT NOT NULL -- JSON array of strings
);

CREATE TABLE job_runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    started_at REAL NOT NULL,
    finished_at REAL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'success', 'failure', 'skipped', 'interrupted')),
    exit_code INTEGER,
    trigger TEXT NOT NULL,
    skip_reason TEXT
);

CREATE TABLE job_run_logs (
    run_id INTEGER PRIMARY KEY REFERENCES job_runs(run_id),
    content TEXT NOT NULL
);

CREATE TABLE job_state (
    job_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY (job_id, key)
);