from __future__ import annotations

from pathlib import Path

from app.adapters.quickbooks_pnl import load_quickbooks_json, parse_quickbooks_pnl
from app.adapters.rootfi_pnl import load_rootfi_json, parse_rootfi_pnl


def test_quickbooks_parses_metrics_and_periods():
    root = Path(__file__).resolve().parents[2]
    payload = load_quickbooks_json(str(root / "data1.json"))
    parsed = parse_quickbooks_pnl(payload)
    assert parsed.currency
    assert any(m.metric == "net_income" for m in parsed.metrics)
    assert any(li.category == "operating_expense" for li in parsed.line_items)


def test_rootfi_parses_metrics_and_periods():
    root = Path(__file__).resolve().parents[2]
    payload = load_rootfi_json(str(root / "data2.json"))
    parsed = parse_rootfi_pnl(payload)
    assert any(m.metric == "net_income" for m in parsed.metrics)
    assert any(li.category == "operating_expense" for li in parsed.line_items)

