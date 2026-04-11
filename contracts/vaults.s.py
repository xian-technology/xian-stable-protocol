BPS_DENOMINATOR = 10000
SECONDS_PER_YEAR = 31536000
DUST = 0.000000001

vault_type_ids = Variable()
vault_type_count = Variable()
vault_count = Variable()

vault_types = Hash(default_value=None)
vaults = Hash(default_value=None)
auction_bids = Hash(default_value=0)

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
        "collateral_amount": (int, float, decimal),
        "principal": (int, float, decimal),
    },
)

CollateralChangedEvent = LogEvent(
    "CollateralChanged",
    {
        "vault_id": {"type": int, "idx": True},
        "owner": {"type": str, "idx": True},
        "delta": (int, float, decimal),
        "direction": {"type": str, "idx": True},
        "collateral_amount": (int, float, decimal),
    },
)

DebtChangedEvent = LogEvent(
    "DebtChanged",
    {
        "vault_id": {"type": int, "idx": True},
        "payer": {"type": str, "idx": True},
        "direction": {"type": str, "idx": True},
        "principal_delta": (int, float, decimal),
        "fee_delta": (int, float, decimal),
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
        "debt_repaid": (int, float, decimal),
        "collateral_paid": (int, float, decimal),
        "partial": bool,
    },
)

AuctionOpenedEvent = LogEvent(
    "AuctionOpened",
    {
        "vault_id": {"type": int, "idx": True},
        "owner": {"type": str, "idx": True},
        "debt": (int, float, decimal),
        "end_time": str,
    },
)

AuctionBidPlacedEvent = LogEvent(
    "AuctionBidPlaced",
    {
        "vault_id": {"type": int, "idx": True},
        "bidder": {"type": str, "idx": True},
        "bid_amount": (int, float, decimal),
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
        "winning_bid": (int, float, decimal),
        "bad_debt": (int, float, decimal),
    },
)

AuctionRefundClaimedEvent = LogEvent(
    "AuctionRefundClaimed",
    {
        "vault_id": {"type": int, "idx": True},
        "claimer": {"type": str, "idx": True},
        "amount": (int, float, decimal),
    },
)

BadDebtCoveredEvent = LogEvent(
    "BadDebtCovered",
    {
        "vault_type_id": {"type": int, "idx": True},
        "amount": (int, float, decimal),
    },
)

RecapitalizedEvent = LogEvent(
    "Recapitalized",
    {
        "vault_type_id": {"type": int, "idx": True},
        "payer": {"type": str, "idx": True},
        "amount": (int, float, decimal),
        "bad_debt_reduced": (int, float, decimal),
        "surplus_added": (int, float, decimal),
    },
)

