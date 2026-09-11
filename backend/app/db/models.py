"""SQLAlchemy ORM models for the airfare database.

Schema mirrors what the problem statement asks for explicitly: fare quotes
carry origin, destination, carrier, advance-purchase window, fare-class,
base fare, taxes, and total fare, plus enough provenance (source, scrape
run, raw snapshot reference) to audit every number back to where it came
from.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Carrier(Base):
    __tablename__ = "carriers"

    code: Mapped[str] = mapped_column(String(4), primary_key=True)  # IATA code
    name: Mapped[str] = mapped_column(String(64))

    quotes: Mapped[list["FareQuote"]] = relationship(back_populates="carrier")


class Route(Base):
    __tablename__ = "routes"
    __table_args__ = (UniqueConstraint("origin", "destination", name="uq_route_pair"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    origin: Mapped[str] = mapped_column(String(3))
    destination: Mapped[str] = mapped_column(String(3))
    display_name: Mapped[str] = mapped_column(String(64))

    quotes: Mapped[list["FareQuote"]] = relationship(back_populates="route")
    weights: Mapped[list["RouteWeight"]] = relationship(back_populates="route")


class RouteWeight(Base):
    """Weight for a route derived from real DGCA city-pair passenger-traffic
    data (see app/index/weights.py). One row per (route, as_of period)."""

    __tablename__ = "route_weights"
    __table_args__ = (UniqueConstraint("route_id", "as_of", name="uq_route_weight_period"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    route_id: Mapped[int] = mapped_column(ForeignKey("routes.id"))
    as_of: Mapped[str] = mapped_column(String(16))  # e.g. "2025-04" (DGCA report month)
    passengers: Mapped[float] = mapped_column(Float)  # raw DGCA traffic figure
    weight: Mapped[float] = mapped_column(Float)  # normalized share within the basket
    source_file: Mapped[str] = mapped_column(String(256))

    route: Mapped["Route"] = relationship(back_populates="weights")


class ScrapeRun(Base):
    """One execution of the scraper (all sources, one pass over the basket)."""

    __tablename__ = "scrape_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="running")  # running|ok|error
    quotes_collected: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str] = mapped_column(String(1024), default="")

    quotes: Mapped[list["FareQuote"]] = relationship(back_populates="scrape_run")


class FareQuote(Base):
    """A single cleaned fare observation: one carrier, one route, one
    advance-purchase window, one point in time."""

    __tablename__ = "fare_quotes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    route_id: Mapped[int] = mapped_column(ForeignKey("routes.id"))
    carrier_code: Mapped[str] = mapped_column(ForeignKey("carriers.code"))
    source_id: Mapped[str] = mapped_column(String(32))  # matches config.SOURCE_REGISTRY key
    scrape_run_id: Mapped[int | None] = mapped_column(ForeignKey("scrape_runs.id"), nullable=True)

    ap_window_days: Mapped[int] = mapped_column(Integer)  # T+1, T+7, ...
    search_date: Mapped[dt.date] = mapped_column(DateTime)  # date the scrape ran (data date)
    travel_date: Mapped[dt.date] = mapped_column(DateTime)  # departure date being priced
    fare_class: Mapped[str] = mapped_column(String(32), default="economy")

    base_fare: Mapped[float | None] = mapped_column(Float, nullable=True)
    taxes_fees: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_fare: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="INR")

    is_outlier: Mapped[bool] = mapped_column(Boolean, default=False)
    sold_out: Mapped[bool] = mapped_column(Boolean, default=False)

    scraped_at: Mapped[dt.datetime] = mapped_column(DateTime)
    raw_snapshot_path: Mapped[str] = mapped_column(String(512), default="")

    route: Mapped["Route"] = relationship(back_populates="quotes")
    carrier: Mapped["Carrier"] = relationship(back_populates="quotes")
    scrape_run: Mapped["ScrapeRun | None"] = relationship(back_populates="quotes")


class IndexValue(Base):
    """A computed Airfare Price Index value for one date/frequency/method."""

    __tablename__ = "index_values"
    __table_args__ = (
        UniqueConstraint("date", "frequency", "method", name="uq_index_period_method"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[dt.date] = mapped_column(DateTime)
    frequency: Mapped[str] = mapped_column(String(8))  # daily|weekly|monthly
    method: Mapped[str] = mapped_column(String(16))  # laspeyres|paasche|fisher
    value: Mapped[float] = mapped_column(Float)  # index value, base period = 100
    sample_size: Mapped[int] = mapped_column(Integer)  # number of fare quotes behind this value
    routes_covered: Mapped[int] = mapped_column(Integer)
    computed_at: Mapped[dt.datetime] = mapped_column(DateTime)


class ComplianceLog(Base):
    """Every robots.txt compliance decision the gate makes, for audit."""

    __tablename__ = "compliance_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(String(32))
    domain: Mapped[str] = mapped_column(String(128))
    path_checked: Mapped[str] = mapped_column(String(512))
    allowed: Mapped[bool] = mapped_column(Boolean)
    reason: Mapped[str] = mapped_column(String(512))
    checked_at: Mapped[dt.datetime] = mapped_column(DateTime)
