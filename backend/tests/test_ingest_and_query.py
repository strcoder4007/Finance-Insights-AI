from __future__ import annotations

import sqlite3
from pathlib import Path

from app.core.settings import Settings
from app.db.sqlite import init_db
from app.services.ingest_service import IngestService
from app.services.query_service import QueryService


def test_ingest_builds_canonical_tables(tmp_path: Path):
    db_path = tmp_path / "test.db"
    init_db(str(db_path))
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")

    root = Path(__file__).resolve().parents[2]
    settings = Settings(
        DB_PATH=str(db_path),
        DATA1_PATH=str(root / "data1.json"),
        DATA2_PATH=str(root / "data2.json"),
        PRIMARY_SOURCE="rootfi",
        MERGE_TOLERANCE=1.0,
    )

    stats = IngestService(settings).ingest(conn, mode="replace")
    assert stats["status"] == "ok"

    qs = QueryService(conn)
    res = qs.metric_timeseries(metric="net_income", start=None, end=None, group_by="month", include_provenance=True)
    assert res["series"]