SurplusSweptEvent = LogEvent(
    "SurplusSwept",
    {
        "vault_type_id": {"type": int, "idx": True},
        "destination": {"type": str, "idx": True},
        "amount": (int, float, decimal),
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


def elapsed_seconds(since_time):
    if since_time is None:
        return 0
    delta = current_time() - since_time
    elapsed = delta.seconds
    if elapsed < 0:
        return 0
    return elapsed


def seconds_until(target_time):
    if target_time is None:
        return 0
    delta = target_time - current_time()
    remaining = delta.seconds
    if remaining < 0:
        return 0
    return remaining


def is_zeroish(value):
    return value <= DUST


def vault_type_value(vault_type_id: int, field: str, fallback: Any = None):
    value = vault_types[vault_type_id, field]
    if value is None:
        return fallback
    return value


def require_vault_type(vault_type_id: int):
    assert vault_type_value(vault_type_id, "collateral_contract") is not None, "Vault type does not exist."
    assert vault_type_value(vault_type_id, "active", False) is True, "Vault type is inactive."


def collateral_contract(vault_type_id: int):
    return importlib.import_module(vault_type_value(vault_type_id, "collateral_contract"))


def current_oracle_price(vault_type_id: int):
    return oracle().get_price(asset=vault_type_value(vault_type_id, "oracle_key"))


def current_rate(vault_type_id: int):
    base_rate = vault_type_value(vault_type_id, "rate_accumulator", 1)
    fee_bps = vault_type_value(vault_type_id, "stability_fee_bps", 0)
    if fee_bps <= 0:
        return base_rate

    elapsed = elapsed_seconds(vault_type_value(vault_type_id, "last_rate_time"))
    if elapsed <= 0:
        return base_rate

    factor = 1 + (
        fee_bps * elapsed / SECONDS_PER_YEAR / BPS_DENOMINATOR
    )
    return base_rate * factor


def accrue_vault_type(vault_type_id: int):
    updated_rate = current_rate(vault_type_id)
    vault_types[vault_type_id, "rate_accumulator"] = updated_rate
    vault_types[vault_type_id, "last_rate_time"] = current_time()
    return updated_rate


def current_live_shares_total(vault_type_id: int):
    total = vault_type_value(vault_type_id, "normalized_debt_total", 0)
    if total is None:
        return 0
    return total


def current_live_principal_outstanding(vault_type_id: int):
    total = vault_type_value(vault_type_id, "principal_outstanding", 0)
    if total is None:
        return 0
    return total


def current_locked_debt(vault_type_id: int):
    total = vault_type_value(vault_type_id, "auction_debt_locked", 0)
    if total is None:
        return 0
    return total


def current_locked_principal(vault_type_id: int):
    total = vault_type_value(vault_type_id, "auction_principal_locked", 0)
    if total is None:
        return 0
    return total


def current_total_debt(vault_type_id: int, rate: Any = None):
    if rate is None:
        rate = current_rate(vault_type_id)
    return current_live_shares_total(vault_type_id) * rate + current_locked_debt(vault_type_id)


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
    amount = vaults[vault_id, "collateral_amount"]
    if amount is None:
        return 0
    return amount


def vault_live_shares(vault_id: int):
    shares = vaults[vault_id, "debt_shares"]
    if shares is None:
        return 0
    return shares


def vault_live_principal(vault_id: int):
    principal = vaults[vault_id, "principal"]
    if principal is None:
        return 0
    return principal


def vault_snapshot_debt(vault_id: int):
    debt = vaults[vault_id, "auction_debt_snapshot"]
    if debt is None:
        return 0
    return debt


def vault_snapshot_principal(vault_id: int):
    principal = vaults[vault_id, "auction_principal_snapshot"]
    if principal is None:
        return 0
    return principal


def vault_snapshot_shares(vault_id: int):
    shares = vaults[vault_id, "auction_shares_snapshot"]
    if shares is None:
        return 0
    return shares


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
    return vault_live_shares(vault_id) * rate


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

    destination = savings_contract.get()
    if destination is None or destination == "":
        destination = treasury_address.get()
    if destination is None or destination == "":
        destination = governor.get()

    if destination != ctx.this:
        stable_token().transfer(amount=distributed_amount, to=destination)

    vault_types[vault_type_id, "fees_distributed"] = (
        vault_type_value(vault_type_id, "fees_distributed", 0)
        + distributed_amount
    )


def burn_principal(amount: Any):
    if amount <= 0:
        return
    stable_token().burn(amount=amount)


def apply_live_repayment(vault_id: int, amount: Any, rate: Any = None):
    if rate is None:
        rate = current_rate(vault_type_id_of(vault_id))

    debt = vault_live_debt(vault_id, rate)
    if amount > debt:
        amount = debt

    principal_due = vault_live_principal(vault_id)
    fee_due = debt - principal_due
    if fee_due < 0:
        fee_due = 0

    fee_paid = amount
    if fee_paid > fee_due:
        fee_paid = fee_due

    principal_paid = amount - fee_paid
    if principal_paid > principal_due:
        principal_paid = principal_due

    shares_paid = 0
    if amount > 0:
        shares_paid = amount / rate

    new_shares = vault_live_shares(vault_id) - shares_paid
    if is_zeroish(new_shares):
        new_shares = 0

    new_principal = principal_due - principal_paid
    if is_zeroish(new_principal):
        new_principal = 0

    vaults[vault_id, "debt_shares"] = new_shares
    vaults[vault_id, "principal"] = new_principal

    vault_types[vault_type_id_of(vault_id), "normalized_debt_total"] = (
        current_live_shares_total(vault_type_id_of(vault_id)) - shares_paid
    )
    vault_types[vault_type_id_of(vault_id), "principal_outstanding"] = (
        current_live_principal_outstanding(vault_type_id_of(vault_id))
        - principal_paid
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


def apply_auction_repayment(vault_id: int, amount: Any):
    debt = vault_snapshot_debt(vault_id)
    if amount > debt:
        amount = debt

    principal_due = vault_snapshot_principal(vault_id)
    fee_due = debt - principal_due
    if fee_due < 0:
        fee_due = 0

    fee_paid = amount
    if fee_paid > fee_due:
        fee_paid = fee_due

    principal_paid = amount - fee_paid
    if principal_paid > principal_due:
        principal_paid = principal_due

    new_debt = debt - amount
    if is_zeroish(new_debt):
        new_debt = 0

    new_principal = principal_due - principal_paid
    if is_zeroish(new_principal):
        new_principal = 0

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


def clear_auction(vault_id: int):
    vaults[vault_id, "auction_open"] = False
    vaults[vault_id, "auction_opened_at"] = None
    vaults[vault_id, "auction_end_time"] = None
    vaults[vault_id, "auction_highest_bidder"] = ""
    vaults[vault_id, "auction_highest_bid"] = 0
    vaults[vault_id, "auction_debt_snapshot"] = 0
    vaults[vault_id, "auction_principal_snapshot"] = 0
    vaults[vault_id, "auction_shares_snapshot"] = 0


def close_vault_record(vault_id: int):
    vaults[vault_id, "open"] = False
    vaults[vault_id, "debt_shares"] = 0
    vaults[vault_id, "principal"] = 0
    vaults[vault_id, "closed_at"] = current_time()
    clear_auction(vault_id)


def restore_auction_to_live(vault_id: int):
    vault_type_id = vault_type_id_of(vault_id)
    rate = accrue_vault_type(vault_type_id)
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

    restored_shares = remaining_debt / rate
    vaults[vault_id, "debt_shares"] = restored_shares
    vaults[vault_id, "principal"] = remaining_principal
    vault_types[vault_type_id, "normalized_debt_total"] = (
        current_live_shares_total(vault_type_id) + restored_shares
    )
    vault_types[vault_type_id, "principal_outstanding"] = (
        current_live_principal_outstanding(vault_type_id) + remaining_principal
    )
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


def min_next_bid(vault_id: int):
    highest_bid = vaults[vault_id, "auction_highest_bid"]
    if highest_bid is None or highest_bid <= 0:
        return 0
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
    assert isinstance(debt_ceiling, (int, float, decimal)), "debt_ceiling must be numeric."
    assert debt_ceiling > 0, "debt_ceiling must be positive."
    assert isinstance(min_debt, (int, float, decimal)), "min_debt must be numeric."
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
    assert vault_type_value(vault_type_id, "collateral_contract") is not None, "Vault type does not exist."
    vault_types[vault_type_id, "active"] = active


@export
def set_vault_type_fee(vault_type_id: int, stability_fee_bps: int):
    require_governor()
    assert stability_fee_bps >= 0, "stability_fee_bps must be non-negative."
    vault_types[vault_type_id, "stability_fee_bps"] = stability_fee_bps


@export
def set_vault_type_limits(vault_type_id: int, debt_ceiling: Any, min_debt: Any):
    require_governor()
    assert isinstance(debt_ceiling, (int, float, decimal)), "debt_ceiling must be numeric."
    assert debt_ceiling > 0, "debt_ceiling must be positive."
    assert isinstance(min_debt, (int, float, decimal)), "min_debt must be numeric."
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
    assert isinstance(collateral_amount, (int, float, decimal)), "collateral_amount must be numeric."
    assert isinstance(debt_amount, (int, float, decimal)), "debt_amount must be numeric."
    assert collateral_amount > 0, "collateral_amount must be positive."
    assert debt_amount > 0, "debt_amount must be positive."
    assert debt_amount >= vault_type_value(vault_type_id, "min_debt", 0), "debt_amount is below min_debt."

    rate = accrue_vault_type(vault_type_id)
    assert current_total_debt(vault_type_id, rate) + debt_amount <= vault_type_value(vault_type_id, "debt_ceiling"), "debt ceiling exceeded."
    assert collateralization_bps_for(vault_type_id, collateral_amount, debt_amount) >= required_min_ratio(vault_type_id), "Not enough collateral."

    collateral_contract(vault_type_id).transfer_from(
        amount=collateral_amount,
        to=ctx.this,
        main_account=ctx.caller,
    )

    vault_id = vault_count.get() + 1
    vault_count.set(vault_id)

    vaults[vault_id, "owner"] = ctx.caller
    vaults[vault_id, "vault_type_id"] = vault_type_id
    vaults[vault_id, "collateral_amount"] = collateral_amount
    vaults[vault_id, "debt_shares"] = debt_amount / rate
    vaults[vault_id, "principal"] = debt_amount
    vaults[vault_id, "open"] = True
    vaults[vault_id, "created_at"] = current_time()
    clear_auction(vault_id)
    vaults[vault_id, "auction_settled"] = False
    vaults[vault_id, "auction_settled_at"] = None

    vault_types[vault_type_id, "normalized_debt_total"] = (
        current_live_shares_total(vault_type_id) + vaults[vault_id, "debt_shares"]
    )
    vault_types[vault_type_id, "principal_outstanding"] = (
        current_live_principal_outstanding(vault_type_id) + debt_amount
    )

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
    assert isinstance(amount, (int, float, decimal)), "amount must be numeric."
    assert amount > 0, "amount must be positive."

    collateral_contract(vault_type_id_of(vault_id)).transfer_from(
        amount=amount,
        to=ctx.this,
        main_account=ctx.caller,
    )
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
    assert isinstance(amount, (int, float, decimal)), "amount must be numeric."
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
    assert isinstance(amount, (int, float, decimal)), "amount must be numeric."
    assert amount > 0, "amount must be positive."

    vault_type_id = vault_type_id_of(vault_id)
    rate = accrue_vault_type(vault_type_id)
    assert current_total_debt(vault_type_id, rate) + amount <= vault_type_value(vault_type_id, "debt_ceiling"), "debt ceiling exceeded."

    new_principal = vault_live_principal(vault_id) + amount
    new_debt = vault_live_debt(vault_id, rate) + amount
    assert new_debt >= vault_type_value(vault_type_id, "min_debt", 0), "debt would be below min_debt."
    assert collateralization_bps_for(vault_type_id, vault_collateral(vault_id), new_debt) >= required_min_ratio(vault_type_id), "Borrow would undercollateralize the vault."

    shares_added = amount / rate
    vaults[vault_id, "debt_shares"] = vault_live_shares(vault_id) + shares_added
    vaults[vault_id, "principal"] = new_principal
    vault_types[vault_type_id, "normalized_debt_total"] = (
        current_live_shares_total(vault_type_id) + shares_added
    )
    vault_types[vault_type_id, "principal_outstanding"] = (
        current_live_principal_outstanding(vault_type_id) + amount
    )

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
    assert isinstance(amount, (int, float, decimal)), "amount must be numeric."
    assert amount > 0, "amount must be positive."

    rate = accrue_vault_type(vault_type_id_of(vault_id))
    debt = vault_live_debt(vault_id, rate)
    assert amount <= debt, "amount exceeds total debt."

    stable_token().transfer_from(amount=amount, to=ctx.this, main_account=ctx.caller)
    repayment = apply_live_repayment(vault_id, amount, rate)

    remaining_debt = vault_live_debt(vault_id, rate)
    assert is_zeroish(remaining_debt) or remaining_debt >= vault_type_value(vault_type_id_of(vault_id), "min_debt", 0), "remaining debt would fall below min_debt."

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
    debt = vault_live_debt(vault_id, rate)
    assert debt > 0, "Vault has no debt."
    assert collateralization_bps_for(vault_type_id, vault_collateral(vault_id), debt) < required_liquidation_ratio(vault_type_id), "Vault is above liquidation threshold."

    quote = liquidation_quote_internal(vault_id)
    assert quote["partial_possible"] is True, "Use auction."

    if repay_amount is None or repay_amount == 0:
        repay_amount = quote["required_repayment"]

    assert isinstance(repay_amount, (int, float, decimal)), "repay_amount must be numeric."
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
    if is_zeroish(remaining_debt):
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
    debt = vault_live_debt(vault_id, rate)
    assert debt > 0, "Vault has no debt."
    assert collateralization_bps_for(vault_type_id, vault_collateral(vault_id), debt) < required_liquidation_ratio(vault_type_id), "Vault is above liquidation threshold."

    principal = vault_live_principal(vault_id)
    shares = vault_live_shares(vault_id)
    duration = vault_type_value(vault_type_id, "auction_duration_seconds")
    end_time = current_time() + datetime.timedelta(seconds=duration)

    vault_types[vault_type_id, "normalized_debt_total"] = (
        current_live_shares_total(vault_type_id) - shares
    )
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
    vaults[vault_id, "principal"] = 0
    vaults[vault_id, "auction_open"] = True
    vaults[vault_id, "auction_opened_at"] = current_time()
    vaults[vault_id, "auction_end_time"] = end_time
    vaults[vault_id, "auction_highest_bidder"] = ""
    vaults[vault_id, "auction_highest_bid"] = 0
    vaults[vault_id, "auction_debt_snapshot"] = debt
    vaults[vault_id, "auction_principal_snapshot"] = principal
    vaults[vault_id, "auction_shares_snapshot"] = shares

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
def bid(vault_id: int, bid_amount: Any):
    require_open_vault(vault_id)
    assert vaults[vault_id, "auction_open"] is True, "Auction is not open."
    assert current_time() < vaults[vault_id, "auction_end_time"], "Auction already ended."
    assert isinstance(bid_amount, (int, float, decimal)), "bid_amount must be numeric."
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

    extension_window_seconds = vault_type_value(
        vault_type_id_of(vault_id), "extension_window_seconds", 0
    )
    bid_extension_seconds = vault_type_value(
        vault_type_id_of(vault_id), "bid_extension_seconds", 0
    )
    if (
        extension_window_seconds > 0
        and bid_extension_seconds > 0
        and seconds_until(vaults[vault_id, "auction_end_time"])
        <= extension_window_seconds
    ):
        vaults[vault_id, "auction_end_time"] = (
            vaults[vault_id, "auction_end_time"]
            + datetime.timedelta(seconds=bid_extension_seconds)
        )

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

    assert isinstance(repay_amount, (int, float, decimal)), "repay_amount must be numeric."
    assert repay_amount >= 0, "repay_amount must be non-negative."

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
    assert current_time() >= vaults[vault_id, "auction_end_time"], "Auction is still open."

    winner = vaults[vault_id, "auction_highest_bidder"]
    winning_bid = vaults[vault_id, "auction_highest_bid"]
    assert winner is not None and winner != "", "Auction has no winning bid."

    vault_type_id = vault_type_id_of(vault_id)
    owner = vault_owner_of(vault_id)
    debt = vault_snapshot_debt(vault_id)
    principal = vault_snapshot_principal(vault_id)
    collateral_amount = vault_collateral(vault_id)
    fee_due = debt - principal
    if fee_due < 0:
        fee_due = 0

    fee_paid = winning_bid
    if fee_paid > fee_due:
        fee_paid = fee_due

    principal_paid = winning_bid - fee_paid
    if principal_paid > principal:
        principal_paid = principal

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

    assert isinstance(amount, (int, float, decimal)), "amount must be numeric."
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
    assert isinstance(amount, (int, float, decimal)), "amount must be numeric."
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

    assert isinstance(amount, (int, float, decimal)), "amount must be numeric."
    assert amount > 0, "amount must be positive."
    assert amount <= available, "amount exceeds surplus buffer."

    destination = savings_contract.get()
    if destination is None or destination == "":
        destination = treasury_address.get()
    if destination is None or destination == "":
        destination = governor.get()

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
        "auction_opened_at": vaults[vault_id, "auction_opened_at"],
        "auction_end_time": vaults[vault_id, "auction_end_time"],
        "highest_bidder": vaults[vault_id, "auction_highest_bidder"],
        "highest_bid": vaults[vault_id, "auction_highest_bid"],
        "min_next_bid": min_next_bid(vault_id),
        "debt_snapshot": vault_snapshot_debt(vault_id),
        "principal_snapshot": vault_snapshot_principal(vault_id),
    }


@export
def get_vault_type(vault_type_id: int):
    assert vault_type_value(vault_type_id, "collateral_contract") is not None, "Vault type does not exist."
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
        "stability_fee_bps": vault_type_value(vault_type_id, "stability_fee_bps"),
        "auction_duration_seconds": vault_type_value(vault_type_id, "auction_duration_seconds"),
        "min_bid_increment_bps": vault_type_value(vault_type_id, "min_bid_increment_bps"),
        "extension_window_seconds": vault_type_value(vault_type_id, "extension_window_seconds"),
        "bid_extension_seconds": vault_type_value(vault_type_id, "bid_extension_seconds"),
        "surplus_buffer_bps": vault_type_value(vault_type_id, "surplus_buffer_bps"),
        "rate_accumulator": rate,
        "live_normalized_debt_total": current_live_shares_total(vault_type_id),
        "live_principal_outstanding": current_live_principal_outstanding(vault_type_id),
        "live_debt_outstanding": current_live_shares_total(vault_type_id) * rate,
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
