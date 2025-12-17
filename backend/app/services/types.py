from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MetricObservation:
    period_start: str
    period_end: str
    metric: str
    value: float


@dataclass(frozen=True, slots=True)
class LineItemObservation:
    period_start: str
    period_end: str
    category: str
    path: str
    name: str
    account_id: str | None
    value: float

