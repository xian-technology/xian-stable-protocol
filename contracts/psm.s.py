BPS_DENOMINATOR = 10000

stable_token_contract = Variable()
reserve_token_contract = Variable()

governor = Variable()
proposed_governor = Variable()
treasury_address = Variable()
mint_fee_bps = Variable()
redeem_fee_bps = Variable()
paused = Variable()

MintedEvent = LogEvent(
    event="Minted",
    params={
        "account": {"type": str, "idx": True},
        "reserve_in": (int, float, decimal),
        "stable_out": (int, float, decimal),
        "fee": (int, float, decimal),
    },
)

RedeemedEvent = LogEvent(
    event="Redeemed",
    params={
        "account": {"type": str, "idx": True},
        "stable_in": (int, float, decimal),
        "reserve_out": (int, float, decimal),
        "fee": (int, float, decimal),
    },
)

FeesUpdatedEvent = LogEvent(
    event="FeesUpdated",
    params={
        "mint_fee_bps": int,
        "redeem_fee_bps": int,
    },
)

PausedUpdatedEvent = LogEvent(
    event="PausedUpdated",
    params={
        "paused": bool,
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
    reserve_token_contract_name: str,
    governor_address: str = None,
    treasury_address_value: str = "",
    mint_fee_bps_value: int = 0,
    redeem_fee_bps_value: int = 0,
):
    assert isinstance(stable_token_contract_name, str) and stable_token_contract_name != "", "stable_token_contract_name must be non-empty."
    assert isinstance(reserve_token_contract_name, str) and reserve_token_contract_name != "", "reserve_token_contract_name must be non-empty."
    assert isinstance(treasury_address_value, str), "treasury_address_value must be a string."

    validate_fee_bps(mint_fee_bps_value)
    validate_fee_bps(redeem_fee_bps_value)

    resolved_governor = governor_address
    if resolved_governor is None or resolved_governor == "":
        resolved_governor = ctx.caller

    stable_token_contract.set(stable_token_contract_name)
    reserve_token_contract.set(reserve_token_contract_name)
    governor.set(resolved_governor)
    proposed_governor.set(None)
    treasury_address.set(treasury_address_value)
    mint_fee_bps.set(mint_fee_bps_value)
    redeem_fee_bps.set(redeem_fee_bps_value)
    paused.set(False)


def stable_token():
    return importlib.import_module(stable_token_contract.get())


def reserve_token():
    return importlib.import_module(reserve_token_contract.get())


def require_governor():
    assert ctx.caller == governor.get(), "Only governor can call."


def assert_not_paused():
    assert paused.get() is not True, "PSM is paused."


def validate_fee_bps(value: int):
    assert isinstance(value, int), "fee must be an int."
    assert value >= 0, "fee cannot be negative."
    assert value < BPS_DENOMINATOR, "fee must be less than 10000 bps."


def fee_destination():
    destination = treasury_address.get()
    if destination is None or destination == "":
        destination = governor.get()
    return destination


def reserve_balance():
    return reserve_token().balance_of(account=ctx.this)


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
    PausedUpdatedEvent({"paused": value})


@export
def set_treasury_address(address: str):
    require_governor()
    assert isinstance(address, str), "address must be a string."
    treasury_address.set(address)


@export
def set_fees(mint_fee_bps_value: int, redeem_fee_bps_value: int):
    require_governor()
    validate_fee_bps(mint_fee_bps_value)
    validate_fee_bps(redeem_fee_bps_value)
    mint_fee_bps.set(mint_fee_bps_value)
    redeem_fee_bps.set(redeem_fee_bps_value)
    FeesUpdatedEvent(
        {
            "mint_fee_bps": mint_fee_bps_value,
            "redeem_fee_bps": redeem_fee_bps_value,
        }
    )


@export
def quote_mint(reserve_amount: Any):
    assert isinstance(reserve_amount, (int, float, decimal)), "reserve_amount must be numeric."
    assert reserve_amount > 0, "reserve_amount must be positive."
    fee = reserve_amount * mint_fee_bps.get() / BPS_DENOMINATOR
    stable_out = reserve_amount - fee
    assert stable_out > 0, "minted amount must be positive."
    return {
        "reserve_in": reserve_amount,
        "stable_out": stable_out,
        "fee": fee,
    }


@export
def quote_redeem(stable_amount: Any):
    assert isinstance(stable_amount, (int, float, decimal)), "stable_amount must be numeric."
    assert stable_amount > 0, "stable_amount must be positive."
    fee = stable_amount * redeem_fee_bps.get() / BPS_DENOMINATOR
    reserve_out = stable_amount - fee
    assert reserve_out > 0, "redeemed amount must be positive."
    return {
        "stable_in": stable_amount,
        "reserve_out": reserve_out,
        "fee": fee,
    }


@export
def mint_stable(reserve_amount: Any):
    assert_not_paused()
    quote = quote_mint(reserve_amount=reserve_amount)

    reserve_token().transfer_from(
        amount=quote["reserve_in"],
        to=ctx.this,
        main_account=ctx.caller,
    )

    destination = fee_destination()
    if quote["fee"] > 0 and destination != ctx.this:
        reserve_token().transfer(amount=quote["fee"], to=destination)

    stable_token().mint(amount=quote["stable_out"], to=ctx.caller)

    MintedEvent(
        {
            "account": ctx.caller,
            "reserve_in": quote["reserve_in"],
            "stable_out": quote["stable_out"],
            "fee": quote["fee"],
        }
    )
    return quote


@export
def redeem_stable(stable_amount: Any):
    assert_not_paused()
    quote = quote_redeem(stable_amount=stable_amount)
    total_required_reserves = quote["reserve_out"] + quote["fee"]
    assert reserve_balance() >= total_required_reserves, "Not enough reserves."

    stable_token().transfer_from(
        amount=quote["stable_in"],
        to=ctx.this,
        main_account=ctx.caller,
    )
    stable_token().burn(amount=quote["stable_in"])

    reserve_token().transfer(amount=quote["reserve_out"], to=ctx.caller)

    destination = fee_destination()
    if quote["fee"] > 0 and destination != ctx.this:
        reserve_token().transfer(amount=quote["fee"], to=destination)

    RedeemedEvent(
        {
            "account": ctx.caller,
            "stable_in": quote["stable_in"],
            "reserve_out": quote["reserve_out"],
            "fee": quote["fee"],
        }
    )
    return quote


@export
def get_state():
    return {
        "stable_token_contract": stable_token_contract.get(),
        "reserve_token_contract": reserve_token_contract.get(),
        "treasury_address": treasury_address.get(),
        "mint_fee_bps": mint_fee_bps.get(),
        "redeem_fee_bps": redeem_fee_bps.get(),
        "paused": paused.get() is True,
        "reserve_balance": reserve_balance(),
    }
