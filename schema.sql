-- Mirrors the artifact `db` collections described in HANDOFF.md §4.

CREATE TABLE IF NOT EXISTS users (
  id     TEXT PRIMARY KEY,
  name   TEXT NOT NULL,
  email  TEXT NOT NULL UNIQUE,          -- UNIQUE fixes the duplicate-account bug (HANDOFF §6)
  role   TEXT NOT NULL CHECK (role IN ('admin','annotator'))
);

CREATE TABLE IF NOT EXISTS videos (
  id      TEXT PRIMARY KEY,
  name    TEXT NOT NULL,
  dur     REAL    DEFAULT 0,
  size    INTEGER DEFAULT 0,
  added   INTEGER NOT NULL,
  thumb   TEXT,                          -- base64 JPEG data URL
  r2_key  TEXT                           -- object key in inoue-new-videos
);

CREATE TABLE IF NOT EXISTS tasks (
  id       TEXT PRIMARY KEY,
  video_id TEXT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
  user_id  TEXT REFERENCES users(id) ON DELETE SET NULL,
  status   TEXT NOT NULL CHECK (status IN ('todo','doing','done')),
  created  INTEGER NOT NULL,
  updated  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS tasks_user ON tasks(user_id);
CREATE INDEX IF NOT EXISTS tasks_video ON tasks(video_id);

-- One row per annotation span, rather than one JSON doc per task.
-- Lets two annotators work the same video without last-writer-wins clobbering.
CREATE TABLE IF NOT EXISTS anns (
  id       TEXT PRIMARY KEY,
  task_id  TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  t_start  REAL NOT NULL,
  t_end    REAL NOT NULL,
  caption  TEXT NOT NULL DEFAULT '',
  at       INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS anns_task ON anns(task_id, t_start);
