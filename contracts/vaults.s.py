BPS_DENOMINATOR = 10000
SECONDS_PER_YEAR = 31536000

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
    event="VaultTypeAdded",
    params={
        "vault_type_id": {"type": int, "idx": True},
        "collateral_contract": {"type": str, "idx": True},
        "oracle_key": {"type": str, "idx": True},
    },
)

VaultOpenedEvent = LogEvent(
    event="VaultOpened",
    params={
        "vault_id": {"type": int, "idx": True},
        "owner": {"type": str, "idx": True},
        "vault_type_id": {"type": int, "idx": True},
        "collateral_amount": (int, float, decimal),
        "principal": (int, float, decimal),
    },
)

CollateralChangedEvent = LogEvent(
    event="CollateralChanged",
    params={
        "vault_id": {"type": int, "idx": True},
        "owner": {"type": str, "idx": True},
        "delta": (int, float, decimal),
        "direction": {"type": str, "idx": True},
        "collateral_amount": (int, float, decimal),
    },
)

DebtChangedEvent = LogEvent(
    event="DebtChanged",
    params={
        "vault_id": {"type": int, "idx": True},
        "payer": {"type": str, "idx": True},
        "direction": {"type": str, "idx": True},
        "principal_delta": (int, float, decimal),
        "fee_delta": (int, float, decimal),
    },
)

VaultClosedEvent = LogEvent(
    event="VaultClosed",
    params={
        "vault_id": {"type": int, "idx": True},
        "owner": {"type": str, "idx": True},
        "closer": {"type": str, "idx": True},
    },
)

FastLiquidationEvent = LogEvent(
    event="FastLiquidation",
    params={
        "vault_id": {"type": int, "idx": True},
        "liquidator": {"type": str, "idx": True},
        "debt_repaid": (int, float, decimal),
        "collateral_paid": (int, float, decimal),
    },
)

AuctionOpenedEvent = LogEvent(
    event="AuctionOpened",
    params={
        "vault_id": {"type": int, "idx": True},
        "owner": {"type": str, "idx": True},
        "debt": (int, float, decimal),
        "end_time": str,
    },
)

AuctionBidPlacedEvent = LogEvent(
    event="AuctionBidPlaced",
    params={
        "vault_id": {"type": int, "idx": True},
        "bidder": {"type": str, "idx": True},
        "bid_amount": (int, float, decimal),
    },
)

AuctionSettledEvent = LogEvent(
    event="AuctionSettled",
    params={
        "vault_id": {"type": int, "idx": True},
        "winner": {"type": str, "idx": True},
        "winning_bid": (int, float, decimal),
        "bad_debt": (int, float, decimal),
    },
)

