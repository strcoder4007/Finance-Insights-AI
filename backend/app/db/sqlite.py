from __future__ import annotations

import sqlite3
from collections.abc import Generator
from pathlib import Path

from fastapi import Depends

from app.core.settings import Settings, get_settings


def connect(db_path: str) -> sqlite3.Connection:
    path = Path(db_path)
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: str) -> None:
    conn = connect(db_path)
    try:
        schema_path = Path(__file__).resolve().parent / "schema.sql"
        conn.executescript(schema_path.read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()


def get_db(settings: Settings = Depends(get_settings)) -> Generator[sqlite3.Connection, None, None]:
    conn = connect(settings.db_path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

