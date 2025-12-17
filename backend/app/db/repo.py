from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clear_financial_data(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DELETE FROM ingestion_issue;
        DELETE FROM ingestion_run;
        DELETE FROM raw_line_item_value;
        DELETE FROM raw_metric_value;
        DELETE FROM line_item_value;
        DELETE FROM metric_value;
        DELETE FROM period;
        """
    )


def clear_canonical_data(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DELETE FROM line_item_value;
        DELETE FROM metric_value;
        """
    )


def upsert_period(conn: sqlite3.Connection, period_start: str, period_end: str, currency: str | None) -> int:
    conn.execute(
        """
        INSERT INTO period(period_start, period_end, currency)
        VALUES (?, ?, ?)
        ON CONFLICT(period_start, period_end) DO UPDATE SET
          currency = COALESCE(period.currency, excluded.currency)
        """,
        (period_start, period_end, currency),
    )
    row = conn.execute(
        "SELECT id FROM period WHERE period_start = ? AND period_end = ?",
        (period_start, period_end),
    ).fetchone()
    assert row is not None
    return int(row["id"])


def upsert_raw_metric(
    conn: sqlite3.Connection, period_id: int, source: str, metric: str, value: float
) -> None:
    conn.execute(
        """
        INSERT INTO raw_metric_value(period_id, source, metric, value)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(period_id, source, metric) DO UPDATE SET
          value = excluded.value
        """,
        (period_id, source, metric, value),
    )


def upsert_raw_line_item(
    conn: sqlite3.Connection,
    period_id: int,
    source: str,
    category: str,
    path: str,
    name: str,
    account_id: str | None,
    value: float,
) -> None:
    conn.execute(
        """
        INSERT INTO raw_line_item_value(period_id, source, category, path, name, account_id, value)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(period_id, source, category, path) DO UPDATE SET
          name = excluded.name,
          account_id = excluded.account_id,
          value = excluded.value
        """,
        (period_id, source, category, path, name, account_id, value),
    )


def upsert_metric_value(
    conn: sqlite3.Connection, period_id: int, metric: str, value: float, provenance: str
) -> None:
    conn.execute(
        """
        INSERT INTO metric_value(period_id, metric, value, provenance)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(period_id, metric) DO UPDATE SET
          value = excluded.value,
          provenance = excluded.provenance
        """,
        (period_id, metric, value, provenance),
    )


def upsert_line_item_value(
    conn: sqlite3.Connection,
    period_id: int,
    category: str,
    path: str,
    name: str,
    account_id: str | None,
    value: float,
    provenance: str,
) -> None:
    conn.execute(
        """
        INSERT INTO line_item_value(period_id, category, path, name, account_id, value, provenance)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(period_id, category, path) DO UPDATE SET
          name = excluded.name,
          account_id = excluded.account_id,
          value = excluded.value,
          provenance = excluded.provenance
        """,
        (period_id, category, path, name, account_id, value, provenance),
    )


def list_periods(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(conn.execute("SELECT id, period_start, period_end, currency FROM period ORDER BY period_start"))


def list_periods_with_sources(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """
            SELECT
              p.id,
              p.period_start,
              p.period_end,
              p.currency,
              GROUP_CONCAT(DISTINCT rm.source) AS sources
            FROM period p
            LEFT JOIN raw_metric_value rm ON rm.period_id = p.id
            GROUP BY p.id
            ORDER BY p.period_start
            """
        )
    )


def fetch_metric_monthly(
    conn: sqlite3.Connection, metric: str, start_date: str, end_date: str
) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """
            SELECT
              p.period_start,
              p.period_end,
              p.currency,
              mv.value,
              mv.provenance
            FROM metric_value mv
            JOIN period p ON p.id = mv.period_id
            WHERE mv.metric = ?
              AND p.period_end >= ?
              AND p.period_start <= ?
            ORDER BY p.period_start
            """,
            (metric, start_date, end_date),
        )
    )


def fetch_metric_sum(conn: sqlite3.Connection, metric: str, start_date: str, end_date: str) -> sqlite3.Row:
    row = conn.execute(
        """
        SELECT
          SUM(mv.value) AS total,
          MIN(p.currency) AS currency
        FROM metric_value mv
        JOIN period p ON p.id = mv.period_id
        WHERE mv.metric = ?
          AND p.period_end >= ?
          AND p.period_start <= ?
        """,
        (metric, start_date, end_date),
    ).fetchone()
    assert row is not None
    return row


def fetch_line_items(
    conn: sqlite3.Connection, category: str, start_date: str, end_date: str
) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """
            SELECT
              p.currency,
              liv.path,
              liv.name,
              liv.account_id,
              liv.value,
              liv.provenance
            FROM line_item_value liv
            JOIN period p ON p.id = liv.period_id
            WHERE liv.category = ?
              AND p.period_end >= ?
              AND p.period_start <= ?
            """,
            (category, start_date, end_date),
        )
    )


def create_ingestion_run(
    conn: sqlite3.Connection,
    mode: str,
    primary_source: str,
    tolerance: float,
) -> int:
    now = utc_now_iso()
    cur = conn.execute(
        """
        INSERT INTO ingestion_run(started_at, mode, primary_source, tolerance, status)
        VALUES (?, ?, ?, ?, ?)
        """,
        (now, mode, primary_source, tolerance, "running"),
    )
    return int(cur.lastrowid)


def finish_ingestion_run(conn: sqlite3.Connection, run_id: int, status: str, details: str | None = None) -> None:
    conn.execute(
        """
        UPDATE ingestion_run
        SET finished_at = ?, status = ?, details = ?
        WHERE id = ?
        """,
        (utc_now_iso(), status, details, run_id),
    )


def log_ingestion_issue(
    conn: sqlite3.Connection,
    run_id: int,
    level: str,
    message: str,
    source: str | None = None,
    period_id: int | None = None,
    metric: str | None = None,
    details: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO ingestion_issue(run_id, level, source, period_id, metric, message, details)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (run_id, level, source, period_id, metric, message, details),
    )


def ensure_chat_session(conn: sqlite3.Connection, session_id: str) -> None:
    conn.execute(
        """
        INSERT INTO chat_session(id, created_at)
        VALUES (?, ?)
        ON CONFLICT(id) DO NOTHING
        """,
        (session_id, utc_now_iso()),
    )


def insert_chat_message(conn: sqlite3.Connection, session_id: str, role: str, content: str) -> None:
    conn.execute(
        """
        INSERT INTO chat_message(session_id, role, content, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (session_id, role, content, utc_now_iso()),
    )


def fetch_chat_messages(conn: sqlite3.Connection, session_id: str, limit: int) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """
            SELECT role, content, created_at
            FROM chat_message
            WHERE session_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (session_id, limit),
        )
    )

