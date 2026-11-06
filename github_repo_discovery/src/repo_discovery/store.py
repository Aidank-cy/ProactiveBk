import json
import sqlite3
from pathlib import Path


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("CREATE TABLE IF NOT EXISTS repositories (id INTEGER PRIMARY KEY, data TEXT NOT NULL, pr_count INTEGER, issue_count INTEGER, license_spdx TEXT, license_status TEXT, license_name TEXT, license_source_url TEXT, error TEXT)")
        self.db.execute("CREATE TABLE IF NOT EXISTS partitions (key TEXT PRIMARY KEY, start TEXT, end TEXT, star_min INTEGER, star_max INTEGER, total_count INTEGER, incomplete INTEGER, status TEXT, error TEXT)")
        self.db.commit()

    def partition(self, key, start, end, star_min, star_max, total_count, incomplete, status, error=None):
        self.db.execute("INSERT OR REPLACE INTO partitions VALUES (?,?,?,?,?,?,?,?,?)", (key, start, end, star_min, star_max, total_count, int(incomplete), status, error))
        self.db.commit()

    def partition_status(self, key):
        row = self.db.execute("SELECT status FROM partitions WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def add_repos(self, items):
        self.db.executemany("INSERT OR IGNORE INTO repositories (id,data) VALUES (?,?)", [(x["id"], json.dumps(x, sort_keys=True)) for x in items])
        self.db.commit()

    def update(self, repo_id, **fields):
        assert fields and set(fields) <= {"pr_count", "issue_count", "license_spdx", "license_status", "license_name", "license_source_url", "error"}
        sql = "UPDATE repositories SET " + ", ".join(f"{k}=?" for k in fields) + " WHERE id=?"
        self.db.execute(sql, [*fields.values(), repo_id])
        self.db.commit()

    def rows(self):
        columns = [x[1] for x in self.db.execute("PRAGMA table_info(repositories)")]
        for row in self.db.execute("SELECT * FROM repositories ORDER BY id"):
            yield dict(zip(columns, row))
