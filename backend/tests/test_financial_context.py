from __future__ import annotations

import inspect

from app import schemas
from app.index import carrier_index, financial_context
from app.index.financial_context import (
    ALL_KNOWN_CARRIER_CODES,
    FINANCIAL_REFERENCE,
    NOT_AVAILABLE_CARRIERS,
    all_financial_context,
    check_investor_relations_compliance,
    financial_context_for_carrier,
)
from app.scraper.compliance import ComplianceGate

NO_ROBOTS_RESTRICTION = "User-agent: *\nAllow: /\n"


def test_akasa_and_air_india_are_explicitly_not_available_with_a_reason():
    for code in ("QP", "AI", "IX"):
        ctx = financial_context_for_carrier(code)
        assert ctx["available"] is False
        assert ctx["quarters"] == []
        assert ctx["compliance"] is None
        assert isinstance(ctx["reason"], str) and len(ctx["reason"]) > 0
        # the reason must actually explain *why*, not just assert the fact
        assert "not" in ctx["reason"].lower() or "private" in ctx["reason"].lower()


def test_indigo_and_spicejet_have_real_dated_sourced_quarters(monkeypatch):
    monkeypatch.setattr(
        "app.scraper.compliance.requests.get",
        lambda *a, **k: type("R", (), {"status_code": 200, "text": NO_ROBOTS_RESTRICTION})(),
    )
    for code in ("6E", "SG"):
        ctx = financial_context_for_carrier(code)
        assert ctx["available"] is True
        assert len(ctx["quarters"]) > 0
        for q in ctx["quarters"]:
            assert q["source_url"].startswith("https://")
            assert q["filing_date"] is not None
            assert q["period_end"] > q["period_start"]
            # margin must be computed from the two real figures, not stored separately
            expected_margin = round(100.0 * q["net_profit_cr"] / q["revenue_cr"], 2)
            assert abs(q["net_margin_pct"] - expected_margin) < 1e-6


def test_financial_reference_never_has_more_quarters_than_researched():
    # Guards against ever silently padding a carrier's history with a
    # placeholder quarter - every entry must carry a real citation.
    for code, quarters in FINANCIAL_REFERENCE.items():
        assert quarters, f"{code} has an empty quarter list"
        for q in quarters:
            assert q.source_url, f"{code} {q.quarter_label} is missing a source_url"
            assert q.source_note, f"{code} {q.quarter_label} is missing a source_note"


def test_check_investor_relations_compliance_fails_closed_when_robots_txt_unreachable(monkeypatch):
    import requests

    def boom(*args, **kwargs):
        raise requests.exceptions.ConnectionError("no route to host")

    monkeypatch.setattr("app.scraper.compliance.requests.get", boom)
    result = check_investor_relations_compliance("SG", ComplianceGate())
    assert result["allowed"] is False
    assert "could not be fetched" in result["reason"]


def test_check_investor_relations_compliance_allows_when_robots_txt_permits(monkeypatch):
    monkeypatch.setattr(
        "app.scraper.compliance.requests.get",
        lambda *a, **k: type("R", (), {"status_code": 200, "text": NO_ROBOTS_RESTRICTION})(),
    )
    result = check_investor_relations_compliance("6E", ComplianceGate())
    assert result["allowed"] is True
    assert result["domain"] == "www.goindigo.in"


def test_all_financial_context_covers_every_known_carrier(monkeypatch):
    monkeypatch.setattr(
        "app.scraper.compliance.requests.get",
        lambda *a, **k: type("R", (), {"status_code": 200, "text": NO_ROBOTS_RESTRICTION})(),
    )
    contexts = all_financial_context(ALL_KNOWN_CARRIER_CODES)
    codes = {c["carrier_code"] for c in contexts}
    assert codes == set(ALL_KNOWN_CARRIER_CODES)
    available = {c["carrier_code"] for c in contexts if c["available"]}
    assert available == {"6E", "SG"}
    assert set(NOT_AVAILABLE_CARRIERS.keys()) == {"QP", "AI", "IX"}


# ---------------------------------------------------------------------
# Regression: no code path anywhere in this feature may compute or
# return a fairness/justification verdict on a fare. This is checked two
# ways: (1) no function or class defined in the two feature modules has a
# name matching that shape, and (2) the actual, real output of the public
# functions never contains a key with that shape - a structural check on
# real data, not just a name check.
# ---------------------------------------------------------------------

BANNED_NAME_FRAGMENTS = ("justif", "is_fair", "unfair", "fairness", "gouging", "price_verdict")


def _defined_names(module) -> list[str]:
    return [
        name
        for name, obj in inspect.getmembers(module)
        if (inspect.isfunction(obj) or inspect.isclass(obj)) and getattr(obj, "__module__", None) == module.__name__
    ]


def test_no_function_or_class_name_looks_like_a_fairness_verdict():
    for module in (financial_context, carrier_index):
        for name in _defined_names(module):
            lowered = name.lower()
            for fragment in BANNED_NAME_FRAGMENTS:
                assert fragment not in lowered, (
                    f"{module.__name__}.{name} looks like a fairness/justification verdict "
                    f"(matches {fragment!r}) - return the two real numbers instead, per this "
                    f"module's own docstring rule"
                )


def _walk_keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield str(k)
            yield from _walk_keys(v)
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            yield from _walk_keys(item)


def test_financial_context_output_has_no_fairness_verdict_key(monkeypatch):
    monkeypatch.setattr(
        "app.scraper.compliance.requests.get",
        lambda *a, **k: type("R", (), {"status_code": 200, "text": NO_ROBOTS_RESTRICTION})(),
    )
    contexts = all_financial_context(ALL_KNOWN_CARRIER_CODES)
    for key in _walk_keys(contexts):
        lowered = key.lower()
        for fragment in BANNED_NAME_FRAGMENTS:
            assert fragment not in lowered, f"output key {key!r} looks like a fairness verdict field"


def test_schemas_have_no_fairness_verdict_fields():
    schema_names = [
        "CarrierFinancialContextOut",
        "CarrierFinancialQuarterOut",
        "InvestorRelationsComplianceOut",
        "ByCarrierIndexOut",
        "CarrierIndexSeriesOut",
        "CarrierIndexPointOut",
    ]
    for name in schema_names:
        model = getattr(schemas, name)
        for field_name in model.model_fields:
            lowered = field_name.lower()
            for fragment in BANNED_NAME_FRAGMENTS:
                assert fragment not in lowered, f"{name}.{field_name} looks like a fairness verdict field"
