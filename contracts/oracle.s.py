reporters = Hash(default_value=False)
reporter_accounts = Variable()

reported_prices = Hash(default_value=None)
reported_at = Hash(default_value=None)
reported_sources = Hash(default_value="")

min_reporters = Hash(default_value=1)
max_age_seconds = Hash(default_value=0)

governor = Variable()
proposed_governor = Variable()

PriceReportedEvent = LogEvent(
    "PriceReported",
    {
        "asset": {"type": str, "idx": True},
        "reporter": {"type": str, "idx": True},
        "price": (int, float, decimal),
        "source": str,
    },
)

ReporterUpdatedEvent = LogEvent(
    "ReporterUpdated",
    {
        "account": {"type": str, "idx": True},
        "enabled": bool,
    },
)

AssetConfigUpdatedEvent = LogEvent(
    "AssetConfigUpdated",
    {
        "asset": {"type": str, "idx": True},
        "min_reporters": int,
        "max_age_seconds": int,
    },
)

GovernanceTransferStartedEvent = LogEvent(
    "GovernanceTransferStarted",
    {
        "current_governor": {"type": str, "idx": True},
        "proposed_governor": {"type": str, "idx": True},
    },
)

GovernanceTransferredEvent = LogEvent(
    "GovernanceTransferred",
    {
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
    reporter_accounts.set([resolved_governor])
    reporters[resolved_governor] = True


def require_governor():
    assert ctx.caller == governor.get(), "Only governor can call."


def require_reporter():
    assert reporters[ctx.caller] is True, "Only reporter can call."


def current_reporters():
    accounts = reporter_accounts.get()
    if accounts is None:
        return []
    return accounts


def elapsed_seconds(since_time):
    if since_time is None:
        return 0
    delta = now - since_time
    elapsed = delta.seconds
    if elapsed < 0:
        return 0
    return elapsed


def sort_prices(values: list):
    ordered = []
    for value in values:
        inserted = False
        i = 0
        while i < len(ordered):
            if value < ordered[i]:
                ordered.insert(i, value)
                inserted = True
                break
            i += 1

        if not inserted:
            ordered.append(value)

    return ordered


def valid_reports(asset: str):
    prices = []
    freshest = None
    oldest = None
    active = 0
    maximum_age = max_age_seconds[asset]

    for reporter in current_reporters():
        if reporters[reporter] is not True:
            continue

        price = reported_prices[asset, reporter]
        timestamp = reported_at[asset, reporter]
        if price is None or timestamp is None:
            continue

        if maximum_age > 0 and elapsed_seconds(timestamp) > maximum_age:
            continue

        prices.append(price)
        active += 1

        if freshest is None or timestamp > freshest:
            freshest = timestamp
        if oldest is None or timestamp < oldest:
            oldest = timestamp

    return {
        "prices": prices,
        "count": active,
        "freshest": freshest,
        "oldest": oldest,
    }


def median_price(values: list):
    assert len(values) > 0, "No prices available."
    ordered = sort_prices(values)
    middle = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


@export
def governor_of():
    return governor.get()


@export
def is_reporter(account: str):
    return reporters[account]


@export
def get_reporters():
    return current_reporters()


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

    if reporters[pending] is not True:
        accounts = current_reporters()
        accounts.append(pending)
        reporter_accounts.set(accounts)
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

    accounts = current_reporters()
    listed = account in accounts

    if enabled:
        if not listed:
            accounts.append(account)
            reporter_accounts.set(accounts)
        reporters[account] = True
    else:
        reporters[account] = False
        if listed:
            accounts.remove(account)
            reporter_accounts.set(accounts)

    ReporterUpdatedEvent({"account": account, "enabled": enabled})


@export
def set_asset_config(
    asset: str,
    min_reporters_required: int,
    max_price_age_seconds: int,
):
    require_governor()
    assert isinstance(asset, str) and asset != "", "asset must be non-empty."
    assert min_reporters_required > 0, "min_reporters_required must be positive."
    assert max_price_age_seconds >= 0, "max_price_age_seconds must be non-negative."

    min_reporters[asset] = min_reporters_required
    max_age_seconds[asset] = max_price_age_seconds

    AssetConfigUpdatedEvent(
        {
            "asset": asset,
            "min_reporters": min_reporters_required,
            "max_age_seconds": max_price_age_seconds,
        }
    )


@export
def submit_price(asset: str, price: Any, source: str = ""):
    require_reporter()
    assert isinstance(asset, str) and asset != "", "asset must be non-empty."
    assert isinstance(price, (int, float, decimal)), "price must be numeric."
    assert price > 0, "price must be positive."
    if source is None:
        source = ""
    assert isinstance(source, str), "source must be a string."

    reported_prices[asset, ctx.caller] = price
    reported_at[asset, ctx.caller] = now
    reported_sources[asset, ctx.caller] = source

    PriceReportedEvent(
        {
            "asset": asset,
            "reporter": ctx.caller,
            "price": price,
            "source": source,
        }
    )


@export
def get_price(asset: str):
    assert isinstance(asset, str) and asset != "", "asset must be non-empty."
    report_data = valid_reports(asset)
    required = min_reporters[asset]
    assert report_data["count"] >= required, "Not enough fresh reports."
    return median_price(report_data["prices"])


@export
def get_reports(asset: str):
    assert isinstance(asset, str) and asset != "", "asset must be non-empty."
    reports = []
    maximum_age = max_age_seconds[asset]

    for reporter in current_reporters():
        if reporters[reporter] is not True:
            continue

        reports.append(
            {
                "reporter": reporter,
                "price": reported_prices[asset, reporter],
                "reported_at": reported_at[asset, reporter],
                "source": reported_sources[asset, reporter],
                "fresh": reported_at[asset, reporter] is not None
                and (
                    maximum_age <= 0
                    or elapsed_seconds(reported_at[asset, reporter]) <= maximum_age
                ),
            }
        )

    return reports


@export
def price_info(asset: str):
    assert isinstance(asset, str) and asset != "", "asset must be non-empty."
    report_data = valid_reports(asset)
    price = None
    if report_data["count"] >= min_reporters[asset]:
        price = median_price(report_data["prices"])

    return {
        "price": price,
        "min_reporters": min_reporters[asset],
        "max_age_seconds": max_age_seconds[asset],
        "report_count": report_data["count"],
        "freshest_report_at": report_data["freshest"],
        "oldest_report_at": report_data["oldest"],
    }
