"""Accès SQLite idempotent (protocole §4, §0.4).

Usage :
    python -m src.storage.database init   (§16)
    python -m src.storage.database path
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


class Database:
    """Enveloppe SQLite avec initialisation idempotente.

    Relancer `init()` ne duplique rien : toutes les tables utilisent
    IF NOT EXISTS et les insertions passent par des upserts déterministes.
    """

    def __init__(self, db_path: str | Path = "data/laya_experiment.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")

    # --- cycle de vie -------------------------------------------------------

    def init(self) -> int:
        """Crée le schéma si nécessaire ; renvoie le nombre de tables."""
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        self.conn.executescript(schema)
        self.conn.commit()
        rows = self.conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchone()
        return int(rows[0])

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # --- insertions idempotentes (§0.4) -------------------------------------

    def upsert(self, table: str, record: dict[str, Any]) -> None:
        """Insertion-or-ignore + update : relancer n'altère pas les lignes validées."""
        if not record:
            raise ValueError("enregistrement vide")
        cols = ", ".join(record)
        placeholders = ", ".join("?" for _ in record)
        updates = ", ".join(f"{c}=excluded.{c}" for c in record if c != f"{_pk(table)}")
        if updates:
            sql = (
                f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) "
                f"ON CONFLICT({_pk(table)}) DO UPDATE SET {updates}"
            )
        else:
            sql = f"INSERT OR IGNORE INTO {table} ({cols}) VALUES ({placeholders})"
        self.conn.execute(sql, tuple(record.values()))
        self.conn.commit()

    def executemany(self, sql: str, rows: list[tuple[Any, ...]]) -> None:
        self.conn.executemany(sql, rows)
        self.conn.commit()

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        cur = self.conn.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]

    def count(self, table: str) -> int:
        return int(self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def _pk(table: str) -> str:
    """Clé primaire canonique de chaque table (§4.2)."""
    return {
        "matches": "match_id",
        "match_events": "event_id",
        "match_statistics": "stat_id",
        "pre_match_context": "pre_match_id",
        "match_snapshots": "snapshot_id",
        "laya_predictions": "prediction_id",
        "evaluation": "evaluation_id",
    }[table]


# --- requêtes point-in-time (§5.2, §5.3) -----------------------------------

PRE_MATCH_WINDOW_SQL = """
SELECT * FROM {table}
WHERE available_timestamp < :pre_match_cutoff
  AND match_id <> :current_match_id
"""

LIVE_WINDOW_SQL = """
SELECT * FROM match_statistics
WHERE match_id = :match_id
  AND available_timestamp <= :cutoff_timestamp
  AND elapsed_seconds <= :cutoff_seconds
"""


def pre_match_window(db: Database, table: str, pre_match_cutoff: str, current_match_id: str) -> list[dict[str, Any]]:
    """Vue temporelle du bloc pré-match (§5.2) — jamais un filtre saison entière."""
    sql = PRE_MATCH_WINDOW_SQL.format(table=table)
    return db.query(sql, {"pre_match_cutoff": pre_match_cutoff, "current_match_id": current_match_id})


def live_window(
    db: Database, match_id: str, cutoff_timestamp: str, cutoff_seconds: int
) -> list[dict[str, Any]]:
    """Vue temporelle live (§5.3) : disponible <= cutoff, elapsed <= cutoff."""
    return db.query(
        LIVE_WINDOW_SQL,
        {
            "match_id": match_id,
            "cutoff_timestamp": cutoff_timestamp,
            "cutoff_seconds": cutoff_seconds,
        },
    )


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    command = argv[0] if argv else "init"
    if command == "init":
        db_path = argv[1] if len(argv) > 1 else "data/laya_experiment.db"
        n = Database(db_path).init()
        print(f"[database] schéma initialisé : {n} tables — {db_path}")
        return 0
    if command == "path":
        print(SCHEMA_PATH)
        return 0
    print("usage: python -m src.storage.database [init [path] | path]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

# Alias utilisé par les tests de sérialisation JSON
json_dumps = json.dumps
