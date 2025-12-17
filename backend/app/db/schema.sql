PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS period (
  id INTEGER PRIMARY KEY,
  period_start TEXT NOT NULL,
  period_end TEXT NOT NULL,
  currency TEXT,
  UNIQUE(period_start, period_end)
);

CREATE TABLE IF NOT EXISTS raw_metric_value (
  id INTEGER PRIMARY KEY,
  period_id INTEGER NOT NULL,
  source TEXT NOT NULL,
  metric TEXT NOT NULL,
  value REAL NOT NULL,
  UNIQUE(period_id, source, metric),
  FOREIGN KEY(period_id) REFERENCES period(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS raw_line_item_value (
  id INTEGER PRIMARY KEY,
  period_id INTEGER NOT NULL,
  source TEXT NOT NULL,
  category TEXT NOT NULL,
  path TEXT NOT NULL,
  name TEXT NOT NULL,
  account_id TEXT,
  value REAL NOT NULL,
  UNIQUE(period_id, source, category, path),
  FOREIGN KEY(period_id) REFERENCES period(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS metric_value (
  id INTEGER PRIMARY KEY,
  period_id INTEGER NOT NULL,
  metric TEXT NOT NULL,
  value REAL NOT NULL,
  provenance TEXT NOT NULL,
  UNIQUE(period_id, metric),
  FOREIGN KEY(period_id) REFERENCES period(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS line_item_value (
  id INTEGER PRIMARY KEY,
  period_id INTEGER NOT NULL,
  category TEXT NOT NULL,
  path TEXT NOT NULL,
  name TEXT NOT NULL,
  account_id TEXT,
  value REAL NOT NULL,
  provenance TEXT NOT NULL,
  UNIQUE(period_id, category, path),
  FOREIGN KEY(period_id) REFERENCES period(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS chat_session (
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_message (
  id INTEGER PRIMARY KEY,
  session_id TEXT NOT NULL,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(session_id) REFERENCES chat_session(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ingestion_run (
  id INTEGER PRIMARY KEY,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  mode TEXT NOT NULL,
  primary_source TEXT NOT NULL,
  tolerance REAL NOT NULL,
  status TEXT NOT NULL,
  details TEXT
);

CREATE TABLE IF NOT EXISTS ingestion_issue (
  id INTEGER PRIMARY KEY,
  run_id INTEGER NOT NULL,
  level TEXT NOT NULL,
  source TEXT,
  period_id INTEGER,
  metric TEXT,
  message TEXT NOT NULL,
  details TEXT,
  FOREIGN KEY(run_id) REFERENCES ingestion_run(id) ON DELETE CASCADE,
  FOREIGN KEY(period_id) REFERENCES period(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_period_start ON period(period_start);
CREATE INDEX IF NOT EXISTS idx_raw_metric_metric ON raw_metric_value(metric);
CREATE INDEX IF NOT EXISTS idx_metric_metric ON metric_value(metric);
CREATE INDEX IF NOT EXISTS idx_line_item_category ON line_item_value(category);
CREATE INDEX IF NOT EXISTS idx_line_item_path ON line_item_value(path);
