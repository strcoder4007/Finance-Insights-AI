from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.settings import Settings, get_settings
from app.db.sqlite import get_db
from app.services.nlq_service import NLQService

router = APIRouter()


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str


@router.post("/chat")
def chat(req: ChatRequest, conn=Depends(get_db), settings: Settings = Depends(get_settings)):
    if not settings.openai_api_key:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is not configured")

    service = NLQService(settings)
    return service.chat(conn, session_id=req.session_id, message=req.message)

