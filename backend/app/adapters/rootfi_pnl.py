from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.services.types import LineItemObservation, MetricObservation


@dataclass(frozen=True, slots=True)
class ParsedRootfi:
    metrics: list[MetricObservation]
    line_items: list[LineItemObservation]


def _to_float(v: Any) -> float:
    try:
        if v is None:
            return 0.0
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _flatten_tree(nodes: list[dict[str, Any]], prefix: list[str]) -> list[tuple[list[str], dict[str, Any]]]:
    out: list[tuple[list[str], dict[str, Any]]] = []
    for n in nodes:
        name = str(n.get("name") or "").strip()
        if not name:
            continue
        line_items = n.get("line_items") or []
        if line_items:
            out.extend(_flatten_tree(line_items, prefix + [name]))
        else:
            out.append((prefix + [name], n))
    return out


def parse_rootfi_pnl(payload: dict[str, Any]) -> ParsedRootfi:
    metrics: list[MetricObservation] = []
    line_items: list[LineItemObservation] = []

    for period in payload.get("data") or []:
        p_start = str(period.get("period_start"))
        p_end = str(period.get("period_end"))

        scalar_metric_map: dict[str, str] = {
            "gross_profit": "gross_profit",
            "operating_profit": "operating_profit",
            "taxes": "taxes_total",
        }
        for src_key, metric_name in scalar_metric_map.items():
            if period.get(src_key) is None:
                continue
            metrics.append(MetricObservation(p_start, p_end, metric_name, _to_float(period.get(src_key))))

        if period.get("net_profit") is not None:
            metrics.append(MetricObservation(p_start, p_end, "net_income", _to_float(period.get("net_profit"))))

        category_trees: list[tuple[str, str]] = [
            ("revenue", "revenue_total"),
            ("cost_of_goods_sold", "cogs_total"),
            ("operating_expenses", "operating_expenses_total"),
            ("non_operating_revenue", "non_operating_revenue_total"),
            ("non_operating_expenses", "non_operating_expenses_total"),
        ]

        for cat_key, total_metric in category_trees:
            nodes = period.get(cat_key) or []
            leaves = _flatten_tree(nodes, prefix=[])
            total = 0.0
            for path_segs, leaf in leaves:
                value = _to_float(leaf.get("value"))
                total += value
                line_items.append(
                    LineItemObservation(
                        period_start=p_start,
                        period_end=p_end,
                        category={
                            "revenue": "revenue",
                            "cost_of_goods_sold": "cogs",
                            "operating_expenses": "operating_expense",
                            "non_operating_revenue": "non_operating_revenue",
                            "non_operating_expenses": "non_operating_expense",
                        }.get(cat_key, "unknown"),
                        path=" > ".join(path_segs),
                        name=path_segs[-1] if path_segs else "",
                        account_id=str(leaf.get("account_id")) if leaf.get("account_id") else None,
                        value=value,
                    )
                )
            metrics.append(MetricObservation(p_start, p_end, total_metric, total))

    return ParsedRootfi(metrics=metrics, line_items=line_items)


def load_rootfi_json(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

