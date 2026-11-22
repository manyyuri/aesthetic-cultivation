PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS issues (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  issue_no INTEGER NOT NULL UNIQUE,
  publish_date TEXT NOT NULL,
  title TEXT NOT NULL,
  subtitle TEXT NOT NULL,
  minutes INTEGER NOT NULL,
  status TEXT NOT NULL,
  generated_at TEXT,
  delivered_at TEXT,
  cover_json TEXT,
  meta_json TEXT
);

CREATE TABLE IF NOT EXISTS items (
  id TEXT PRIMARY KEY,
  issue_id TEXT NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
  ord INTEGER NOT NULL,
  domain TEXT NOT NULL,
  title_zh TEXT NOT NULL,
  title_orig TEXT,
  meta_json TEXT NOT NULL,
  hook TEXT NOT NULL,
  anchor_json TEXT NOT NULL,
  evidence_json TEXT NOT NULL,
  image_url TEXT,
  done_at TEXT,
  rank_score REAL NOT NULL DEFAULT 0,
  UNIQUE (issue_id, ord)
);

CREATE TABLE IF NOT EXISTS subscriptions (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  time_of_day TEXT NOT NULL,
  channels_json TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1,
  streak INTEGER NOT NULL DEFAULT 0,
  last_done_date TEXT
);

CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  subject_id TEXT,
  status TEXT NOT NULL,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  budget_json TEXT,
  usage_json TEXT,
  error TEXT
);

CREATE TABLE IF NOT EXISTS steps (
  run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  seq INTEGER NOT NULL,
  step TEXT NOT NULL,
  status TEXT NOT NULL,
  latency_ms INTEGER NOT NULL DEFAULT 0,
  tokens_in INTEGER NOT NULL DEFAULT 0,
  tokens_out INTEGER NOT NULL DEFAULT 0,
  payload_json TEXT,
  ts TEXT NOT NULL,
  PRIMARY KEY (run_id, seq)
);

CREATE TABLE IF NOT EXISTS feedback (
  id TEXT PRIMARY KEY,
  item_id TEXT,
  run_id TEXT,
  domain TEXT,
  verdict TEXT NOT NULL,
  note TEXT,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_items_domain ON items(domain);
CREATE INDEX IF NOT EXISTS idx_issues_date ON issues(publish_date);
CREATE INDEX IF NOT EXISTS idx_steps_run ON steps(run_id, seq);
