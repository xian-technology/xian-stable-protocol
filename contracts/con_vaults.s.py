import time_checkpoints

BPS_DENOMINATOR = 10000
SECONDS_PER_YEAR = 31536000

vault_type_ids = Variable()
vault_type_count = Variable()
vault_count = Variable()

vault_types = Hash(default_value=None)
vaults = Hash(default_value=None)
auction_bids = Hash(default_value=0)
debt_group_rates = Hash(default_value=None)
debt_group_remaining = Hash(default_value=0)
debt_group_shares = Hash(default_value=0)
debt_group_carry = Hash(default_value=0)

stable_token_contract = Variable()
oracle_contract = Variable()
savings_contract = Variable()
treasury_address = Variable()
governor = Variable()
proposed_governor = Variable()
paused = Variable()

VaultTypeAddedEvent = LogEvent(
    "VaultTypeAdded",
    {
        "vault_type_id": {"type": int, "idx": True},
        "collateral_contract": {"type": str, "idx": True},
        "oracle_key": {"type": str, "idx": True},
    },
)

VaultOpenedEvent = LogEvent(
    "VaultOpened",
    {
        "vault_id": {"type": int, "idx": True},
        "owner": {"type": str, "idx": True},
        "vault_type_id": {"type": int, "idx": True},
        "collateral_amount": (int, decimal),
        "principal": (int, decimal),
    },
)

CollateralChangedEvent = LogEvent(
    "CollateralChanged",
    {
        "vault_id": {"type": int, "idx": True},
        "owner": {"type": str, "idx": True},
        "delta": (int, decimal),
        "direction": {"type": str, "idx": True},
        "collateral_amount": (int, decimal),
    },
)

DebtChangedEvent = LogEvent(
    "DebtChanged",
    {
        "vault_id": {"type": int, "idx": True},
        "payer": {"type": str, "idx": True},
        "direction": {"type": str, "idx": True},
        "principal_delta": (int, decimal),
        "fee_delta": (int, decimal),
    },
)

VaultClosedEvent = LogEvent(
    "VaultClosed",
    {
        "vault_id": {"type": int, "idx": True},
        "owner": {"type": str, "idx": True},
        "closer": {"type": str, "idx": True},
    },
)

LiquidationEvent = LogEvent(
    "Liquidation",
    {
        "vault_id": {"type": int, "idx": True},
        "liquidator": {"type": str, "idx": True},
        "debt_repaid": (int, decimal),
        "collateral_paid": (int, decimal),
        "partial": bool,
    },
)

AuctionOpenedEvent = LogEvent(
    "AuctionOpened",
    {
        "vault_id": {"type": int, "idx": True},
        "owner": {"type": str, "idx": True},
        "debt": (int, decimal),
        "end_time": str,
    },
)

AuctionRestartedEvent = LogEvent(
    "AuctionRestarted",
    {
        "vault_id": {"type": int, "idx": True},
        "owner": {"type": str, "idx": True},
        "debt": (int, decimal),
        "end_time": str,
    },
)

AuctionBidPlacedEvent = LogEvent(
    "AuctionBidPlaced",
    {
        "vault_id": {"type": int, "idx": True},
        "bidder": {"type": str, "idx": True},
        "bid_amount": (int, decimal),
        "end_time": str,
    },
)

AuctionCancelledEvent = LogEvent(
    "AuctionCancelled",
    {
        "vault_id": {"type": int, "idx": True},
        "owner": {"type": str, "idx": True},
        "reason": str,
    },
)

AuctionSettledEvent = LogEvent(
    "AuctionSettled",
    {
        "vault_id": {"type": int, "idx": True},
        "winner": {"type": str, "idx": True},
        "winning_bid": (int, decimal),
        "bad_debt": (int, decimal),
    },
)

AuctionRefundClaimedEvent = LogEvent(
    "AuctionRefundClaimed",
    {
        "vault_id": {"type": int, "idx": True},
        "claimer": {"type": str, "idx": True},
        "amount": (int, decimal),
    },
)

BadDebtCoveredEvent = LogEvent(
    "BadDebtCovered",
    {
        "vault_type_id": {"type": int, "idx": True},
        "amount": (int, decimal),
    },
)

RecapitalizedEvent = LogEvent(
    "Recapitalized",
    {
        "vault_type_id": {"type": int, "idx": True},
        "payer": {"type": str, "idx": True},
        "amount": (int, decimal),
        "bad_debt_reduced": (int, decimal),
        "surplus_added": (int, decimal),
    },
)

