prices = Hash(default_value=None)
updated_at = Hash(default_value=None)
max_age_seconds = Hash(default_value=0)
sources = Hash(default_value="")
reporters = Hash(default_value=False)

governor = Variable()
proposed_governor = Variable()

PriceUpdatedEvent = LogEvent(
    event="PriceUpdated",
    params={
        "asset": {"type": str, "idx": True},
        "price": (int, float, decimal),
        "reporter": {"type": str, "idx": True},
        "source": str,
    },
)

ReporterUpdatedEvent = LogEvent(
    event="ReporterUpdated",
    params={
        "account": {"type": str, "idx": True},
        "enabled": bool,
    },
)

GovernanceTransferStartedEvent = LogEvent(
    event="GovernanceTransferStarted",
    params={
        "current_governor": {"type": str, "idx": True},
        "proposed_governor": {"type": str, "idx": True},
    },
)

GovernanceTransferredEvent = LogEvent(
    event="GovernanceTransferred",
    params={
        "previous_governor": {"type": str, "idx": True},
        "new_governor": {"type": str, "idx": True},
    },
)


@construct
def seed(governor_address: str = None):
    resolved_governor = governor_address
    if resolved_governor is None or resolved_governor == "":
        resolved_governor = ctx.caller

    governor.set(resolved_governor)
    proposed_governor.set(None)
    reporters[resolved_governor] = True


def require_governor():
    assert ctx.caller == governor.get(), "Only governor can call."


def require_reporter():
    assert reporters[ctx.caller] is True, "Only reporter can call."


def elapsed_seconds(since_time):
    if since_time is None:
        return 0
    delta = now - since_time
    elapsed = delta.seconds
    if elapsed < 0:
        return 0
    return elapsed


@export
def governor_of():
    return governor.get()


@export
def is_reporter(account: str):
    return reporters[account]


@export
def start_governance_transfer(new_governor: str):
    require_governor()
    assert isinstance(new_governor, str) and new_governor != "", "new_governor must be non-empty."
    proposed_governor.set(new_governor)
    GovernanceTransferStartedEvent(
        {
            "current_governor": governor.get(),
            "proposed_governor": new_governor,
        }
    )


@export
def accept_governance():
    pending = proposed_governor.get()
    assert pending is not None and pending != "", "No governance transfer pending."
    assert ctx.caller == pending, "Only proposed governor can accept."
    previous = governor.get()
    governor.set(pending)
    proposed_governor.set(None)
    reporters[pending] = True
    GovernanceTransferredEvent(
        {
            "previous_governor": previous,
            "new_governor": pending,
        }
    )


@export
def set_reporter(account: str, enabled: bool):
    require_governor()
    assert isinstance(account, str) and account != "", "account must be non-empty."
    reporters[account] = enabled
    ReporterUpdatedEvent({"account": account, "enabled": enabled})


@export
def set_max_price_age(asset: str, seconds: int):
    require_governor()
    assert isinstance(asset, str) and asset != "", "asset must be non-empty."
    assert seconds >= 0, "seconds must be non-negative."
    max_age_seconds[asset] = seconds


@export
def set_price(asset: str, price: Any, source: str = ""):
    require_reporter()
    assert isinstance(asset, str) and asset != "", "asset must be non-empty."
    assert isinstance(price, (int, float, decimal)), "price must be numeric."
    assert price > 0, "price must be positive."
    if source is None:
        source = ""
    assert isinstance(source, str), "source must be a string."

    prices[asset] = price
    updated_at[asset] = now
    sources[asset] = source

    PriceUpdatedEvent(
        {
            "asset": asset,
            "price": price,
            "reporter": ctx.caller,
            "source": source,
        }
    )


@export
def get_price(asset: str):
    assert isinstance(asset, str) and asset != "", "asset must be non-empty."
    price = prices[asset]
    assert price is not None, "Price not set."

    freshness_limit = max_age_seconds[asset]
    if freshness_limit is not None and freshness_limit > 0:
        assert elapsed_seconds(updated_at[asset]) <= freshness_limit, "Price is stale."

    return price


@export
def price_info(asset: str):
    assert isinstance(asset, str) and asset != "", "asset must be non-empty."
    return {
        "price": prices[asset],
        "updated_at": updated_at[asset],
        "max_age_seconds": max_age_seconds[asset],
        "source": sources[asset],
    }
