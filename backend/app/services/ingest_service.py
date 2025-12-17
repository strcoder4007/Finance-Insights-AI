from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.adapters.quickbooks_pnl import load_quickbooks_json, parse_quickbooks_pnl
from app.adapters.rootfi_pnl import load_rootfi_json, parse_rootfi_pnl
from app.core.settings import Settings
from app.db import repo


def _within_tolerance(a: float, b: float, tol: float) -> bool:
    if tol < 1:
        denom = max(abs(a), abs(b), 1.0)
        return abs(a - b) <= tol * denom
    return abs(a - b) <= tol


class IngestService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def ingest(self, conn: sqlite3.Connection, mode: str = "replace") -> dict:
        if mode == "replace":
            repo.clear_financial_data(conn)

        run_id = repo.create_ingestion_run(
            conn,
            mode=mode,
            primary_source=self.settings.primary_source,
            tolerance=float(self.settings.merge_tolerance),
        )

        try:
            qb_payload = load_quickbooks_json(self.settings.data1_path)
            rf_payload = load_rootfi_json(self.settings.data2_path)

            qb = parse_quickbooks_pnl(qb_payload)
            rf = parse_rootfi_pnl(rf_payload)

            qb_period_ids: dict[tuple[str, str], int] = {}
            for obs in qb.metrics:
                key = (obs.period_start, obs.period_end)
                if key not in qb_period_ids:
                    qb_period_ids[key] = repo.upsert_period(conn, obs.period_start, obs.period_end, qb.currency)
                repo.upsert_raw_metric(conn, qb_period_ids[key], "quickbooks", obs.metric, obs.value)

            for obs in qb.line_items:
                key = (obs.period_start, obs.period_end)
                if key not in qb_period_ids:
                    qb_period_ids[key] = repo.upsert_period(conn, obs.period_start, obs.period_end, qb.currency)
                repo.upsert_raw_line_item(
                    conn,
                    qb_period_ids[key],
                    "quickbooks",
                    obs.category,
                    obs.path,
                    obs.name,
                    obs.account_id,
                    obs.value,
                )

            rf_period_ids: dict[tuple[str, str], int] = {}
            for obs in rf.metrics:
                key = (obs.period_start, obs.period_end)
                if key not in rf_period_ids:
                    rf_period_ids[key] = repo.upsert_period(conn, obs.period_start, obs.period_end, currency=None)
                repo.upsert_raw_metric(conn, rf_period_ids[key], "rootfi", obs.metric, obs.value)

            for obs in rf.line_items:
                key = (obs.period_start, obs.period_end)
                if key not in rf_period_ids:
                    rf_period_ids[key] = repo.upsert_period(conn, obs.period_start, obs.period_end, currency=None)
                repo.upsert_raw_line_item(
                    conn,
                    rf_period_ids[key],
                    "rootfi",
                    obs.category,
                    obs.path,
                    obs.name,
                    obs.account_id,
                    obs.value,
                )

            self._rebuild_canonical(conn, run_id)

            stats = self._basic_stats(conn)
            repo.finish_ingestion_run(conn, run_id, status="ok", details=json.dumps(stats))
            return {"run_id": run_id, "status": "ok", "stats": stats}
        except Exception as e:
            repo.finish_ingestion_run(conn, run_id, status="error", details=str(e))
            raise

    def _basic_stats(self, conn: sqlite3.Connection) -> dict:
        def count(sql: str) -> int:
            row = conn.execute(sql).fetchone()
            assert row is not None
            return int(row[0])

        return {
            "periods": count("SELECT COUNT(*) FROM period"),
            "raw_metrics": count("SELECT COUNT(*) FROM raw_metric_value"),
            "raw_line_items": count("SELECT COUNT(*) FROM raw_line_item_value"),
            "metrics": count("SELECT COUNT(*) FROM metric_value"),
            "line_items": count("SELECT COUNT(*) FROM line_item_value"),
            "issues": count("SELECT COUNT(*) FROM ingestion_issue"),
        }

    def _rebuild_canonical(self, conn: sqlite3.Connection, run_id: int) -> None:
        repo.clear_canonical_data(conn)

        primary = self.settings.primary_source
        other = "rootfi" if primary == "quickbooks" else "quickbooks"
        tol = float(self.settings.merge_tolerance)

        # Metrics
        for r in conn.execute("SELECT id FROM period ORDER BY period_start"):
            period_id = int(r["id"])
            raw = list(
                conn.execute(
                    "SELECT source, metric, value FROM raw_metric_value WHERE period_id = ?",
                    (period_id,),
                )
            )
            by_metric: dict[str, dict[str, float]] = {}
            for row in raw:
                by_metric.setdefault(row["metric"], {})[row["source"]] = float(row["value"])

            for metric, values in by_metric.items():
                p_val = values.get(primary)
                o_val = values.get(other)
                if p_val is None and o_val is None:
                    continue
                if p_val is None:
                    repo.upsert_metric_value(conn, period_id, metric, o_val, other)
                    continue
                if o_val is None:
                    repo.upsert_metric_value(conn, period_id, metric, p_val, primary)
                    continue

                if _within_tolerance(p_val, o_val, tol):
                    repo.upsert_metric_value(conn, period_id, metric, p_val, f"{primary}+{other}")
                else:
                    repo.upsert_metric_value(conn, period_id, metric, p_val, primary)
                    repo.log_ingestion_issue(
                        conn,
                        run_id=run_id,
                        level="warn",
                        source=f"{primary},{other}",
                        period_id=period_id,
                        metric=metric,
                        message="Metric mismatch beyond tolerance; using primary source",
                        details=json.dumps({"primary_value": p_val, "other_value": o_val, "tolerance": tol}),
                    )

        # Line items
        categories = [
            "revenue",
            "cogs",
            "operating_expense",
            "non_operating_revenue",
            "non_operating_expense",
            "other_income",
            "other_expense",
            "unknown",
        ]
        for r in conn.execute("SELECT id FROM period ORDER BY period_start"):
            period_id = int(r["id"])
            for category in categories:
                primary_items = list(
                    conn.execute(
                        """
                        SELECT category, path, name, account_id, value
                        FROM raw_line_item_value
                        WHERE period_id = ? AND source = ? AND category = ?
                        """,
                        (period_id, primary, category),
                    )
                )
                chosen_source = primary
                chosen_items = primary_items
                if not chosen_items:
                    fallback_items = list(
                        conn.execute(
                            """
                            SELECT category, path, name, account_id, value
                            FROM raw_line_item_value
                            WHERE period_id = ? AND source = ? AND category = ?
                            """,
                            (period_id, other, category),
                        )
                    )
                    chosen_source = other
                    chosen_items = fallback_items

                for item in chosen_items:
                    repo.upsert_line_item_value(
                        conn,
                        period_id=period_id,
                        category=category,
                        path=item["path"],
                        name=item["name"],
                        account_id=item["account_id"],
                        value=float(item["value"]),
                        provenance=chosen_source,
                    )
