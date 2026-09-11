"""Central logging setup, called once from every real entry point (the
FastAPI app in app.main and the CLI in app.cli).

Every logger in this codebase is namespaced under "airfare_idex" (e.g.
"airfare_idex.scraper", "airfare_idex.pipeline") specifically so
configuring the parent logger once here covers all of them. Without this,
Python's logging module falls back to its "handler of last resort," which
silently drops everything below WARNING and prints what little it does
show with no timestamp or module name — so every logger.info/warning/
exception call across the scraper, pipeline, and CLI was effectively
going nowhere useful. That made a failed scrape run much harder to
diagnose than it needed to be.
"""
from __future__ import annotations

import logging
import sys

_CONFIGURED = False


def configure_logging(level: int = logging.INFO) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    )

    root = logging.getLogger("airfare_idex")
    root.addHandler(handler)
    root.setLevel(level)
    root.propagate = False

    _CONFIGURED = True
