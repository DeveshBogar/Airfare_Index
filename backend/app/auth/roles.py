"""The three roles, and exactly what each one unlocks.

The split is drawn around *what is not public*, not around who someone is:

  - CITIZEN ("traveller"): an account is **not** needed to read anything.
    The index, route explorer, affordability view, festival watch and data
    sources are open to everyone, and they stay that way — that is the
    project's premise. What the account unlocks is the ability to **submit**
    a fare report, and to follow what happened to the ones you submitted.
    Submission is gated because an open write endpoint is an open invitation
    to flood the regulator's triage queue with junk; attaching every report
    to an account makes a spammer identifiable and their reports removable
    as a set, which anonymous intake cannot offer.

  - REGULATOR ("government official"): DGCA/ministry side. The only role
    that can see the fare-anomaly flags at all, work the review queue, read
    the raw citizen-report backlog including its unverified content, and
    open draft notice documents. Flags are withheld from the public because
    a flag names a specific carrier on a specific route and is easily
    misread as a finding of wrongdoing when it is nothing of the sort; that
    judgement belongs with a human regulator before it goes anywhere.

  - OPERATOR ("flight company operator"): an airline, bound to exactly one
    carrier code. Sees its own carrier's index, its own fares, the flags
    raised against it, and can file a written response to those flags.
    Scoped to own-carrier data on purpose: handing an airline a
    competitor's fare-level detail would turn a transparency tool into a
    price-signalling channel, which is the opposite of the intent.

An operator row is only coherent with a carrier_code attached, and the other
two roles must not have one; ``validate_role_carrier_pairing`` is the single
place that rule is enforced, called from both the account-creation path and
the User model's own before-insert/update hook.
"""
from __future__ import annotations

ROLE_CITIZEN = "citizen"
ROLE_REGULATOR = "regulator"
ROLE_OPERATOR = "operator"

ALL_ROLES = (ROLE_CITIZEN, ROLE_REGULATOR, ROLE_OPERATOR)

ROLE_LABELS = {
    ROLE_CITIZEN: "Traveller",
    ROLE_REGULATOR: "Government official",
    ROLE_OPERATOR: "Airline operator",
}


def validate_role_carrier_pairing(role: str, carrier_code: str | None) -> None:
    """Raise ValueError unless the role/carrier combination is coherent.

    Operators are meaningless without a carrier to scope them to, and a
    carrier on a traveller or regulator account would be silently ignored by
    every query - which is exactly the kind of misconfiguration that later
    reads as "the permission system didn't work".
    """
    if role not in ALL_ROLES:
        raise ValueError(f"role must be one of {list(ALL_ROLES)}, got {role!r}")

    if role == ROLE_OPERATOR and not carrier_code:
        raise ValueError("an operator account must be bound to a carrier_code")

    if role != ROLE_OPERATOR and carrier_code:
        raise ValueError(f"a {role} account must not be bound to a carrier_code")
