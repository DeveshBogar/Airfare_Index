from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.session import init_db
from app.logging_config import configure_logging
from app.routers import fares, health, index, routes

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Daily collection is driven solely by the external scheduled task
    # (see docs/architecture.md) — this process used to also run its own
    # in-process APScheduler job, but that only ever worked while this
    # exact server process happened to be alive (never guaranteed - dev
    # sessions end, deployments restart), and running two independent,
    # uncoordinated triggers against the same SQLite file was a real
    # collision risk. One well-tested, observable trigger beats two
    # redundant ones. init_db() still needs to run on startup regardless.
    init_db()
    yield


app = FastAPI(
    title="Airfare Price Index (APIx) API",
    description=(
        "Real-time Indian domestic airfare price index, built from live-scraped "
        "carrier data gated by a runtime robots.txt compliance check and weighted "
        "by real DGCA passenger-traffic data. Prototype for NSO/RBI CPI augmentation."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8001", "http://127.0.0.1:8001"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(routes.router)
app.include_router(fares.router)
app.include_router(index.router)
