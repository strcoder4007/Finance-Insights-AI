from __future__ import annotations

import re
import sqlite3
from datetime import date, timedelta

from app.db import repo


_ALLOWED_METRICS = {
    "revenue_total",
    "cogs_total",
    "gross_profit",
    "operating_expenses_total",
    "operating_profit",
    "non_operating_revenue_total",
    "non_operating_expenses_total",
    "taxes_total",
    "net_income",
}

_ALLOWED_CATEGORIES = {
    "revenue",
    "cogs",
    "operating_expense",
    "non_operating_revenue",
    "non_operating_expense",
    "other_income",
    "other_expense",
    "unknown",
}


def _date_or_default(value: date | None, default: date) -> date:
    return value if value is not None else default


def _truncate_path(path: str, level: int) -> str:
    parts = [p.strip() for p in path.split(">") if p.strip()]
    if not parts:
        return path.strip()
    if len(parts) > 1:
        parts = parts[1:]
    return " > ".join(parts[:level]) if parts[:level] else parts[-1]


def _quarter_label(d: date) -> str:
    q = ((d.month - 1) // 3) + 1
    return f"{d.year}-Q{q}"


def _parse_period_label(label: str) -> tuple[date, date]:
    label = label.strip()
    if re.fullmatch(r"\d{4}-Q[1-4]", label):
        year = int(label[:4])
        quarter = int(label[-1])
        start_month = (quarter - 1) * 3 + 1
        start = date(year, start_month, 1)
        end_month = start_month + 2
        if end_month == 12:
            end = date(year, 12, 31)
        else:
            end = date(year, end_month + 1, 1) - timedelta(days=1)
        return start, end

    if re.fullmatch(r"\d{4}-\d{2}", label):
        year, month = map(int, label.split("-"))
        start = date(year, month, 1)
        if month == 12:
            end = date(year, 12, 31)
        else:
            end = date(year, month + 1, 1) - timedelta(days=1)
        return start, end

    if re.fullmatch(r"\d{4}", label):
        year = int(label)
        return date(year, 1, 1), date(year, 12, 31)

    raise ValueError(f"Unsupported period label: {label}")


class QueryService:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def metric_timeseries(self, metric: str, start: date | None, end: date | None, group_by: str, include_provenance: bool):
        if metric not in _ALLOWED_METRICS:
            raise ValueError(f"Unknown metric: {metric}")

        periods = repo.list_periods(self.conn)
        if not periods:
            return {"metric": metric, "total": 0.0, "series": [], "currency": None}

        min_start = date.fromisoformat(periods[0]["period_start"])
        max_end = date.fromisoformat(periods[-1]["period_end"])
        start_d = _date_or_default(start, min_start)
        end_d = _date_or_default(end, max_end)

        rows = repo.fetch_metric_monthly(self.conn, metric=metric, start_date=start_d.isoformat(), end_date=end_d.isoformat())

        currency = next((r["currency"] for r in rows if r["currency"]), None)

        buckets: dict[str, dict] = {}
        for r in rows:
            p_start = date.fromisoformat(r["period_start"])
            if group_by == "month":
                key = p_start.strftime("%Y-%m")
            elif group_by == "quarter":
                key = _quarter_label(p_start)
            elif group_by == "year":
                key = str(p_start.year)
            else:
                raise ValueError(f"Unsupported group_by: {group_by}")

            b = buckets.setdefault(key, {"period": key, "value": 0.0, "provenances": set()})
            b["value"] += float(r["value"])
            b["provenances"].add(r["provenance"])

        series = []
        for key in sorted(buckets.keys()):
            b = buckets[key]
            entry = {"period": b["period"], "value": b["value"]}
            if include_provenance:
                provenances = sorted(b["provenances"])
                entry["provenance"] = provenances[0] if len(provenances) == 1 else "mixed"
            series.append(entry)

        total = sum(x["value"] for x in series)
        return {"metric": metric, "total": total, "series": series, "currency": currency}

    def compare_periods(self, metric: str, period_a: str, period_b: str, include_provenance: bool):
        if metric not in _ALLOWED_METRICS:
            raise ValueError(f"Unknown metric: {metric}")

        a_start, a_end = _parse_period_label(period_a)
        b_start, b_end = _parse_period_label(period_b)

        a_row = repo.fetch_metric_sum(self.conn, metric=metric, start_date=a_start.isoformat(), end_date=a_end.isoformat())
        b_row = repo.fetch_metric_sum(self.conn, metric=metric, start_date=b_start.isoformat(), end_date=b_end.isoformat())

        a_val = float(a_row["total"] or 0.0)
        b_val = float(b_row["total"] or 0.0)
        delta_abs = b_val - a_val
        delta_pct = (delta_abs / abs(a_val)) if abs(a_val) > 1e-9 else None

        out = {
            "metric": metric,
            "period_a": period_a,
            "period_b": period_b,
            "a_value": a_val,
            "b_value": b_val,
            "delta_abs": delta_abs,
            "delta_pct": delta_pct,
            "currency": b_row["currency"] or a_row["currency"],
        }
        if include_provenance:
            out["note"] = "Provenance is month-level; compare aggregates across months."
        return out

    def breakdown(self, category: str, start: date | None, end: date | None, level: int, include_provenance: bool):
        if category not in _ALLOWED_CATEGORIES:
            raise ValueError(f"Unknown category: {category}")

        periods = repo.list_periods(self.conn)
        if not periods:
            return {"category": category, "total": 0.0, "rows": [], "currency": None}

        min_start = date.fromisoformat(periods[0]["period_start"])
        max_end = date.fromisoformat(periods[-1]["period_end"])
        start_d = _date_or_default(start, min_start)
        end_d = _date_or_default(end, max_end)

        rows = repo.fetch_line_items(self.conn, category=category, start_date=start_d.isoformat(), end_date=end_d.isoformat())
        currency = next((r["currency"] for r in rows if r["currency"]), None)

        agg: dict[str, dict] = {}
        for r in rows:
            key = _truncate_path(str(r["path"]), level=level)
            a = agg.setdefault(key, {"name": key, "value": 0.0, "provenances": set()})
            a["value"] += float(r["value"])
            a["provenances"].add(r["provenance"])

        total = sum(v["value"] for v in agg.values())

        out_rows = []
        for v in sorted(agg.values(), key=lambda x: abs(x["value"]), reverse=True):
            entry = {"name": v["name"], "value": v["value"], "share": (v["value"] / total) if total else None}
            if include_provenance:
                provenances = sorted(v["provenances"])
                entry["provenance"] = provenances[0] if len(provenances) == 1 else "mixed"
            out_rows.append(entry)

        return {"category": category, "total": total, "rows": out_rows, "currency": currency}
