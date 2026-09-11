"""Maps each source_id in app.config.SOURCE_REGISTRY to the adapter class
that knows how to collect fares from it."""
from __future__ import annotations

from app.scraper.base import SourceAdapter
from app.scraper.sources.akasa import AkasaAdapter
from app.scraper.sources.gated_generic import (
    AirIndiaAdapter,
    AirIndiaExpressAdapter,
    CleartripAdapter,
    EaseMyTripAdapter,
    GoibiboAdapter,
    IndiGoAdapter,
    IxigoAdapter,
    MakeMyTripAdapter,
    YatraAdapter,
)
from app.scraper.sources.spicejet import SpiceJetAdapter

ADAPTER_CLASSES: dict[str, type[SourceAdapter]] = {
    "spicejet": SpiceJetAdapter,
    "akasa": AkasaAdapter,
    "indigo": IndiGoAdapter,
    "air_india": AirIndiaAdapter,
    "air_india_express": AirIndiaExpressAdapter,
    "ixigo": IxigoAdapter,
    "easemytrip": EaseMyTripAdapter,
    "cleartrip": CleartripAdapter,
    "yatra": YatraAdapter,
    "goibibo": GoibiboAdapter,
    "makemytrip": MakeMyTripAdapter,
}


def get_adapter(source_id: str) -> SourceAdapter:
    return ADAPTER_CLASSES[source_id]()
