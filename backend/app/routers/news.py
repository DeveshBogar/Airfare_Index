from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter

from app.news.fetch_news import get_airfare_news
from app.schemas import NewsOut

router = APIRouter(prefix="/api", tags=["news"])


@router.get("/news", response_model=NewsOut)
def news() -> NewsOut:
    """Real, dated headlines from real news sources (see app.news.sources)
    that mention something that actually moves airfares — fuel cost,
    regulation, airline capacity, travel demand, or disruption (see
    app.news.keywords). Never claims one of these caused a specific index
    move; it's context for a reader to weigh alongside the real trend."""
    result = get_airfare_news()
    return NewsOut(
        items=[asdict(i) for i in result.items],
        as_of=result.as_of,
        sources_checked=[asdict(c) for c in result.sources_checked],
    )