AuctionRefundClaimedEvent = LogEvent(
    event="AuctionRefundClaimed",
    params={
        "vault_id": {"type": int, "idx": True},
        "claimer": {"type": str, "idx": True},
        "amount": (int, float, decimal),
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


def require_open_vault(vault_id: int):
    assert vaults[vault_id, "owner"] is not None, "Vault does not exist."
    assert vaults[vault_id, "open"] is True, "Vault is not open."


def require_vault_owner(vault_id: int):
    require_open_vault(vault_id)
    assert vaults[vault_id, "owner"] == ctx.caller, "Only vault owner can call."


def require_not_in_auction(vault_id: int):
    assert vaults[vault_id, "auction_open"] is not True, "Vault is in auction."


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


def vault_principal(vault_id: int):
    principal = vaults[vault_id, "principal"]
    if principal is None:
        return 0
    return principal


def vault_fees(vault_id: int):
    fees = vaults[vault_id, "accrued_fees"]
    if fees is None:
        return 0
    return fees


def vault_collateral(vault_id: int):
    collateral_amount = vaults[vault_id, "collateral_amount"]
    if collateral_amount is None:
        return 0
    return collateral_amount


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


def collateral_value(vault_id: int):
    return vault_collateral(vault_id) * current_oracle_price(vaults[vault_id, "vault_type_id"])


def preview_fee(vault_id: int):
    if vaults[vault_id, "open"] is not True:
        return 0
    if vaults[vault_id, "auction_open"] is True:
        return 0

    principal = vault_principal(vault_id)
    if principal <= 0:
        return 0

    stability_fee_bps = vault_type_value(vaults[vault_id, "vault_type_id"], "stability_fee_bps", 0)
    if stability_fee_bps <= 0:
        return 0

    elapsed = elapsed_seconds(vaults[vault_id, "last_fee_time"])
    if elapsed <= 0:
        return 0

    return principal * stability_fee_bps * elapsed / SECONDS_PER_YEAR / BPS_DENOMINATOR


def preview_debt(vault_id: int):
    if vaults[vault_id, "auction_open"] is True:
        debt = vaults[vault_id, "auction_debt"]
        if debt is None:
            return 0
        return debt
    return vault_principal(vault_id) + vault_fees(vault_id) + preview_fee(vault_id)


def accrue_fees(vault_id: int):
    fee = preview_fee(vault_id)
    if fee > 0:
        vaults[vault_id, "accrued_fees"] = vault_fees(vault_id) + fee
    if vaults[vault_id, "open"] is True and vaults[vault_id, "auction_open"] is not True:
        vaults[vault_id, "last_fee_time"] = current_time()
    return fee


def collateralization_bps(vault_id: int, debt_amount: Any = None):
    if debt_amount is None:
        debt_amount = preview_debt(vault_id)
    if debt_amount <= 0:
        return 10 ** 18
    return collateral_value(vault_id) * BPS_DENOMINATOR / debt_amount


def required_min_ratio(vault_id: int):
    return vault_type_value(vaults[vault_id, "vault_type_id"], "min_collateral_ratio_bps")


def required_liquidation_ratio(vault_id: int):
    return vault_type_value(vaults[vault_id, "vault_type_id"], "liquidation_ratio_bps")


def route_fee_income(vault_type_id: int, amount: Any):
    if amount <= 0:
        return

    destination = savings_contract.get()
    if destination is None or destination == "":
        destination = treasury_address.get()
    if destination is None or destination == "":
        destination = governor.get()

    if destination != ctx.this:
        stable_token().transfer(amount=amount, to=destination)

    current_distributed = vault_type_value(vault_type_id, "fees_distributed", 0)
    vault_types[vault_type_id, "fees_distributed"] = current_distributed + amount


def burn_principal(vault_type_id: int, amount: Any):
    if amount <= 0:
        return
    stable_token().burn(amount=amount)
    outstanding = vault_type_value(vault_type_id, "principal_outstanding", 0)
    vault_types[vault_type_id, "principal_outstanding"] = outstanding - amount


def apply_repayment(vault_id: int, amount: Any):
    fees_due = vault_fees(vault_id)
    principal_due = vault_principal(vault_id)
    fee_paid = 0
    principal_paid = 0

    if amount > 0 and fees_due > 0:
        fee_paid = amount
        if fee_paid > fees_due:
            fee_paid = fees_due

    amount_remaining = amount - fee_paid
    if amount_remaining > 0 and principal_due > 0:
        principal_paid = amount_remaining
        if principal_paid > principal_due:
            principal_paid = principal_due

    if fee_paid > 0:
        vaults[vault_id, "accrued_fees"] = fees_due - fee_paid
        route_fee_income(vaults[vault_id, "vault_type_id"], fee_paid)

    if principal_paid > 0:
        vaults[vault_id, "principal"] = principal_due - principal_paid
        burn_principal(vaults[vault_id, "vault_type_id"], principal_paid)

    return {
        "fee_paid": fee_paid,
        "principal_paid": principal_paid,
        "total_paid": fee_paid + principal_paid,
    }


def close_vault_record(vault_id: int):
    vaults[vault_id, "open"] = False
    vaults[vault_id, "auction_open"] = False
    vaults[vault_id, "closed_at"] = current_time()
    vaults[vault_id, "principal"] = 0
    vaults[vault_id, "accrued_fees"] = 0
    vaults[vault_id, "last_fee_time"] = current_time()


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

    vault_type_id = vault_type_count.get() + 1
    vault_type_count.set(vault_type_id)
    vault_type_ids.set(current_vault_type_ids() + [vault_type_id])

    vault_types[vault_type_id, "active"] = True
    vault_types[vault_type_id, "collateral_contract"] = collateral_contract_name
    vault_types[vault_type_id, "oracle_key"] = oracle_key
    vault_types[vault_type_id, "min_collateral_ratio_bps"] = min_collateral_ratio_bps
    vault_types[vault_type_id, "liquidation_ratio_bps"] = liquidation_ratio_bps
    vault_types[vault_type_id, "liquidation_bonus_bps"] = liquidation_bonus_bps
    vault_types[vault_type_id, "debt_ceiling"] = debt_ceiling
    vault_types[vault_type_id, "min_debt"] = min_debt
    vault_types[vault_type_id, "stability_fee_bps"] = stability_fee_bps
    vault_types[vault_type_id, "auction_duration_seconds"] = auction_duration_seconds
    vault_types[vault_type_id, "principal_outstanding"] = 0
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
    assert vault_type_value(vault_type_id, "collateral_contract") is not None, "Vault type does not exist."
    assert stability_fee_bps >= 0, "stability_fee_bps must be non-negative."
    vault_types[vault_type_id, "stability_fee_bps"] = stability_fee_bps


@export
def set_vault_type_limits(vault_type_id: int, debt_ceiling: Any, min_debt: Any):
    require_governor()
    assert vault_type_value(vault_type_id, "collateral_contract") is not None, "Vault type does not exist."
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
):
    require_governor()
    assert vault_type_value(vault_type_id, "collateral_contract") is not None, "Vault type does not exist."
    assert min_collateral_ratio_bps > 0, "min_collateral_ratio_bps must be positive."
    assert liquidation_ratio_bps > 0, "liquidation_ratio_bps must be positive."
    assert liquidation_ratio_bps <= min_collateral_ratio_bps, "liquidation ratio must be <= minimum ratio."
    assert liquidation_bonus_bps >= 0, "liquidation_bonus_bps must be non-negative."
    vault_types[vault_type_id, "min_collateral_ratio_bps"] = min_collateral_ratio_bps
    vault_types[vault_type_id, "liquidation_ratio_bps"] = liquidation_ratio_bps
    vault_types[vault_type_id, "liquidation_bonus_bps"] = liquidation_bonus_bps


@export
def set_vault_type_auction_duration(vault_type_id: int, auction_duration_seconds: int):
    require_governor()
    assert vault_type_value(vault_type_id, "collateral_contract") is not None, "Vault type does not exist."
    assert auction_duration_seconds > 0, "auction_duration_seconds must be positive."
    vault_types[vault_type_id, "auction_duration_seconds"] = auction_duration_seconds


@export
def create_vault(vault_type_id: int, collateral_amount: Any, debt_amount: Any):
    assert_not_paused()
    require_vault_type(vault_type_id)
    assert isinstance(collateral_amount, (int, float, decimal)), "collateral_amount must be numeric."
    assert isinstance(debt_amount, (int, float, decimal)), "debt_amount must be numeric."
    assert collateral_amount > 0, "collateral_amount must be positive."
    assert debt_amount > 0, "debt_amount must be positive."
    assert debt_amount >= vault_type_value(vault_type_id, "min_debt", 0), "debt_amount is below min_debt."

    outstanding = vault_type_value(vault_type_id, "principal_outstanding", 0)
    assert outstanding + debt_amount <= vault_type_value(vault_type_id, "debt_ceiling"), "debt ceiling exceeded."

    collateral_value_after = collateral_amount * current_oracle_price(vault_type_id)
    ratio_bps = collateral_value_after * BPS_DENOMINATOR / debt_amount
    assert ratio_bps >= vault_type_value(vault_type_id, "min_collateral_ratio_bps"), "Not enough collateral."

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
    vaults[vault_id, "principal"] = debt_amount
    vaults[vault_id, "accrued_fees"] = 0
    vaults[vault_id, "last_fee_time"] = current_time()
    vaults[vault_id, "open"] = True
    vaults[vault_id, "auction_open"] = False
    vaults[vault_id, "created_at"] = current_time()

    vault_types[vault_type_id, "principal_outstanding"] = outstanding + debt_amount
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

    collateral_contract(vaults[vault_id, "vault_type_id"]).transfer_from(
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

    accrue_fees(vault_id)

    new_collateral_amount = vault_collateral(vault_id) - amount
    debt = vault_principal(vault_id) + vault_fees(vault_id)
    if debt > 0:
        new_collateral_value = new_collateral_amount * current_oracle_price(vaults[vault_id, "vault_type_id"])
        new_ratio = new_collateral_value * BPS_DENOMINATOR / debt
        assert new_ratio >= required_min_ratio(vault_id), "Withdrawal would undercollateralize the vault."

    vaults[vault_id, "collateral_amount"] = new_collateral_amount
    collateral_contract(vaults[vault_id, "vault_type_id"]).transfer(amount=amount, to=ctx.caller)

    CollateralChangedEvent(
        {
            "vault_id": vault_id,
            "owner": ctx.caller,
            "delta": amount,
            "direction": "withdraw",
            "collateral_amount": new_collateral_amount,
        }
    )
    return new_collateral_amount


@export
def borrow(vault_id: int, amount: Any):
    assert_not_paused()
    require_vault_owner(vault_id)
    require_not_in_auction(vault_id)
    assert isinstance(amount, (int, float, decimal)), "amount must be numeric."
    assert amount > 0, "amount must be positive."

    accrue_fees(vault_id)

    vault_type_id = vaults[vault_id, "vault_type_id"]
    outstanding = vault_type_value(vault_type_id, "principal_outstanding", 0)
    assert outstanding + amount <= vault_type_value(vault_type_id, "debt_ceiling"), "debt ceiling exceeded."

    new_principal = vault_principal(vault_id) + amount
    new_debt = new_principal + vault_fees(vault_id)
    assert new_debt >= vault_type_value(vault_type_id, "min_debt", 0), "debt would be below min_debt."
    assert collateralization_bps(vault_id, debt_amount=new_debt) >= required_min_ratio(vault_id), "Borrow would undercollateralize the vault."

    vaults[vault_id, "principal"] = new_principal
    vault_types[vault_type_id, "principal_outstanding"] = outstanding + amount
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

    accrue_fees(vault_id)
    total_due = vault_principal(vault_id) + vault_fees(vault_id)
    assert amount <= total_due, "amount exceeds total debt."

    stable_token().transfer_from(amount=amount, to=ctx.this, main_account=ctx.caller)
    repayment = apply_repayment(vault_id, amount)
    vaults[vault_id, "last_fee_time"] = current_time()

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

    accrue_fees(vault_id)
    total_due = vault_principal(vault_id) + vault_fees(vault_id)
    if total_due > 0:
        stable_token().transfer_from(amount=total_due, to=ctx.this, main_account=ctx.caller)
        apply_repayment(vault_id, total_due)

    collateral_amount = vault_collateral(vault_id)
    vaults[vault_id, "collateral_amount"] = 0
    close_vault_record(vault_id)
    collateral_contract(vaults[vault_id, "vault_type_id"]).transfer(amount=collateral_amount, to=ctx.caller)

    VaultClosedEvent(
        {
            "vault_id": vault_id,
            "owner": ctx.caller,
            "closer": ctx.caller,
        }
    )
    return collateral_amount


@export
def liquidate_fast(vault_id: int):
    assert_not_paused()
    require_open_vault(vault_id)
    require_not_in_auction(vault_id)

    accrue_fees(vault_id)
    debt = vault_principal(vault_id) + vault_fees(vault_id)
    assert debt > 0, "Vault has no debt."
    assert collateralization_bps(vault_id, debt_amount=debt) < required_liquidation_ratio(vault_id), "Vault is above liquidation threshold."

    vault_type_id = vaults[vault_id, "vault_type_id"]
    price = current_oracle_price(vault_type_id)
    collateral_amount = vault_collateral(vault_id)
    bonus_bps = vault_type_value(vault_type_id, "liquidation_bonus_bps", 0)
    payout_collateral = debt * (BPS_DENOMINATOR + bonus_bps) / BPS_DENOMINATOR / price
    assert payout_collateral <= collateral_amount, "Fast liquidation cannot pay full bonus; use auction."

    stable_token().transfer_from(amount=debt, to=ctx.this, main_account=ctx.caller)
    apply_repayment(vault_id, debt)

    owner = vaults[vault_id, "owner"]
    remainder = collateral_amount - payout_collateral
    vaults[vault_id, "collateral_amount"] = 0
    close_vault_record(vault_id)

    collateral_contract(vault_type_id).transfer(amount=payout_collateral, to=ctx.caller)
    if remainder > 0:
        collateral_contract(vault_type_id).transfer(amount=remainder, to=owner)

    FastLiquidationEvent(
        {
            "vault_id": vault_id,
            "liquidator": ctx.caller,
            "debt_repaid": debt,
            "collateral_paid": payout_collateral,
        }
    )
    return payout_collateral


@export
def open_liquidation_auction(vault_id: int):
    assert_not_paused()
    require_open_vault(vault_id)
    require_not_in_auction(vault_id)

    accrue_fees(vault_id)
    debt = vault_principal(vault_id) + vault_fees(vault_id)
    assert debt > 0, "Vault has no debt."
    assert collateralization_bps(vault_id, debt_amount=debt) < required_liquidation_ratio(vault_id), "Vault is above liquidation threshold."

    vault_type_id = vaults[vault_id, "vault_type_id"]
    duration = vault_type_value(vault_type_id, "auction_duration_seconds")
    end_time = current_time() + datetime.timedelta(seconds=duration)

    vaults[vault_id, "auction_open"] = True
    vaults[vault_id, "auction_opened_at"] = current_time()
    vaults[vault_id, "auction_end_time"] = end_time
    vaults[vault_id, "auction_highest_bidder"] = ""
    vaults[vault_id, "auction_highest_bid"] = 0
    vaults[vault_id, "auction_debt"] = debt
    vaults[vault_id, "auction_principal"] = vault_principal(vault_id)
    vaults[vault_id, "auction_fees"] = vault_fees(vault_id)
    vaults[vault_id, "last_fee_time"] = current_time()

    AuctionOpenedEvent(
        {
            "vault_id": vault_id,
            "owner": vaults[vault_id, "owner"],
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
    assert bid_amount > vaults[vault_id, "auction_highest_bid"], "Bid is too low."

    existing_bid = auction_bids[vault_id, ctx.caller]
    transfer_delta = bid_amount - existing_bid
    assert transfer_delta > 0, "Bid must increase."

    stable_token().transfer_from(amount=transfer_delta, to=ctx.this, main_account=ctx.caller)
    auction_bids[vault_id, ctx.caller] = bid_amount
    vaults[vault_id, "auction_highest_bidder"] = ctx.caller
    vaults[vault_id, "auction_highest_bid"] = bid_amount

    AuctionBidPlacedEvent(
        {
            "vault_id": vault_id,
            "bidder": ctx.caller,
            "bid_amount": bid_amount,
        }
    )
    return bid_amount


@export
def settle_auction(vault_id: int):
    require_open_vault(vault_id)
    assert vaults[vault_id, "auction_open"] is True, "Auction is not open."
    assert current_time() >= vaults[vault_id, "auction_end_time"], "Auction is still open."

    winner = vaults[vault_id, "auction_highest_bidder"]
    winning_bid = vaults[vault_id, "auction_highest_bid"]
    assert winner is not None and winner != "", "Auction has no winning bid."

    vault_type_id = vaults[vault_id, "vault_type_id"]
    owner = vaults[vault_id, "owner"]
    debt = vaults[vault_id, "auction_debt"]
    principal = vaults[vault_id, "auction_principal"]
    fees = vaults[vault_id, "auction_fees"]
    collateral_amount = vault_collateral(vault_id)

    fee_paid = winning_bid
    if fee_paid > fees:
        fee_paid = fees

    remaining = winning_bid - fee_paid
    principal_paid = remaining
    if principal_paid > principal:
        principal_paid = principal

    excess = remaining - principal_paid
    bad_debt = debt - winning_bid
    if bad_debt < 0:
        bad_debt = 0

    if fee_paid > 0:
        route_fee_income(vault_type_id, fee_paid)
    if principal_paid > 0:
        burn_principal(vault_type_id, principal_paid)
    if excess > 0:
        stable_token().transfer(amount=excess, to=owner)
    if bad_debt > 0:
        vault_types[vault_type_id, "bad_debt"] = vault_type_value(vault_type_id, "bad_debt", 0) + bad_debt

    auction_bids[vault_id, winner] = 0
    vaults[vault_id, "auction_open"] = False
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
def get_vault(vault_id: int):
    assert vaults[vault_id, "owner"] is not None, "Vault does not exist."
    return {
        "owner": vaults[vault_id, "owner"],
        "vault_type_id": vaults[vault_id, "vault_type_id"],
        "collateral_amount": vault_collateral(vault_id),
        "principal": vault_principal(vault_id),
        "accrued_fees": vault_fees(vault_id),
        "preview_debt": preview_debt(vault_id),
        "open": vaults[vault_id, "open"],
        "auction_open": vaults[vault_id, "auction_open"],
    }


@export
def get_vault_type(vault_type_id: int):
    assert vault_type_value(vault_type_id, "collateral_contract") is not None, "Vault type does not exist."
    return {
        "active": vault_type_value(vault_type_id, "active"),
        "collateral_contract": vault_type_value(vault_type_id, "collateral_contract"),
        "oracle_key": vault_type_value(vault_type_id, "oracle_key"),
        "min_collateral_ratio_bps": vault_type_value(vault_type_id, "min_collateral_ratio_bps"),
        "liquidation_ratio_bps": vault_type_value(vault_type_id, "liquidation_ratio_bps"),
        "liquidation_bonus_bps": vault_type_value(vault_type_id, "liquidation_bonus_bps"),
        "debt_ceiling": vault_type_value(vault_type_id, "debt_ceiling"),
        "min_debt": vault_type_value(vault_type_id, "min_debt"),
        "stability_fee_bps": vault_type_value(vault_type_id, "stability_fee_bps"),
        "auction_duration_seconds": vault_type_value(vault_type_id, "auction_duration_seconds"),
        "principal_outstanding": vault_type_value(vault_type_id, "principal_outstanding", 0),
        "fees_distributed": vault_type_value(vault_type_id, "fees_distributed", 0),
        "bad_debt": vault_type_value(vault_type_id, "bad_debt", 0),
    }


@export
def get_collateralization_bps(vault_id: int):
    require_open_vault(vault_id)
    return collateralization_bps(vault_id)
