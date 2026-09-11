from __future__ import annotations

import datetime as dt

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "time": dt.datetime.utcnow().isoformat()}
