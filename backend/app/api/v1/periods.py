from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.db.repo import list_periods, list_periods_with_sources
from app.db.sqlite import get_db

router = APIRouter()


@router.get("/periods")
def get_periods(
    include_provenance: bool = Query(default=False),
    conn=Depends(get_db),
):
    if include_provenance:
        rows = list_periods_with_sources(conn)
        return [
            {
                "id": r["id"],
                "period_start": r["period_start"],
                "period_end": r["period_end"],
                "currency": r["currency"],
                "sources": (r["sources"].split(",") if r["sources"] else []),
            }
            for r in rows
        ]

    rows = list_periods(conn)
    return [
        {"id": r["id"], "period_start": r["period_start"], "period_end": r["period_end"], "currency": r["currency"]}
        for r in rows
    ]

