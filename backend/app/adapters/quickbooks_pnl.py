from __future__ import annotations

import calendar
import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from app.services.types import LineItemObservation, MetricObservation


@dataclass(frozen=True, slots=True)
class ParsedQuickBooks:
    currency: str | None
    metrics: list[MetricObservation]
    line_items: list[LineItemObservation]


_GROUP_TO_CATEGORY: dict[str, str] = {
    "Income": "revenue",
    "COGS": "cogs",
    "Expenses": "operating_expense",
    "OtherIncome": "other_income",
    "OtherExpenses": "other_expense",
}

_GROUP_TO_METRIC: dict[str, str] = {
    "Income": "revenue_total",
    "COGS": "cogs_total",
    "GrossProfit": "gross_profit",
    "Expenses": "operating_expenses_total",
    "NetOperatingIncome": "operating_profit",
    "OtherIncome": "non_operating_revenue_total",
    "OtherExpenses": "non_operating_expenses_total",
    "NetIncome": "net_income",
}


def _parse_money(value: Any) -> float:
    if value is None:
        return 0.0
    s = str(value).strip()
    if not s:
        return 0.0
    s = s.replace(",", "")
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1]
    try:
        v = float(s)
    except ValueError:
        return 0.0
    return -v if neg else v


def _month_range_from_title(title: str) -> tuple[date, date] | None:
    t = title.strip()
    if not t or t.lower() == "total":
        return None
    for fmt in ("%b %Y", "%B %Y"):
        try:
            dt = datetime.strptime(t, fmt)
            break
        except ValueError:
            dt = None
    if dt is None:
        return None

    start = date(dt.year, dt.month, 1)
    last_day = calendar.monthrange(dt.year, dt.month)[1]
    end = date(dt.year, dt.month, last_day)
    return start, end


def parse_quickbooks_pnl(payload: dict[str, Any]) -> ParsedQuickBooks:
    data = payload.get("data") or {}
    header = data.get("Header") or {}
    currency = header.get("Currency")

    columns = (data.get("Columns") or {}).get("Column") or []
    month_columns: dict[int, tuple[str, str]] = {}
    for idx, col in enumerate(columns):
        title = col.get("ColTitle") or ""
        rng = _month_range_from_title(title)
        if not rng:
            continue
        start, end = rng
        month_columns[idx] = (start.isoformat(), end.isoformat())

    metrics: list[MetricObservation] = []
    line_items: list[LineItemObservation] = []

    def walk(row: dict[str, Any], category: str | None, path_segments: list[str]) -> None:
        r_type = row.get("type")
        group = row.get("group")

        header_cd = (row.get("Header") or {}).get("ColData") or []
        header_label = header_cd[0].get("value") if header_cd else None
        next_segments = path_segments + ([header_label] if header_label else [])

        if group in _GROUP_TO_CATEGORY:
            category = _GROUP_TO_CATEGORY[group]

        if group in _GROUP_TO_METRIC:
            metric_name = _GROUP_TO_METRIC[group]
            summary = (row.get("Summary") or {}).get("ColData") or []
            for col_idx, (p_start, p_end) in month_columns.items():
                if col_idx >= len(summary):
                    continue
                value = _parse_money(summary[col_idx].get("value"))
                metrics.append(MetricObservation(p_start, p_end, metric_name, value))

        if r_type == "Data":
            if not category:
                return
            coldata = row.get("ColData") or []
            if not coldata:
                return
            name = str((coldata[0] or {}).get("value") or "").strip()
            if not name:
                return
            full_path = " > ".join(next_segments + [name]) if next_segments else name
            for col_idx, (p_start, p_end) in month_columns.items():
                if col_idx >= len(coldata):
                    continue
                value = _parse_money((coldata[col_idx] or {}).get("value"))
                line_items.append(
                    LineItemObservation(
                        period_start=p_start,
                        period_end=p_end,
                        category=category,
                        path=full_path,
                        name=name,
                        account_id=str((coldata[0] or {}).get("id")) if (coldata[0] or {}).get("id") else None,
                        value=value,
                    )
                )
            return

        for child in ((row.get("Rows") or {}).get("Row") or []):
            if isinstance(child, dict):
                walk(child, category, next_segments)

    for top in ((data.get("Rows") or {}).get("Row") or []):
        if isinstance(top, dict):
            walk(top, category=None, path_segments=[])

    return ParsedQuickBooks(currency=currency, metrics=metrics, line_items=line_items)


def load_quickbooks_json(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

