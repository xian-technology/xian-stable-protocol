balances = Hash(default_value=0)
approvals = Hash(default_value=0)
controllers = Hash(default_value=False)
metadata = Hash(default_value=None)

governor = Variable()
proposed_governor = Variable()
total_supply = Variable()

TransferEvent = LogEvent(
    event="Transfer",
    params={
        "from": {"type": str, "idx": True},
        "to": {"type": str, "idx": True},
        "amount": (int, float, decimal),
    },
)

ApproveEvent = LogEvent(
    event="Approve",
    params={
        "owner": {"type": str, "idx": True},
        "spender": {"type": str, "idx": True},
        "amount": (int, float, decimal),
    },
)

ControllerUpdatedEvent = LogEvent(
    event="ControllerUpdated",
    params={
        "account": {"type": str, "idx": True},
        "enabled": bool,
    },
)

MintEvent = LogEvent(
    event="Mint",
    params={
        "to": {"type": str, "idx": True},
        "amount": (int, float, decimal),
    },
)

BurnEvent = LogEvent(
    event="Burn",
    params={
        "from": {"type": str, "idx": True},
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
    token_name: str,
    token_symbol: str,
    token_logo_url: str = "",
    token_logo_svg: str = "",
    token_website: str = "",
    initial_supply: Any = 0,
    initial_holder: str = None,
    governor_address: str = None,
):
    assert isinstance(token_name, str) and token_name != "", "token_name must be non-empty."
    assert isinstance(token_symbol, str) and token_symbol != "", "token_symbol must be non-empty."
    assert isinstance(token_logo_url, str), "token_logo_url must be a string."
    assert isinstance(token_logo_svg, str), "token_logo_svg must be a string."
    assert isinstance(token_website, str), "token_website must be a string."
    assert isinstance(initial_supply, (int, float, decimal)), "initial_supply must be numeric."
    assert initial_supply >= 0, "initial_supply must be non-negative."

    resolved_holder = initial_holder
    if resolved_holder is None or resolved_holder == "":
        resolved_holder = ctx.caller

    resolved_governor = governor_address
    if resolved_governor is None or resolved_governor == "":
        resolved_governor = ctx.caller

    governor.set(resolved_governor)
    proposed_governor.set(None)
    total_supply.set(initial_supply)

    balances[resolved_holder] = initial_supply
    metadata["token_name"] = token_name
    metadata["token_symbol"] = token_symbol
    metadata["token_logo_url"] = token_logo_url
    metadata["token_logo_svg"] = token_logo_svg
    metadata["token_website"] = token_website


def require_governor():
    assert ctx.caller == governor.get(), "Only governor can call."


def require_controller():
    assert controllers[ctx.caller] is True, "Only controller can call."


@export
def governor_of():
    return governor.get()


@export
def is_controller(account: str):
    return controllers[account]


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
def set_controller(account: str, enabled: bool):
    require_governor()
    assert isinstance(account, str) and account != "", "account must be non-empty."
    controllers[account] = enabled
    ControllerUpdatedEvent({"account": account, "enabled": enabled})


@export
def total_supply_of():
    return total_supply.get()


@export
def balance_of(account: str):
    return balances[account]


@export
def allowance(owner: str, spender: str):
    return approvals[owner, spender]


@export
def approve(amount: Any, to: str):
    assert isinstance(amount, (int, float, decimal)), "amount must be numeric."
    assert amount >= 0, "Cannot approve negative balances."
    assert isinstance(to, str) and to != "", "to must be non-empty."

    approvals[ctx.caller, to] = amount
    ApproveEvent({"owner": ctx.caller, "spender": to, "amount": amount})
    return approvals[ctx.caller, to]


@export
def transfer(amount: Any, to: str):
    assert isinstance(amount, (int, float, decimal)), "amount must be numeric."
    assert amount > 0, "Cannot transfer non-positive balances."
    assert isinstance(to, str) and to != "", "to must be non-empty."
    assert balances[ctx.caller] >= amount, "Not enough balance."

    balances[ctx.caller] -= amount
    balances[to] += amount
    TransferEvent({"from": ctx.caller, "to": to, "amount": amount})


@export
def transfer_from(amount: Any, to: str, main_account: str):
    assert isinstance(amount, (int, float, decimal)), "amount must be numeric."
    assert amount > 0, "Cannot transfer non-positive balances."
    assert isinstance(to, str) and to != "", "to must be non-empty."
    assert isinstance(main_account, str) and main_account != "", "main_account must be non-empty."
    assert approvals[main_account, ctx.caller] >= amount, "Not enough approved balance."
    assert balances[main_account] >= amount, "Not enough balance."

    approvals[main_account, ctx.caller] -= amount
    balances[main_account] -= amount
    balances[to] += amount
    TransferEvent({"from": main_account, "to": to, "amount": amount})


@export
def mint(amount: Any, to: str):
    require_controller()
    assert isinstance(amount, (int, float, decimal)), "amount must be numeric."
    assert amount > 0, "Cannot mint non-positive balances."
    assert isinstance(to, str) and to != "", "to must be non-empty."

    balances[to] += amount
    total_supply.set(total_supply.get() + amount)
    MintEvent({"to": to, "amount": amount})
    TransferEvent({"from": "mint", "to": to, "amount": amount})


@export
def burn(amount: Any):
    assert isinstance(amount, (int, float, decimal)), "amount must be numeric."
    assert amount > 0, "Cannot burn non-positive balances."
    assert balances[ctx.caller] >= amount, "Not enough balance to burn."

    balances[ctx.caller] -= amount
    total_supply.set(total_supply.get() - amount)
    BurnEvent({"from": ctx.caller, "amount": amount})
    TransferEvent({"from": ctx.caller, "to": "burn", "amount": amount})


@export
def change_metadata(key: str, value: Any):
    require_governor()
    assert isinstance(key, str) and key != "", "key must be non-empty."
    metadata[key] = value
