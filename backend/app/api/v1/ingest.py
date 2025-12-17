from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.settings import Settings, get_settings
from app.db.sqlite import get_db
from app.services.ingest_service import IngestService

router = APIRouter()


class IngestRequest(BaseModel):
    mode: Literal["replace", "upsert"] = "replace"


@router.post("/ingest")
def ingest(req: IngestRequest, conn=Depends(get_db), settings: Settings = Depends(get_settings)):
    service = IngestService(settings)
    return service.ingest(conn, mode=req.mode)