SurplusSweptEvent = LogEvent(
    "SurplusSwept",
    {
        "vault_type_id": {"type": int, "idx": True},
        "destination": {"type": str, "idx": True},
        "amount": (int, decimal),
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
def seed(
    stable_token_contract_name: str,
    oracle_contract_name: str,
    governor_address: str = None,
    savings_contract_name: str = "",
    treasury_address_value: str = "",
):
    assert isinstance(stable_token_contract_name, str) and stable_token_contract_name != "", "stable_token_contract_name must be non-empty."
    assert isinstance(oracle_contract_name, str) and oracle_contract_name != "", "oracle_contract_name must be non-empty."
    assert isinstance(savings_contract_name, str), "savings_contract_name must be a string."
    assert isinstance(treasury_address_value, str), "treasury_address_value must be a string."

    resolved_governor = governor_address
    if resolved_governor is None or resolved_governor == "":
        resolved_governor = ctx.caller

    require_savings_contract(savings_contract_name)

    stable_token_contract.set(stable_token_contract_name)
    oracle_contract.set(oracle_contract_name)
    savings_contract.set(savings_contract_name)
    treasury_address.set(treasury_address_value)
    governor.set(resolved_governor)
    proposed_governor.set(None)
    paused.set(False)
    vault_type_ids.set([])
    vault_type_count.set(0)
    vault_count.set(0)


def stable_token():
    return importlib.import_module(stable_token_contract.get())


def require_savings_contract(name: str):
    if name != "":
        assert importlib.has_export(name, "total_supply"), (
            "savings contract must export total_supply."
        )


def oracle():
    return importlib.import_module(oracle_contract.get())


def require_governor():
    assert ctx.caller == governor.get(), "Only governor can call."


def assert_not_paused():
    assert paused.get() is not True, "Protocol is paused."


def current_vault_type_ids():
    ids = vault_type_ids.get()
    if ids is None:
        return []
    return ids


def current_time():
    return now




def seconds_until(target_time):
    if target_time is None:
        return 0
    delta = target_time - current_time()
    remaining = delta.seconds
    if remaining < 0:
        return 0
    return remaining


def vault_value(vault_id: int, field: str, fallback: Any = None):
    value = vaults[vault_id, field]
    return fallback if value is None else value


def vault_type_value(vault_type_id: int, field: str, fallback: Any = None):
    value = vault_types[vault_type_id, field]
    if value is None:
        return fallback
    return value


def require_vault_type_exists(vault_type_id: int):
    assert vault_type_value(vault_type_id, "collateral_contract") is not None, "Vault type does not exist."


def require_vault_type(vault_type_id: int):
    require_vault_type_exists(vault_type_id)
    assert vault_type_value(vault_type_id, "active", False) is True, "Vault type is inactive."


def collateral_contract(vault_type_id: int):
    return importlib.import_module(vault_type_value(vault_type_id, "collateral_contract"))


def receive_collateral(vault_type_id: int, amount: Any):
    token = collateral_contract(vault_type_id)
    balance_before = token.balance_of(address=ctx.this)
    token.transfer_from(amount=amount, to=ctx.this, main_account=ctx.caller)
    assert token.balance_of(address=ctx.this) == balance_before + amount, "Vault requires an exact collateral transfer."


def current_oracle_price(vault_type_id: int):
    return oracle().get_price(asset=vault_type_value(vault_type_id, "oracle_key"))



def elapsed_to(since_time, until_time):
    if since_time is None:
        return 0
    return max(0, (until_time - since_time).seconds)


def linear_rate(base, fee_bps, since_time, until_time):
    return base * (1 + fee_bps * elapsed_to(since_time, until_time) / SECONDS_PER_YEAR / BPS_DENOMINATOR)


def fee_anchor(vault_type_id: int):
    height = vault_type_value(vault_type_id, "pending_fee_height")
    if height is None:
        return None
    return time_checkpoints.get_anchor(height=height)


def effective_fee(vault_type_id: int):
    if fee_anchor(vault_type_id) is not None:
        return vault_type_value(vault_type_id, "pending_fee_bps")
    return vault_type_value(vault_type_id, "stability_fee_bps")


def rate_events(vault_type_id: int):
    events = []
    debt_height = vault_type_value(vault_type_id, "pending_debt_height")
    if debt_height is not None:
        anchor = time_checkpoints.get_anchor(height=debt_height)
        if anchor is not None:
            events.append({"time": anchor, "fee": None})
    pending_fee = vault_type_value(vault_type_id, "pending_fee_bps")
    anchor = fee_anchor(vault_type_id)
    if anchor is not None and pending_fee != vault_type_value(vault_type_id, "stability_fee_bps", 0):
        events.append({"time": anchor, "fee": pending_fee})
    if len(events) == 2 and events[0]["time"] > events[1]["time"]:
        return [events[1], events[0]]
    return events


def rate_at(vault_type_id: int, until_time):
    base = vault_type_value(vault_type_id, "rate_accumulator", 1)
    since_time = vault_type_value(vault_type_id, "last_rate_time")
    fee = vault_type_value(vault_type_id, "stability_fee_bps", 0)
    # At most one ready debt group and one ready fee change; no history scan.
    for event in rate_events(vault_type_id):
        if event["time"] <= until_time:
            assert since_time is None or event["time"] >= since_time, "Rate checkpoint precedes its base."
            base = linear_rate(base, fee, since_time, event["time"])
            since_time = event["time"]
            if event["fee"] is not None:
                fee = event["fee"]
    return linear_rate(base, fee, since_time, until_time)


def raw_live_shares_total(vault_type_id: int):
    return vault_type_value(vault_type_id, "normalized_debt_total", 0)


def pending_group_debt(vault_type_id: int):
    return vault_type_value(vault_type_id, "pending_debt_total", 0)


def group_rate(vault_type_id: int, height: int):
    stored = debt_group_rates[vault_type_id, height]
    if stored is not None:
        return stored
    assert vault_type_value(vault_type_id, "pending_debt_height") == height, "Missing debt checkpoint group."
    anchor = time_checkpoints.get_anchor(height=height)
    if anchor is None:
        return None
    since = vault_type_value(vault_type_id, "last_rate_time")
    assert since is None or anchor >= since, "Debt checkpoint precedes the rate base."
    return rate_at(vault_type_id, anchor)


def normalize_debt(debt: Any, rate: Any):
    shares = debt / rate
    return {"shares": shares, "carry": debt - shares * rate}


def raw_live_carry_total(vault_type_id: int):
    return vault_type_value(vault_type_id, "debt_carry_total", 0)


def raw_vault_carry(vault_id: int):
    return vault_value(vault_id, "debt_carry", 0)


def adjust_type_components(vault_type_id: int, shares: Any, carry: Any):
    # Only exact owner deltas change totals; aggregate carry is never normalized.
    vault_types[vault_type_id, "normalized_debt_total"] = raw_live_shares_total(vault_type_id) + shares
    vault_types[vault_type_id, "debt_carry_total"] = raw_live_carry_total(vault_type_id) + carry


def write_vault_debt(vault_id: int, debt: Any, rate: Any):
    parts = normalize_debt(debt, rate)
    adjust_type_components(vault_type_id_of(vault_id), parts["shares"] - raw_vault_shares(vault_id), parts["carry"] - raw_vault_carry(vault_id))
    vaults[vault_id, "debt_shares"] = parts["shares"]
    vaults[vault_id, "debt_carry"] = parts["carry"]


def allocate_group(vault_type_id: int, height: int, debt: Any, parts: dict):
    remaining = debt_group_remaining[vault_type_id, height] - debt
    shares = debt_group_shares[vault_type_id, height] - parts["shares"]
    carry = remaining - shares * debt_group_rates[vault_type_id, height]
    assert remaining >= 0 and shares >= 0, "Invalid debt checkpoint remainder."
    # Splitting fixed-decimal multiplication can cost one quantum. Preserve each
    # owner's exact anchor debt and record that exact component delta globally.
    adjust_type_components(vault_type_id, 0, parts["carry"] + carry - debt_group_carry[vault_type_id, height])
    debt_group_remaining[vault_type_id, height] = remaining
    debt_group_shares[vault_type_id, height] = shares
    debt_group_carry[vault_type_id, height] = carry
    if remaining == 0:
        assert shares == 0 and carry == 0, "Debt checkpoint components remain."
        debt_group_rates[vault_type_id, height] = None
        debt_group_remaining[vault_type_id, height] = None
        debt_group_shares[vault_type_id, height] = None
        debt_group_carry[vault_type_id, height] = None


def group_projection(vault_type_id: int):
    height = vault_type_value(vault_type_id, "pending_debt_height")
    if height is None:
        return {"shares": 0, "carry": 0, "unanchored_debt": 0}
    debt = pending_group_debt(vault_type_id)
    rate = group_rate(vault_type_id, height)
    if rate is None:
        return {"shares": 0, "carry": 0, "unanchored_debt": debt}
    parts = normalize_debt(debt, rate)
    return {"shares": parts["shares"], "carry": parts["carry"], "unanchored_debt": 0}


def clear_pending_group(vault_type_id: int):
    vault_types[vault_type_id, "pending_debt_height"] = None
    vault_types[vault_type_id, "pending_debt_total"] = 0


def materialize_group(vault_type_id: int):
    height = vault_type_value(vault_type_id, "pending_debt_height")
    if height is None:
        return False
    rate = group_rate(vault_type_id, height)
    if rate is None:
        return False
    debt = pending_group_debt(vault_type_id)
    assert debt > 0, "Invalid debt checkpoint conversion."
    parts = normalize_debt(debt, rate)
    debt_group_rates[vault_type_id, height] = rate
    debt_group_remaining[vault_type_id, height] = debt
    debt_group_shares[vault_type_id, height] = parts["shares"]
    debt_group_carry[vault_type_id, height] = parts["carry"]
    adjust_type_components(vault_type_id, parts["shares"], parts["carry"])
    clear_pending_group(vault_type_id)
    return True


def materialize_fee(vault_type_id: int):
    anchor = fee_anchor(vault_type_id)
    if anchor is None:
        return False
    vault_types[vault_type_id, "stability_fee_bps"] = vault_type_value(vault_type_id, "pending_fee_bps")
    vault_types[vault_type_id, "pending_fee_height"] = None
    vault_types[vault_type_id, "pending_fee_bps"] = None
    return True


def vault_pending_debt(vault_id: int):
    return vault_value(vault_id, "pending_debt", 0)


def vault_pending_principal(vault_id: int):
    return vault_value(vault_id, "pending_principal", 0)


def raw_vault_shares(vault_id: int):
    return vault_value(vault_id, "debt_shares", 0)


def pending_vault_projection(vault_id: int):
    debt = vault_pending_debt(vault_id)
    if debt <= 0:
        return {"shares": 0, "carry": 0, "unanchored_debt": 0}
    vault_type_id = vault_type_id_of(vault_id)
    height = vaults[vault_id, "pending_debt_height"]
    rate = group_rate(vault_type_id, height)
    if rate is None:
        return {"shares": 0, "carry": 0, "unanchored_debt": debt}
    shares = debt / rate
    if debt_group_remaining[vault_type_id, height] == debt:
        shares = debt_group_shares[vault_type_id, height]
    return {"shares": shares, "carry": debt - shares * rate, "unanchored_debt": 0}


def clear_vault_pending(vault_id: int):
    vaults[vault_id, "pending_debt"] = 0
    vaults[vault_id, "pending_principal"] = 0
    vaults[vault_id, "pending_debt_height"] = None


def materialize_vault(vault_id: int):
    debt = vault_pending_debt(vault_id)
    if debt <= 0:
        return False
    vault_type_id = vault_type_id_of(vault_id)
    materialize_group(vault_type_id)
    height = vaults[vault_id, "pending_debt_height"]
    if debt_group_rates[vault_type_id, height] is None:
        return False
    parts = pending_vault_projection(vault_id)
    allocate_group(vault_type_id, height, debt, parts)
    shares = raw_vault_shares(vault_id) + parts["shares"]
    carry = raw_vault_carry(vault_id) + parts["carry"]
    vaults[vault_id, "debt_shares"] = shares
    vaults[vault_id, "debt_carry"] = carry
    clear_vault_pending(vault_id)
    write_vault_debt(vault_id, shares * current_rate(vault_type_id) + carry, current_rate(vault_type_id))
    return True


def new_debt_height(vault_type_id: int):
    height = time_checkpoints.request_anchor()
    materialize_group(vault_type_id)
    old_height = vault_type_value(vault_type_id, "pending_debt_height")
    assert old_height is None or old_height == height, "Earlier debt checkpoint anchor is pending."
    return height


def add_pending_debt(vault_id: int, debt: Any, principal: Any, height: int):
    vault_type_id = vault_type_id_of(vault_id)
    old_height = vaults[vault_id, "pending_debt_height"]
    assert old_height is None or old_height == height, "Earlier vault debt checkpoint anchor is pending."
    vaults[vault_id, "pending_debt_height"] = height
    vaults[vault_id, "pending_debt"] = vault_pending_debt(vault_id) + debt
    vaults[vault_id, "pending_principal"] = vault_pending_principal(vault_id) + principal
    vaults[vault_id, "principal"] = vault_live_principal(vault_id) + principal
    vault_types[vault_type_id, "pending_debt_height"] = height
    vault_types[vault_type_id, "pending_debt_total"] = pending_group_debt(vault_type_id) + debt
    vault_types[vault_type_id, "principal_outstanding"] = current_live_principal_outstanding(vault_type_id) + principal


def remove_pending_debt(vault_id: int, debt: Any, principal: Any):
    vault_type_id = vault_type_id_of(vault_id)
    remaining = vault_pending_debt(vault_id) - debt
    vaults[vault_id, "pending_debt"] = remaining
    vaults[vault_id, "pending_principal"] = vault_pending_principal(vault_id) - principal
    vault_types[vault_type_id, "pending_debt_total"] = pending_group_debt(vault_type_id) - debt
    if remaining == 0:
        clear_vault_pending(vault_id)
    if pending_group_debt(vault_type_id) == 0:
        clear_pending_group(vault_type_id)


def current_rate(vault_type_id: int):
    return rate_at(vault_type_id, current_time())


def accrue_vault_type(vault_type_id: int):
    # Resolve the bounded group before advancing its rate history; fee changes
    # use their own immutable breakpoint and may precede the debt anchor.
    updated_rate = current_rate(vault_type_id)
    materialize_group(vault_type_id)
    materialize_fee(vault_type_id)
    vault_types[vault_type_id, "rate_accumulator"] = updated_rate
    vault_types[vault_type_id, "last_rate_time"] = current_time()
    return updated_rate


def current_live_shares_total(vault_type_id: int):
    return raw_live_shares_total(vault_type_id) + group_projection(vault_type_id)["shares"]


def current_live_principal_outstanding(vault_type_id: int):
    return vault_type_value(vault_type_id, "principal_outstanding", 0)


def current_locked_debt(vault_type_id: int):
    return vault_type_value(vault_type_id, "auction_debt_locked", 0)


def current_locked_principal(vault_type_id: int):
    return vault_type_value(vault_type_id, "auction_principal_locked", 0)


def current_total_debt(vault_type_id: int, rate: Any = None):
    if rate is None:
        rate = current_rate(vault_type_id)
    group = group_projection(vault_type_id)
    return current_live_shares_total(vault_type_id) * rate + raw_live_carry_total(vault_type_id) + group["carry"] + group["unanchored_debt"] + current_locked_debt(vault_type_id)


def require_vault_exists(vault_id: int):
    assert vaults[vault_id, "owner"] is not None, "Vault does not exist."


def require_open_vault(vault_id: int):
    require_vault_exists(vault_id)
    assert vaults[vault_id, "open"] is True, "Vault is not open."


def require_vault_owner(vault_id: int):
    require_open_vault(vault_id)
    assert vaults[vault_id, "owner"] == ctx.caller, "Only vault owner can call."


def require_not_in_auction(vault_id: int):
    assert vaults[vault_id, "auction_open"] is not True, "Vault is in auction."


def vault_type_id_of(vault_id: int):
    return vaults[vault_id, "vault_type_id"]


def vault_owner_of(vault_id: int):
    return vaults[vault_id, "owner"]


def vault_collateral(vault_id: int):
    return vault_value(vault_id, "collateral_amount", 0)


def vault_live_shares(vault_id: int):
    return raw_vault_shares(vault_id) + pending_vault_projection(vault_id)["shares"]


def vault_live_principal(vault_id: int):
    return vault_value(vault_id, "principal", 0)


def vault_snapshot_debt(vault_id: int):
    return vault_value(vault_id, "auction_debt_snapshot", 0)


def vault_snapshot_principal(vault_id: int):
    return vault_value(vault_id, "auction_principal_snapshot", 0)




def collateral_value_amount(
    vault_type_id: int,
    collateral_amount: Any,
):
    return collateral_amount * current_oracle_price(vault_type_id)


def collateral_value(vault_id: int):
    return collateral_value_amount(vault_type_id_of(vault_id), vault_collateral(vault_id))


def vault_live_debt(vault_id: int, rate: Any = None):
    if rate is None:
        rate = current_rate(vault_type_id_of(vault_id))
    group = pending_vault_projection(vault_id)
    return vault_live_shares(vault_id) * rate + raw_vault_carry(vault_id) + group["carry"] + group["unanchored_debt"]


def vault_total_debt(vault_id: int, rate: Any = None):
    if vaults[vault_id, "auction_open"] is True:
        return vault_snapshot_debt(vault_id)
    return vault_live_debt(vault_id, rate)


def vault_total_principal(vault_id: int):
    if vaults[vault_id, "auction_open"] is True:
        return vault_snapshot_principal(vault_id)
    return vault_live_principal(vault_id)


def vault_fee_due(vault_id: int, rate: Any = None):
    debt = vault_total_debt(vault_id, rate)
    principal = vault_total_principal(vault_id)
    fees = debt - principal
    if fees < 0:
        return 0
    return fees


def collateralization_bps_for(
    vault_type_id: int,
    collateral_amount: Any,
    debt_amount: Any,
):
    if debt_amount <= 0:
        return 10 ** 18
    return (
        collateral_value_amount(vault_type_id, collateral_amount)
        * BPS_DENOMINATOR
        / debt_amount
    )


def collateralization_bps(vault_id: int, debt_amount: Any = None):
    if debt_amount is None:
        debt_amount = vault_total_debt(vault_id)
    return collateralization_bps_for(
        vault_type_id_of(vault_id),
        vault_collateral(vault_id),
        debt_amount,
    )


def route_fee_income(vault_type_id: int, amount: Any):
    if amount <= 0:
        return

    surplus_share_bps = vault_type_value(vault_type_id, "surplus_buffer_bps", 0)
    buffer_amount = amount * surplus_share_bps / BPS_DENOMINATOR
    distributed_amount = amount - buffer_amount

    if buffer_amount > 0:
        vault_types[vault_type_id, "surplus_buffer"] = (
            vault_type_value(vault_type_id, "surplus_buffer", 0)
            + buffer_amount
        )

    if distributed_amount <= 0:
        return

    destination = fee_destination()
    if destination != ctx.this:
        stable_token().transfer(amount=distributed_amount, to=destination)

    vault_types[vault_type_id, "fees_distributed"] = (
        vault_type_value(vault_type_id, "fees_distributed", 0)
        + distributed_amount
    )


def fee_destination():
    # Savings earns protocol income only while it has depositors; earlier
    # income would otherwise sit in the empty vault for the first depositor.
    destination = savings_contract.get()
    if destination is not None and destination != "":
        if importlib.import_module(destination).total_supply() > 0:
            return destination
    destination = treasury_address.get()
    if destination is None or destination == "":
        destination = governor.get()
    return destination


def burn_principal(amount: Any):
    if amount <= 0:
        return
    stable_token().burn(amount=amount)


def repayment_parts(debt: Any, principal: Any, amount: Any):
    amount = min(amount, debt)
    fee_paid = min(amount, max(0, debt - principal))
    principal_paid = min(principal, amount - fee_paid)
    return {"total_paid": amount, "fee_paid": fee_paid, "principal_paid": principal_paid}


def apply_live_repayment(vault_id: int, amount: Any, rate: Any = None):
    if rate is None:
        rate = current_rate(vault_type_id_of(vault_id))
    materialize_vault(vault_id)
    debt = vault_live_debt(vault_id, rate)
    principal_due = vault_live_principal(vault_id)
    parts = repayment_parts(debt, principal_due, amount)
    amount = parts["total_paid"]
    fee_paid = parts["fee_paid"]
    principal_paid = parts["principal_paid"]
    pending_fees = max(0, vault_pending_debt(vault_id) - vault_pending_principal(vault_id))
    pending_fee_paid = min(fee_paid, pending_fees)
    pending_principal_paid = min(principal_paid, vault_pending_principal(vault_id))
    pending_paid = pending_fee_paid + pending_principal_paid
    active_paid = amount - pending_paid
    active_debt = raw_vault_shares(vault_id) * rate + raw_vault_carry(vault_id)
    if pending_paid > 0:
        remove_pending_debt(vault_id, pending_paid, pending_principal_paid)
    write_vault_debt(vault_id, active_debt - active_paid, rate)
    vaults[vault_id, "principal"] = principal_due - principal_paid
    vault_type_id = vault_type_id_of(vault_id)
    vault_types[vault_type_id, "principal_outstanding"] = current_live_principal_outstanding(vault_type_id) - principal_paid
    if fee_paid > 0:
        route_fee_income(vault_type_id, fee_paid)
    if principal_paid > 0:
        burn_principal(principal_paid)
    return {"total_paid": amount, "fee_paid": fee_paid, "principal_paid": principal_paid}


def apply_auction_repayment(vault_id: int, amount: Any):
    debt = vault_snapshot_debt(vault_id)
    principal_due = vault_snapshot_principal(vault_id)
    parts = repayment_parts(debt, principal_due, amount)
    amount = parts["total_paid"]
    fee_paid = parts["fee_paid"]
    principal_paid = parts["principal_paid"]

    new_debt = debt - amount

    new_principal = principal_due - principal_paid

    vaults[vault_id, "auction_debt_snapshot"] = new_debt
    vaults[vault_id, "auction_principal_snapshot"] = new_principal

    vault_types[vault_type_id_of(vault_id), "auction_debt_locked"] = (
        current_locked_debt(vault_type_id_of(vault_id)) - amount
    )
    vault_types[vault_type_id_of(vault_id), "auction_principal_locked"] = (
        current_locked_principal(vault_type_id_of(vault_id)) - principal_paid
    )

    if fee_paid > 0:
        route_fee_income(vault_type_id_of(vault_id), fee_paid)
    if principal_paid > 0:
        burn_principal(principal_paid)

    return {
        "total_paid": amount,
        "fee_paid": fee_paid,
        "principal_paid": principal_paid,
    }



def auction_clock(vault_id: int):
    opened = vaults[vault_id, "auction_opened_at"]
    end_time = vaults[vault_id, "auction_end_time"]
    height = vaults[vault_id, "auction_anchor_height"]
    if opened is None and height is not None:
        opened = time_checkpoints.get_anchor(height=height)
        if opened is not None:
            end_time = opened + datetime.timedelta(seconds=vaults[vault_id, "auction_duration_seconds"])
    extension_height = vaults[vault_id, "auction_extension_height"]
    if extension_height is not None:
        anchor = time_checkpoints.get_anchor(height=extension_height)
        if anchor is None:
            return {"opened": opened, "end": None}
        end_time = max(end_time, anchor + datetime.timedelta(seconds=vaults[vault_id, "auction_extension_seconds"]))
    return {"opened": opened, "end": end_time}


def materialize_auction_clock(vault_id: int):
    window = auction_clock(vault_id)
    if window["end"] is None:
        return None
    vaults[vault_id, "auction_opened_at"] = window["opened"]
    vaults[vault_id, "auction_end_time"] = window["end"]
    vaults[vault_id, "auction_extension_height"] = None
    vaults[vault_id, "auction_extension_seconds"] = 0
    return window["end"]


def begin_auction_clock(vault_id: int):
    height = time_checkpoints.request_anchor()
    vaults[vault_id, "auction_anchor_height"] = height
    vaults[vault_id, "auction_duration_seconds"] = vault_type_value(vault_type_id_of(vault_id), "auction_duration_seconds")
    vaults[vault_id, "auction_opened_at"] = None
    vaults[vault_id, "auction_end_time"] = None
    vaults[vault_id, "auction_extension_height"] = None
    vaults[vault_id, "auction_extension_seconds"] = 0
    return None


def clear_auction(vault_id: int):
    vaults[vault_id, "auction_open"] = False
    vaults[vault_id, "auction_extension_height"] = None
    vaults[vault_id, "auction_extension_seconds"] = 0
    vaults[vault_id, "auction_anchor_height"] = None
    vaults[vault_id, "auction_duration_seconds"] = None
    vaults[vault_id, "auction_opened_at"] = None
    vaults[vault_id, "auction_end_time"] = None
    vaults[vault_id, "auction_highest_bidder"] = ""
    vaults[vault_id, "auction_highest_bid"] = 0
    vaults[vault_id, "auction_debt_snapshot"] = 0
    vaults[vault_id, "auction_principal_snapshot"] = 0


def close_vault_record(vault_id: int):
    vaults[vault_id, "open"] = False
    vaults[vault_id, "debt_shares"] = 0
    vaults[vault_id, "debt_carry"] = 0
    vaults[vault_id, "principal"] = 0
    vaults[vault_id, "closed_at"] = current_time()
    clear_vault_pending(vault_id)
    clear_auction(vault_id)


def restore_auction_to_live(vault_id: int):
    vault_type_id = vault_type_id_of(vault_id)
    accrue_vault_type(vault_type_id)
    remaining_debt = vault_snapshot_debt(vault_id)
    remaining_principal = vault_snapshot_principal(vault_id)

    vault_types[vault_type_id, "auction_debt_locked"] = (
        current_locked_debt(vault_type_id) - remaining_debt
    )
    vault_types[vault_type_id, "auction_principal_locked"] = (
        current_locked_principal(vault_type_id) - remaining_principal
    )

    if remaining_debt <= 0:
        clear_auction(vault_id)
        return

    height = new_debt_height(vault_type_id)
    vaults[vault_id, "debt_shares"] = 0
    vaults[vault_id, "debt_carry"] = 0
    vaults[vault_id, "principal"] = 0
    clear_vault_pending(vault_id)
    add_pending_debt(vault_id, remaining_debt, remaining_principal, height)
    clear_auction(vault_id)


def required_min_ratio(vault_type_id: int):
    return vault_type_value(vault_type_id, "min_collateral_ratio_bps")


def required_liquidation_ratio(vault_type_id: int):
    return vault_type_value(vault_type_id, "liquidation_ratio_bps")


def partial_liquidation_target_ratio(vault_type_id: int):
    target_ratio = vault_type_value(
        vault_type_id,
        "partial_liquidation_target_ratio_bps",
    )
    if target_ratio is None:
        return required_min_ratio(vault_type_id)
    return target_ratio


def collateral_out_for_repayment(vault_type_id: int, repay_amount: Any):
    price = current_oracle_price(vault_type_id)
    bonus_bps = vault_type_value(vault_type_id, "liquidation_bonus_bps", 0)
    return (
        repay_amount
        * (BPS_DENOMINATOR + bonus_bps)
        / BPS_DENOMINATOR
        / price
    )


def required_partial_repayment(vault_id: int):
    vault_type_id = vault_type_id_of(vault_id)
    debt = vault_live_debt(vault_id)
    if debt <= 0:
        return 0

    collateral_value_now = collateral_value(vault_id)
    target_bps = partial_liquidation_target_ratio(vault_type_id)
    numerator = debt * target_bps - collateral_value_now * BPS_DENOMINATOR
    if numerator <= 0:
        return 0

    denominator = target_bps - (
        BPS_DENOMINATOR
        + vault_type_value(vault_type_id, "liquidation_bonus_bps", 0)
    )
    if denominator <= 0:
        return debt

    repayment = numerator / denominator
    if repayment > debt:
        repayment = debt
    return repayment


def liquidation_quote_internal(vault_id: int):
    vault_type_id = vault_type_id_of(vault_id)
    debt = vault_live_debt(vault_id)
    required_repayment = required_partial_repayment(vault_id)
    if required_repayment < 0:
        required_repayment = 0

    partial_possible = required_repayment > 0 and required_repayment < debt
    collateral_out = 0
    if required_repayment > 0:
        collateral_out = collateral_out_for_repayment(
            vault_type_id, required_repayment
        )

    if collateral_out > vault_collateral(vault_id):
        partial_possible = False

    return {
        "debt": debt,
        "required_repayment": required_repayment,
        "collateral_out": collateral_out,
        "partial_possible": partial_possible,
    }


def reserve_bid(vault_id: int):
    # The opening bid must repay the debt, or, when the collateral is worth less,
    # buy the collateral at no more than the liquidation-bonus discount. This
    # keeps a lone bidder from winning collateral for a token amount.
    if vaults[vault_id, "auction_open"] is not True:
        return 0
    bonus_bps = vault_type_value(vault_type_id_of(vault_id), "liquidation_bonus_bps", 0)
    discounted_value = (
        collateral_value(vault_id) * (BPS_DENOMINATOR - bonus_bps) / BPS_DENOMINATOR
    )
    reserve = min(vault_snapshot_debt(vault_id), discounted_value)
    if reserve < 0:
        return 0
    return reserve


def min_next_bid(vault_id: int):
    highest_bid = vaults[vault_id, "auction_highest_bid"]
    if highest_bid is None or highest_bid <= 0:
        return reserve_bid(vault_id)
    increment_bps = vault_type_value(
        vault_type_id_of(vault_id), "min_bid_increment_bps", 0
    )
    return highest_bid * (BPS_DENOMINATOR + increment_bps) / BPS_DENOMINATOR


@export
def governor_of():
    return governor.get()


@export
def is_paused():
    return paused.get() is True


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
    GovernanceTransferredEvent(
        {
            "previous_governor": previous,
            "new_governor": pending,
        }
    )


@export
def set_paused(value: bool):
    require_governor()
    paused.set(value)


@export
def set_savings_contract(target_contract: str):
    require_governor()
    assert isinstance(target_contract, str), "target_contract must be a string."
    require_savings_contract(target_contract)
    savings_contract.set(target_contract)


@export
def set_treasury_address(address: str):
    require_governor()
    assert isinstance(address, str), "address must be a string."
    treasury_address.set(address)


@export
def add_vault_type(
    collateral_contract_name: str,
    oracle_key: str,
    min_collateral_ratio_bps: int,
    liquidation_ratio_bps: int,
    liquidation_bonus_bps: int,
    debt_ceiling: Any,
    min_debt: Any,
    stability_fee_bps: int,
    auction_duration_seconds: int,
    partial_liquidation_target_ratio_bps: int = None,
    surplus_buffer_bps: int = 2000,
    min_bid_increment_bps: int = 500,
    extension_window_seconds: int = 3600,
    bid_extension_seconds: int = 3600,
):
    require_governor()
    assert isinstance(collateral_contract_name, str) and collateral_contract_name != "", "collateral_contract_name must be non-empty."
    assert isinstance(oracle_key, str) and oracle_key != "", "oracle_key must be non-empty."
    assert min_collateral_ratio_bps > 0, "min_collateral_ratio_bps must be positive."
    assert liquidation_ratio_bps > 0, "liquidation_ratio_bps must be positive."
    assert liquidation_ratio_bps <= min_collateral_ratio_bps, "liquidation ratio must be <= minimum ratio."
    assert liquidation_bonus_bps >= 0, "liquidation_bonus_bps must be non-negative."
    assert isinstance(debt_ceiling, (int, decimal)), "debt_ceiling must be numeric."
    assert debt_ceiling > 0, "debt_ceiling must be positive."
    assert isinstance(min_debt, (int, decimal)), "min_debt must be numeric."
    assert min_debt >= 0, "min_debt must be non-negative."
    assert stability_fee_bps >= 0, "stability_fee_bps must be non-negative."
    assert auction_duration_seconds > 0, "auction_duration_seconds must be positive."
    assert surplus_buffer_bps >= 0, "surplus_buffer_bps must be non-negative."
    assert surplus_buffer_bps <= BPS_DENOMINATOR, "surplus_buffer_bps must be <= 10000."
    assert min_bid_increment_bps >= 0, "min_bid_increment_bps must be non-negative."
    assert extension_window_seconds >= 0, "extension_window_seconds must be non-negative."
    assert bid_extension_seconds >= 0, "bid_extension_seconds must be non-negative."

    if partial_liquidation_target_ratio_bps is None:
        partial_liquidation_target_ratio_bps = min_collateral_ratio_bps

    assert partial_liquidation_target_ratio_bps >= min_collateral_ratio_bps, "partial liquidation target must be >= min ratio."

    vault_type_id = vault_type_count.get() + 1
    vault_type_count.set(vault_type_id)
    vault_type_ids.set(current_vault_type_ids() + [vault_type_id])

    vault_types[vault_type_id, "active"] = True
    vault_types[vault_type_id, "collateral_contract"] = collateral_contract_name
    vault_types[vault_type_id, "oracle_key"] = oracle_key
    vault_types[vault_type_id, "min_collateral_ratio_bps"] = min_collateral_ratio_bps
    vault_types[vault_type_id, "liquidation_ratio_bps"] = liquidation_ratio_bps
    vault_types[vault_type_id, "liquidation_bonus_bps"] = liquidation_bonus_bps
    vault_types[vault_type_id, "partial_liquidation_target_ratio_bps"] = partial_liquidation_target_ratio_bps
    vault_types[vault_type_id, "debt_ceiling"] = debt_ceiling
    vault_types[vault_type_id, "min_debt"] = min_debt
    vault_types[vault_type_id, "stability_fee_bps"] = stability_fee_bps
    vault_types[vault_type_id, "auction_duration_seconds"] = auction_duration_seconds
    vault_types[vault_type_id, "surplus_buffer_bps"] = surplus_buffer_bps
    vault_types[vault_type_id, "min_bid_increment_bps"] = min_bid_increment_bps
    vault_types[vault_type_id, "extension_window_seconds"] = extension_window_seconds
    vault_types[vault_type_id, "bid_extension_seconds"] = bid_extension_seconds
    vault_types[vault_type_id, "rate_accumulator"] = 1
    vault_types[vault_type_id, "last_rate_time"] = current_time()
    vault_types[vault_type_id, "normalized_debt_total"] = 0
    vault_types[vault_type_id, "debt_carry_total"] = 0
    vault_types[vault_type_id, "principal_outstanding"] = 0
    vault_types[vault_type_id, "auction_debt_locked"] = 0
    vault_types[vault_type_id, "auction_principal_locked"] = 0
    vault_types[vault_type_id, "surplus_buffer"] = 0
    vault_types[vault_type_id, "fees_distributed"] = 0
    vault_types[vault_type_id, "bad_debt"] = 0

    VaultTypeAddedEvent(
        {
            "vault_type_id": vault_type_id,
            "collateral_contract": collateral_contract_name,
            "oracle_key": oracle_key,
        }
    )
    return vault_type_id


@export
def set_vault_type_active(vault_type_id: int, active: bool):
    require_governor()
    require_vault_type_exists(vault_type_id)
    vault_types[vault_type_id, "active"] = active


@export
def set_vault_type_fee(vault_type_id: int, stability_fee_bps: int):
    require_governor()
    require_vault_type_exists(vault_type_id)
    assert stability_fee_bps >= 0, "stability_fee_bps must be non-negative."
    accrue_vault_type(vault_type_id)
    height = time_checkpoints.request_anchor()
    previous = vault_type_value(vault_type_id, "pending_fee_height")
    assert previous is None or previous == height, "Earlier fee checkpoint anchor is pending."
    vault_types[vault_type_id, "pending_fee_height"] = height
    vault_types[vault_type_id, "pending_fee_bps"] = stability_fee_bps


@export
def set_vault_type_limits(vault_type_id: int, debt_ceiling: Any, min_debt: Any):
    require_governor()
    assert isinstance(debt_ceiling, (int, decimal)), "debt_ceiling must be numeric."
    assert debt_ceiling > 0, "debt_ceiling must be positive."
    assert isinstance(min_debt, (int, decimal)), "min_debt must be numeric."
    assert min_debt >= 0, "min_debt must be non-negative."
    vault_types[vault_type_id, "debt_ceiling"] = debt_ceiling
    vault_types[vault_type_id, "min_debt"] = min_debt


@export
def set_vault_type_ratios(
    vault_type_id: int,
    min_collateral_ratio_bps: int,
    liquidation_ratio_bps: int,
    liquidation_bonus_bps: int,
    partial_liquidation_target_ratio_bps: int = None,
):
    require_governor()
    assert min_collateral_ratio_bps > 0, "min_collateral_ratio_bps must be positive."
    assert liquidation_ratio_bps > 0, "liquidation_ratio_bps must be positive."
    assert liquidation_ratio_bps <= min_collateral_ratio_bps, "liquidation ratio must be <= minimum ratio."
    assert liquidation_bonus_bps >= 0, "liquidation_bonus_bps must be non-negative."
    if partial_liquidation_target_ratio_bps is None:
        partial_liquidation_target_ratio_bps = min_collateral_ratio_bps
    assert partial_liquidation_target_ratio_bps >= min_collateral_ratio_bps, "partial liquidation target must be >= min ratio."

    vault_types[vault_type_id, "min_collateral_ratio_bps"] = min_collateral_ratio_bps
    vault_types[vault_type_id, "liquidation_ratio_bps"] = liquidation_ratio_bps
    vault_types[vault_type_id, "liquidation_bonus_bps"] = liquidation_bonus_bps
    vault_types[vault_type_id, "partial_liquidation_target_ratio_bps"] = partial_liquidation_target_ratio_bps


@export
def set_vault_type_auction_config(
    vault_type_id: int,
    auction_duration_seconds: int,
    min_bid_increment_bps: int,
    extension_window_seconds: int,
    bid_extension_seconds: int,
):
    require_governor()
    assert auction_duration_seconds > 0, "auction_duration_seconds must be positive."
    assert min_bid_increment_bps >= 0, "min_bid_increment_bps must be non-negative."
    assert extension_window_seconds >= 0, "extension_window_seconds must be non-negative."
    assert bid_extension_seconds >= 0, "bid_extension_seconds must be non-negative."

    vault_types[vault_type_id, "auction_duration_seconds"] = auction_duration_seconds
    vault_types[vault_type_id, "min_bid_increment_bps"] = min_bid_increment_bps
    vault_types[vault_type_id, "extension_window_seconds"] = extension_window_seconds
    vault_types[vault_type_id, "bid_extension_seconds"] = bid_extension_seconds


@export
def set_vault_type_surplus_buffer_bps(vault_type_id: int, surplus_buffer_bps: int):
    require_governor()
    assert surplus_buffer_bps >= 0, "surplus_buffer_bps must be non-negative."
    assert surplus_buffer_bps <= BPS_DENOMINATOR, "surplus_buffer_bps must be <= 10000."
    vault_types[vault_type_id, "surplus_buffer_bps"] = surplus_buffer_bps


@export
def create_vault(vault_type_id: int, collateral_amount: Any, debt_amount: Any):
    assert_not_paused()
    require_vault_type(vault_type_id)
    assert isinstance(collateral_amount, (int, decimal)), "collateral_amount must be numeric."
    assert isinstance(debt_amount, (int, decimal)), "debt_amount must be numeric."
    assert collateral_amount > 0, "collateral_amount must be positive."
    assert debt_amount > 0, "debt_amount must be positive."
    assert debt_amount >= vault_type_value(vault_type_id, "min_debt", 0), "debt_amount is below min_debt."

    rate = accrue_vault_type(vault_type_id)
    height = new_debt_height(vault_type_id)
    assert current_total_debt(vault_type_id, rate) + debt_amount <= vault_type_value(vault_type_id, "debt_ceiling"), "debt ceiling exceeded."
    assert collateralization_bps_for(vault_type_id, collateral_amount, debt_amount) >= required_min_ratio(vault_type_id), "Not enough collateral."

    receive_collateral(vault_type_id, collateral_amount)

    vault_id = vault_count.get() + 1
    vault_count.set(vault_id)

    vaults[vault_id, "owner"] = ctx.caller
    vaults[vault_id, "vault_type_id"] = vault_type_id
    vaults[vault_id, "collateral_amount"] = collateral_amount
    vaults[vault_id, "debt_shares"] = 0
    vaults[vault_id, "debt_carry"] = 0
    vaults[vault_id, "principal"] = 0
    clear_vault_pending(vault_id)
    vaults[vault_id, "open"] = True
    vaults[vault_id, "created_at"] = current_time()
    clear_auction(vault_id)
    vaults[vault_id, "auction_settled"] = False
    vaults[vault_id, "auction_settled_at"] = None

    add_pending_debt(vault_id, debt_amount, debt_amount, height)

    stable_token().mint(amount=debt_amount, to=ctx.caller)

    VaultOpenedEvent(
        {
            "vault_id": vault_id,
            "owner": ctx.caller,
            "vault_type_id": vault_type_id,
            "collateral_amount": collateral_amount,
            "principal": debt_amount,
        }
    )
    return vault_id


@export
def deposit_collateral(vault_id: int, amount: Any):
    require_vault_owner(vault_id)
    require_not_in_auction(vault_id)
    assert isinstance(amount, (int, decimal)), "amount must be numeric."
    assert amount > 0, "amount must be positive."

    receive_collateral(vault_type_id_of(vault_id), amount)
    vaults[vault_id, "collateral_amount"] = vault_collateral(vault_id) + amount

    CollateralChangedEvent(
        {
            "vault_id": vault_id,
            "owner": ctx.caller,
            "delta": amount,
            "direction": "deposit",
            "collateral_amount": vault_collateral(vault_id),
        }
    )
    return vault_collateral(vault_id)


@export
def withdraw_collateral(vault_id: int, amount: Any):
    assert_not_paused()
    require_vault_owner(vault_id)
    require_not_in_auction(vault_id)
    assert isinstance(amount, (int, decimal)), "amount must be numeric."
    assert amount > 0, "amount must be positive."
    assert vault_collateral(vault_id) >= amount, "Not enough collateral."

    rate = accrue_vault_type(vault_type_id_of(vault_id))
    new_collateral = vault_collateral(vault_id) - amount
    debt = vault_live_debt(vault_id, rate)

    if debt > 0:
        assert collateralization_bps_for(vault_type_id_of(vault_id), new_collateral, debt) >= required_min_ratio(vault_type_id_of(vault_id)), "Withdrawal would undercollateralize the vault."

    vaults[vault_id, "collateral_amount"] = new_collateral
    collateral_contract(vault_type_id_of(vault_id)).transfer(amount=amount, to=ctx.caller)

    CollateralChangedEvent(
        {
            "vault_id": vault_id,
            "owner": ctx.caller,
            "delta": amount,
            "direction": "withdraw",
            "collateral_amount": new_collateral,
        }
    )
    return new_collateral


@export
def borrow(vault_id: int, amount: Any):
    assert_not_paused()
    require_vault_owner(vault_id)
    require_not_in_auction(vault_id)
    assert isinstance(amount, (int, decimal)), "amount must be numeric."
    assert amount > 0, "amount must be positive."

    vault_type_id = vault_type_id_of(vault_id)
    rate = accrue_vault_type(vault_type_id)
    materialize_vault(vault_id)
    height = new_debt_height(vault_type_id)
    assert current_total_debt(vault_type_id, rate) + amount <= vault_type_value(vault_type_id, "debt_ceiling"), "debt ceiling exceeded."

    new_principal = vault_live_principal(vault_id) + amount
    new_debt = vault_live_debt(vault_id, rate) + amount
    assert new_debt >= vault_type_value(vault_type_id, "min_debt", 0), "debt would be below min_debt."
    assert collateralization_bps_for(vault_type_id, vault_collateral(vault_id), new_debt) >= required_min_ratio(vault_type_id), "Borrow would undercollateralize the vault."

    add_pending_debt(vault_id, amount, amount, height)

    stable_token().mint(amount=amount, to=ctx.caller)

    DebtChangedEvent(
        {
            "vault_id": vault_id,
            "payer": ctx.caller,
            "direction": "borrow",
            "principal_delta": amount,
            "fee_delta": 0,
        }
    )
    return new_principal


@export
def repay(vault_id: int, amount: Any):
    require_open_vault(vault_id)
    require_not_in_auction(vault_id)
    assert isinstance(amount, (int, decimal)), "amount must be numeric."
    assert amount > 0, "amount must be positive."

    rate = accrue_vault_type(vault_type_id_of(vault_id))
    debt = vault_live_debt(vault_id, rate)
    assert amount <= debt, "amount exceeds total debt."

    stable_token().transfer_from(amount=amount, to=ctx.this, main_account=ctx.caller)
    repayment = apply_live_repayment(vault_id, amount, rate)

    remaining_debt = vault_live_debt(vault_id, rate)
    assert remaining_debt == 0 or remaining_debt >= vault_type_value(vault_type_id_of(vault_id), "min_debt", 0), "remaining debt would fall below min_debt."

    DebtChangedEvent(
        {
            "vault_id": vault_id,
            "payer": ctx.caller,
            "direction": "repay",
            "principal_delta": repayment["principal_paid"],
            "fee_delta": repayment["fee_paid"],
        }
    )
    return repayment


@export
def close_vault(vault_id: int):
    require_vault_owner(vault_id)
    require_not_in_auction(vault_id)

    rate = accrue_vault_type(vault_type_id_of(vault_id))
    debt = vault_live_debt(vault_id, rate)
    if debt > 0:
        stable_token().transfer_from(amount=debt, to=ctx.this, main_account=ctx.caller)
        apply_live_repayment(vault_id, debt, rate)

    collateral_amount = vault_collateral(vault_id)
    vaults[vault_id, "collateral_amount"] = 0
    close_vault_record(vault_id)
    collateral_contract(vault_type_id_of(vault_id)).transfer(amount=collateral_amount, to=ctx.caller)

    VaultClosedEvent(
        {
            "vault_id": vault_id,
            "owner": ctx.caller,
            "closer": ctx.caller,
        }
    )
    return collateral_amount


@export
def get_liquidation_quote(vault_id: int):
    require_open_vault(vault_id)
    require_not_in_auction(vault_id)
    quote = liquidation_quote_internal(vault_id)
    return {
        "debt": quote["debt"],
        "required_repayment": quote["required_repayment"],
        "collateral_out": quote["collateral_out"],
        "partial_possible": quote["partial_possible"],
    }


@export
def liquidate(vault_id: int, repay_amount: Any = None):
    assert_not_paused()
    require_open_vault(vault_id)
    require_not_in_auction(vault_id)

    vault_type_id = vault_type_id_of(vault_id)
    rate = accrue_vault_type(vault_type_id)
    materialize_vault(vault_id)
    debt = vault_live_debt(vault_id, rate)
    assert debt > 0, "Vault has no debt."
    assert collateralization_bps_for(vault_type_id, vault_collateral(vault_id), debt) < required_liquidation_ratio(vault_type_id), "Vault is above liquidation threshold."

    quote = liquidation_quote_internal(vault_id)
    assert quote["partial_possible"] is True, "Use auction."

    if repay_amount is None or repay_amount == 0:
        repay_amount = quote["required_repayment"]

    assert isinstance(repay_amount, (int, decimal)), "repay_amount must be numeric."
    assert repay_amount >= quote["required_repayment"], "repay_amount is too low."
    assert repay_amount <= debt, "repay_amount exceeds debt."

    collateral_paid = collateral_out_for_repayment(vault_type_id, repay_amount)
    assert collateral_paid <= vault_collateral(vault_id), "Use auction."

    stable_token().transfer_from(
        amount=repay_amount,
        to=ctx.this,
        main_account=ctx.caller,
    )
    repayment = apply_live_repayment(vault_id, repay_amount, rate)
    vaults[vault_id, "collateral_amount"] = vault_collateral(vault_id) - collateral_paid
    collateral_contract(vault_type_id).transfer(amount=collateral_paid, to=ctx.caller)

    remaining_debt = vault_live_debt(vault_id, rate)
    if remaining_debt == 0:
        remaining_collateral = vault_collateral(vault_id)
        vaults[vault_id, "collateral_amount"] = 0
        close_vault_record(vault_id)
        if remaining_collateral > 0:
            collateral_contract(vault_type_id).transfer(
                amount=remaining_collateral,
                to=vault_owner_of(vault_id),
            )
    else:
        assert remaining_debt >= vault_type_value(vault_type_id, "min_debt", 0), "remaining debt would fall below min_debt."
        assert collateralization_bps_for(vault_type_id, vault_collateral(vault_id), remaining_debt) >= required_min_ratio(vault_type_id), "liquidation did not restore safety."

    LiquidationEvent(
        {
            "vault_id": vault_id,
            "liquidator": ctx.caller,
            "debt_repaid": repayment["total_paid"],
            "collateral_paid": collateral_paid,
            "partial": True,
        }
    )
    return collateral_paid


@export
def liquidate_fast(vault_id: int):
    return liquidate(vault_id=vault_id)


@export
def open_liquidation_auction(vault_id: int):
    assert_not_paused()
    require_open_vault(vault_id)
    require_not_in_auction(vault_id)

    vault_type_id = vault_type_id_of(vault_id)
    rate = accrue_vault_type(vault_type_id)
    materialize_vault(vault_id)
    debt = vault_live_debt(vault_id, rate)
    assert debt > 0, "Vault has no debt."
    assert collateralization_bps_for(vault_type_id, vault_collateral(vault_id), debt) < required_liquidation_ratio(vault_type_id), "Vault is above liquidation threshold."

    principal = vault_live_principal(vault_id)
    shares = raw_vault_shares(vault_id)
    pending_debt = vault_pending_debt(vault_id)
    if pending_debt > 0:
        remove_pending_debt(vault_id, pending_debt, vault_pending_principal(vault_id))
    end_time = begin_auction_clock(vault_id)

    adjust_type_components(vault_type_id, -shares, -raw_vault_carry(vault_id))
    vault_types[vault_type_id, "principal_outstanding"] = (
        current_live_principal_outstanding(vault_type_id) - principal
    )
    vault_types[vault_type_id, "auction_debt_locked"] = (
        current_locked_debt(vault_type_id) + debt
    )
    vault_types[vault_type_id, "auction_principal_locked"] = (
        current_locked_principal(vault_type_id) + principal
    )

    vaults[vault_id, "debt_shares"] = 0
    vaults[vault_id, "debt_carry"] = 0
    vaults[vault_id, "principal"] = 0
    vaults[vault_id, "auction_open"] = True
    vaults[vault_id, "auction_highest_bidder"] = ""
    vaults[vault_id, "auction_highest_bid"] = 0
    vaults[vault_id, "auction_debt_snapshot"] = debt
    vaults[vault_id, "auction_principal_snapshot"] = principal

    AuctionOpenedEvent(
        {
            "vault_id": vault_id,
            "owner": vault_owner_of(vault_id),
            "debt": debt,
            "end_time": str(end_time),
        }
    )
    return end_time


@export
def restart_auction(vault_id: int):
    assert_not_paused()
    require_open_vault(vault_id)
    assert vaults[vault_id, "auction_open"] is True, "Auction is not open."
    previous_end = materialize_auction_clock(vault_id)
    assert previous_end is not None, "Auction checkpoint anchor is pending."
    assert current_time() >= previous_end, "Auction is still open."
    assert vaults[vault_id, "auction_highest_bid"] <= 0, "Auction already has bids."
    end_time = begin_auction_clock(vault_id)
    AuctionRestartedEvent({"vault_id": vault_id, "owner": vault_owner_of(vault_id),
        "debt": vault_snapshot_debt(vault_id), "end_time": "pending"})
    return end_time



def maybe_extend_auction(vault_id: int):
    nominal_end = vaults[vault_id, "auction_end_time"]
    if nominal_end is None:
        return
    vault_type_id = vault_type_id_of(vault_id)
    window = vault_type_value(vault_type_id, "extension_window_seconds", 0)
    extension = vault_type_value(vault_type_id, "bid_extension_seconds", 0)
    if window <= 0 or extension <= 0 or seconds_until(nominal_end) > window:
        return
    height = time_checkpoints.request_anchor()
    previous = vaults[vault_id, "auction_extension_height"]
    assert previous is None or previous == height, "Earlier auction extension checkpoint is pending."
    captured = vault_value(vault_id, "auction_extension_seconds", 0)
    # Preserve each qualifying additive extension, even when governance changes
    # its duration between same-height bids. The successor supplies a lower bound
    # for the whole newly promised interval, never an earlier deadline.
    vaults[vault_id, "auction_end_time"] = nominal_end + datetime.timedelta(seconds=extension)
    vaults[vault_id, "auction_extension_height"] = height
    vaults[vault_id, "auction_extension_seconds"] = captured + extension


@export
def bid(vault_id: int, bid_amount: Any):
    require_open_vault(vault_id)
    assert vaults[vault_id, "auction_open"] is True, "Auction is not open."
    end_time = materialize_auction_clock(vault_id)
    assert end_time is None or current_time() < end_time, "Auction already ended."
    assert isinstance(bid_amount, (int, decimal)), "bid_amount must be numeric."
    assert bid_amount > 0, "bid_amount must be positive."

    next_required = min_next_bid(vault_id)
    if next_required <= 0:
        assert bid_amount > 0, "Bid is too low."
    else:
        assert bid_amount >= next_required, "Bid is too low."

    existing_bid = auction_bids[vault_id, ctx.caller]
    transfer_delta = bid_amount - existing_bid
    assert transfer_delta > 0, "Bid must increase."

    stable_token().transfer_from(amount=transfer_delta, to=ctx.this, main_account=ctx.caller)
    auction_bids[vault_id, ctx.caller] = bid_amount
    vaults[vault_id, "auction_highest_bidder"] = ctx.caller
    vaults[vault_id, "auction_highest_bid"] = bid_amount

    maybe_extend_auction(vault_id)

    AuctionBidPlacedEvent(
        {
            "vault_id": vault_id,
            "bidder": ctx.caller,
            "bid_amount": bid_amount,
            "end_time": str(vaults[vault_id, "auction_end_time"]),
        }
    )
    return bid_amount


@export
def cure_auction(vault_id: int, repay_amount: Any = 0):
    require_vault_owner(vault_id)
    assert vaults[vault_id, "auction_open"] is True, "Auction is not open."
    assert vaults[vault_id, "auction_highest_bid"] <= 0, "Auction already has bids."

    if repay_amount is None:
        repay_amount = 0

    assert isinstance(repay_amount, (int, decimal)), "repay_amount must be numeric."
    assert repay_amount >= 0, "repay_amount must be non-negative."
    assert repay_amount <= vault_snapshot_debt(vault_id), "repay_amount exceeds total debt."

    if repay_amount > 0:
        stable_token().transfer_from(
            amount=repay_amount,
            to=ctx.this,
            main_account=ctx.caller,
        )
        apply_auction_repayment(vault_id, repay_amount)

    remaining_debt = vault_snapshot_debt(vault_id)
    if remaining_debt <= 0:
        remaining_collateral = vault_collateral(vault_id)
        vaults[vault_id, "collateral_amount"] = 0
        close_vault_record(vault_id)
        if remaining_collateral > 0:
            collateral_contract(vault_type_id_of(vault_id)).transfer(
                amount=remaining_collateral,
                to=ctx.caller,
            )
        AuctionCancelledEvent(
            {
                "vault_id": vault_id,
                "owner": ctx.caller,
                "reason": "fully_repaid",
            }
        )
        return 0

    assert remaining_debt >= vault_type_value(vault_type_id_of(vault_id), "min_debt", 0), "remaining debt would fall below min_debt."
    assert collateralization_bps_for(vault_type_id_of(vault_id), vault_collateral(vault_id), remaining_debt) >= required_min_ratio(vault_type_id_of(vault_id)), "auction cure did not restore safety."

    restore_auction_to_live(vault_id)
    AuctionCancelledEvent(
        {
            "vault_id": vault_id,
            "owner": ctx.caller,
            "reason": "cured",
        }
    )
    return vault_total_debt(vault_id)


@export
def cancel_auction_if_safe(vault_id: int):
    require_open_vault(vault_id)
    assert vaults[vault_id, "auction_open"] is True, "Auction is not open."
    assert vaults[vault_id, "auction_highest_bid"] <= 0, "Auction already has bids."
    assert collateralization_bps_for(vault_type_id_of(vault_id), vault_collateral(vault_id), vault_snapshot_debt(vault_id)) >= required_min_ratio(vault_type_id_of(vault_id)), "Vault is still unsafe."

    restore_auction_to_live(vault_id)
    AuctionCancelledEvent(
        {
            "vault_id": vault_id,
            "owner": vault_owner_of(vault_id),
            "reason": "price_recovery",
        }
    )
    return get_vault(vault_id)


@export
def settle_auction(vault_id: int):
    require_open_vault(vault_id)
    assert vaults[vault_id, "auction_open"] is True, "Auction is not open."
    end_time = materialize_auction_clock(vault_id)
    assert end_time is not None, "Auction checkpoint anchor is pending."
    assert current_time() >= end_time, "Auction is still open."

    winner = vaults[vault_id, "auction_highest_bidder"]
    winning_bid = vaults[vault_id, "auction_highest_bid"]
    assert winner is not None and winner != "", "Auction has no winning bid."

    vault_type_id = vault_type_id_of(vault_id)
    owner = vault_owner_of(vault_id)
    debt = vault_snapshot_debt(vault_id)
    principal = vault_snapshot_principal(vault_id)
    collateral_amount = vault_collateral(vault_id)
    parts = repayment_parts(debt, principal, winning_bid)
    fee_paid = parts["fee_paid"]
    principal_paid = parts["principal_paid"]

    excess = winning_bid - fee_paid - principal_paid
    bad_debt = debt - winning_bid
    if bad_debt < 0:
        bad_debt = 0

    vault_types[vault_type_id, "auction_debt_locked"] = (
        current_locked_debt(vault_type_id) - debt
    )
    vault_types[vault_type_id, "auction_principal_locked"] = (
        current_locked_principal(vault_type_id) - principal
    )

    if fee_paid > 0:
        route_fee_income(vault_type_id, fee_paid)
    if principal_paid > 0:
        burn_principal(principal_paid)
    if excess > 0:
        stable_token().transfer(amount=excess, to=owner)
    if bad_debt > 0:
        vault_types[vault_type_id, "bad_debt"] = (
            vault_type_value(vault_type_id, "bad_debt", 0) + bad_debt
        )

    auction_bids[vault_id, winner] = 0
    vaults[vault_id, "auction_settled"] = True
    vaults[vault_id, "auction_settled_at"] = current_time()
    vaults[vault_id, "collateral_amount"] = 0
    close_vault_record(vault_id)
    collateral_contract(vault_type_id).transfer(amount=collateral_amount, to=winner)

    AuctionSettledEvent(
        {
            "vault_id": vault_id,
            "winner": winner,
            "winning_bid": winning_bid,
            "bad_debt": bad_debt,
        }
    )

    return {
        "winner": winner,
        "winning_bid": winning_bid,
        "bad_debt": bad_debt,
    }


@export
def claim_refund(vault_id: int):
    assert vaults[vault_id, "auction_settled"] is True, "Auction is not settled."
    refund = auction_bids[vault_id, ctx.caller]
    assert refund > 0, "No refund available."

    auction_bids[vault_id, ctx.caller] = 0
    stable_token().transfer(amount=refund, to=ctx.caller)
    AuctionRefundClaimedEvent(
        {
            "vault_id": vault_id,
            "claimer": ctx.caller,
            "amount": refund,
        }
    )
    return refund


@export
def cover_bad_debt(vault_type_id: int, amount: Any = None):
    available = vault_type_value(vault_type_id, "surplus_buffer", 0)
    current_bad_debt = vault_type_value(vault_type_id, "bad_debt", 0)
    coverable = available
    if coverable > current_bad_debt:
        coverable = current_bad_debt

    if amount is None or amount == 0:
        amount = coverable

    assert isinstance(amount, (int, decimal)), "amount must be numeric."
    assert amount > 0, "amount must be positive."
    assert amount <= coverable, "amount exceeds coverable bad debt."

    vault_types[vault_type_id, "surplus_buffer"] = available - amount
    vault_types[vault_type_id, "bad_debt"] = current_bad_debt - amount
    burn_principal(amount)

    BadDebtCoveredEvent(
        {
            "vault_type_id": vault_type_id,
            "amount": amount,
        }
    )
    return amount


@export
def recapitalize(vault_type_id: int, amount: Any):
    require_vault_type_exists(vault_type_id)
    assert isinstance(amount, (int, decimal)), "amount must be numeric."
    assert amount > 0, "amount must be positive."

    stable_token().transfer_from(amount=amount, to=ctx.this, main_account=ctx.caller)

    current_bad_debt = vault_type_value(vault_type_id, "bad_debt", 0)
    bad_debt_reduced = amount
    if bad_debt_reduced > current_bad_debt:
        bad_debt_reduced = current_bad_debt

    surplus_added = amount - bad_debt_reduced
    if bad_debt_reduced > 0:
        vault_types[vault_type_id, "bad_debt"] = current_bad_debt - bad_debt_reduced
        burn_principal(bad_debt_reduced)

    if surplus_added > 0:
        vault_types[vault_type_id, "surplus_buffer"] = (
            vault_type_value(vault_type_id, "surplus_buffer", 0)
            + surplus_added
        )

    RecapitalizedEvent(
        {
            "vault_type_id": vault_type_id,
            "payer": ctx.caller,
            "amount": amount,
            "bad_debt_reduced": bad_debt_reduced,
            "surplus_added": surplus_added,
        }
    )

    return {
        "bad_debt_reduced": bad_debt_reduced,
        "surplus_added": surplus_added,
    }


@export
def sweep_surplus(vault_type_id: int, amount: Any = None):
    require_governor()
    assert vault_type_value(vault_type_id, "bad_debt", 0) <= 0, "Cannot sweep surplus while bad debt remains."
    available = vault_type_value(vault_type_id, "surplus_buffer", 0)

    if amount is None or amount == 0:
        amount = available

    assert isinstance(amount, (int, decimal)), "amount must be numeric."
    assert amount > 0, "amount must be positive."
    assert amount <= available, "amount exceeds surplus buffer."

    destination = fee_destination()
    vault_types[vault_type_id, "surplus_buffer"] = available - amount
    if destination != ctx.this:
        stable_token().transfer(amount=amount, to=destination)

    SurplusSweptEvent(
        {
            "vault_type_id": vault_type_id,
            "destination": destination,
            "amount": amount,
        }
    )
    return amount


@export
def get_vault(vault_id: int):
    require_vault_exists(vault_id)
    auction_open = vaults[vault_id, "auction_open"] is True
    debt = vault_total_debt(vault_id)
    return {
        "owner": vault_owner_of(vault_id),
        "vault_type_id": vault_type_id_of(vault_id),
        "collateral_amount": vault_collateral(vault_id),
        "debt_shares": vault_live_shares(vault_id),
        "debt_carry": raw_vault_carry(vault_id) + pending_vault_projection(vault_id)["carry"],
        "pending_debt": vault_pending_debt(vault_id),
        "pending_principal": vault_pending_principal(vault_id),
        "pending_debt_height": vaults[vault_id, "pending_debt_height"],
        "principal": vault_total_principal(vault_id),
        "fee_due": vault_fee_due(vault_id),
        "debt": debt,
        "collateralization_bps": collateralization_bps(vault_id, debt),
        "open": vaults[vault_id, "open"] is True,
        "auction_open": auction_open,
        "created_at": vaults[vault_id, "created_at"],
        "closed_at": vaults[vault_id, "closed_at"],
    }


@export
def get_auction(vault_id: int):
    require_vault_exists(vault_id)
    return {
        "auction_open": vaults[vault_id, "auction_open"] is True,
        "auction_opened_at": auction_clock(vault_id)["opened"],
        "auction_end_time": auction_clock(vault_id)["end"],
        "auction_anchor_height": vaults[vault_id, "auction_anchor_height"],
        "extension_anchor_height": vaults[vault_id, "auction_extension_height"],
        "highest_bidder": vaults[vault_id, "auction_highest_bidder"],
        "highest_bid": vaults[vault_id, "auction_highest_bid"],
        "min_next_bid": min_next_bid(vault_id),
        "debt_snapshot": vault_snapshot_debt(vault_id),
        "principal_snapshot": vault_snapshot_principal(vault_id),
    }


@export
def get_vault_type(vault_type_id: int):
    require_vault_type_exists(vault_type_id)
    rate = current_rate(vault_type_id)
    return {
        "active": vault_type_value(vault_type_id, "active"),
        "collateral_contract": vault_type_value(vault_type_id, "collateral_contract"),
        "oracle_key": vault_type_value(vault_type_id, "oracle_key"),
        "min_collateral_ratio_bps": vault_type_value(vault_type_id, "min_collateral_ratio_bps"),
        "liquidation_ratio_bps": vault_type_value(vault_type_id, "liquidation_ratio_bps"),
        "liquidation_bonus_bps": vault_type_value(vault_type_id, "liquidation_bonus_bps"),
        "partial_liquidation_target_ratio_bps": vault_type_value(vault_type_id, "partial_liquidation_target_ratio_bps"),
        "debt_ceiling": vault_type_value(vault_type_id, "debt_ceiling"),
        "min_debt": vault_type_value(vault_type_id, "min_debt"),
        "stability_fee_bps": effective_fee(vault_type_id),
        "auction_duration_seconds": vault_type_value(vault_type_id, "auction_duration_seconds"),
        "min_bid_increment_bps": vault_type_value(vault_type_id, "min_bid_increment_bps"),
        "extension_window_seconds": vault_type_value(vault_type_id, "extension_window_seconds"),
        "bid_extension_seconds": vault_type_value(vault_type_id, "bid_extension_seconds"),
        "surplus_buffer_bps": vault_type_value(vault_type_id, "surplus_buffer_bps"),
        "rate_accumulator": rate,
        "live_normalized_debt_total": current_live_shares_total(vault_type_id),
        "live_debt_carry_total": raw_live_carry_total(vault_type_id) + group_projection(vault_type_id)["carry"],
        "live_principal_outstanding": current_live_principal_outstanding(vault_type_id),
        "live_debt_outstanding": current_total_debt(vault_type_id, rate) - current_locked_debt(vault_type_id),
        "pending_debt_outstanding": pending_group_debt(vault_type_id),
        "pending_debt_height": vault_type_value(vault_type_id, "pending_debt_height"),
        "pending_stability_fee_bps": vault_type_value(vault_type_id, "pending_fee_bps"),
        "pending_fee_height": vault_type_value(vault_type_id, "pending_fee_height"),
        "auction_debt_locked": current_locked_debt(vault_type_id),
        "auction_principal_locked": current_locked_principal(vault_type_id),
        "fees_distributed": vault_type_value(vault_type_id, "fees_distributed", 0),
        "surplus_buffer": vault_type_value(vault_type_id, "surplus_buffer", 0),
        "bad_debt": vault_type_value(vault_type_id, "bad_debt", 0),
    }


@export
def get_collateralization_bps(vault_id: int):
    require_open_vault(vault_id)
    return collateralization_bps(vault_id)
