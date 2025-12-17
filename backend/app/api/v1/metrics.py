from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db.sqlite import get_db
from app.services.query_service import QueryService

router = APIRouter()


@router.get("/metrics/timeseries")
def get_metric_timeseries(
    metric: str = Query(...),
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    group_by: Literal["month", "quarter", "year"] = Query(default="month"),
    include_provenance: bool = Query(default=False),
    conn=Depends(get_db),
):
    try:
        return QueryService(conn).metric_timeseries(
            metric=metric,
            start=start,
            end=end,
            group_by=group_by,
            include_provenance=include_provenance,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/metrics/compare")
def compare_metric_periods(
    metric: str = Query(...),
    period_a: str = Query(...),
    period_b: str = Query(...),
    include_provenance: bool = Query(default=False),
    conn=Depends(get_db),
):
    try:
        return QueryService(conn).compare_periods(
            metric=metric,
            period_a=period_a,
            period_b=period_b,
            include_provenance=include_provenance,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/breakdown")
def get_breakdown(
    category: str = Query(...),
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    level: int = Query(default=1, ge=1, le=10),
    include_provenance: bool = Query(default=False),
    conn=Depends(get_db),
):
    try:
        return QueryService(conn).breakdown(
            category=category,
            start=start,
            end=end,
            level=level,
            include_provenance=include_provenance,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
