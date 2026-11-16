balances = Hash(default_value=0)
approvals = Hash(default_value=0)
controllers = Hash(default_value=False)
metadata = Hash(default_value=None)

governor = Variable()
proposed_governor = Variable()
total_supply = Variable()

TransferEvent = LogEvent(
    "Transfer",
    {
        "from": {"type": str, "idx": True},
        "to": {"type": str, "idx": True},
        "amount": (int, decimal),
    },
)

ApproveEvent = LogEvent(
    "Approve",
    {
        "owner": {"type": str, "idx": True},
        "spender": {"type": str, "idx": True},
        "amount": (int, decimal),
    },
)

ControllerUpdatedEvent = LogEvent(
    "ControllerUpdated",
    {
        "account": {"type": str, "idx": True},
        "enabled": bool,
    },
)

MintEvent = LogEvent(
    "Mint",
    {
        "to": {"type": str, "idx": True},
        "amount": (int, decimal),
    },
)

BurnEvent = LogEvent(
    "Burn",
    {
        "from": {"type": str, "idx": True},
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
    assert isinstance(initial_supply, (int, decimal)), "initial_supply must be numeric."
    assert initial_supply >= 0, "initial_supply must be non-negative."

    resolved_holder = initial_holder
    if resolved_holder is None or resolved_holder == "":
        resolved_holder = ctx.caller

    resolved_governor = governor_address
    if resolved_governor is None or resolved_governor == "":
        resolved_governor = ctx.caller

    require_account(resolved_holder)
    require_account(resolved_governor)

    governor.set(resolved_governor)
    proposed_governor.set(None)
    total_supply.set(initial_supply)

    balances[resolved_holder] = initial_supply
    metadata["token_name"] = token_name
    metadata["token_symbol"] = token_symbol
    metadata["token_logo_url"] = token_logo_url
    metadata["token_logo_svg"] = token_logo_svg
    metadata["token_website"] = token_website
    metadata["total_supply"] = initial_supply


def require_account(account: str):
    assert isinstance(account, str) and account != "", "Account must be non-empty."
    if len(account) != 64 or account == account.lower():
        return
    for character in account.lower():
        if character not in "0123456789abcdef":
            return
    assert False, "Account key must use canonical lowercase hex."


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
    require_account(new_governor)
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
    require_account(account)
    controllers[account] = enabled
    ControllerUpdatedEvent({"account": account, "enabled": enabled})


@export
def total_supply_of():
    return total_supply.get()


@export
def balance_of(address: str):
    return balances[address]


@export
def allowance(owner: str, spender: str):
    return approvals[owner, spender]


@export
def approve(amount: Any, to: str):
    assert isinstance(amount, (int, decimal)), "amount must be numeric."
    assert amount >= 0, "Cannot approve negative balances."
    require_account(to)

    approvals[ctx.caller, to] = amount
    ApproveEvent({"owner": ctx.caller, "spender": to, "amount": amount})
    return approvals[ctx.caller, to]


@export
def transfer(amount: Any, to: str):
    assert isinstance(amount, (int, decimal)), "amount must be numeric."
    assert amount > 0, "Cannot transfer non-positive balances."
    require_account(to)
    assert balances[ctx.caller] >= amount, "Not enough balance."

    balances[ctx.caller] -= amount
    balances[to] += amount
    TransferEvent({"from": ctx.caller, "to": to, "amount": amount})


@export
def transfer_from(amount: Any, to: str, main_account: str):
    assert isinstance(amount, (int, decimal)), "amount must be numeric."
    assert amount > 0, "Cannot transfer non-positive balances."
    require_account(to)
    require_account(main_account)
    assert approvals[main_account, ctx.caller] >= amount, "Not enough approved balance."
    assert balances[main_account] >= amount, "Not enough balance."

    approvals[main_account, ctx.caller] -= amount
    balances[main_account] -= amount
    balances[to] += amount
    TransferEvent({"from": main_account, "to": to, "amount": amount})


@export
def mint(amount: Any, to: str):
    require_controller()
    assert isinstance(amount, (int, decimal)), "amount must be numeric."
    assert amount > 0, "Cannot mint non-positive balances."
    require_account(to)

    balances[to] += amount
    total_supply.set(total_supply.get() + amount)
    metadata["total_supply"] = total_supply.get()
    MintEvent({"to": to, "amount": amount})
    TransferEvent({"from": "mint", "to": to, "amount": amount})


@export
def burn(amount: Any):
    assert isinstance(amount, (int, decimal)), "amount must be numeric."
    assert amount > 0, "Cannot burn non-positive balances."
    assert balances[ctx.caller] >= amount, "Not enough balance to burn."

    balances[ctx.caller] -= amount
    total_supply.set(total_supply.get() - amount)
    metadata["total_supply"] = total_supply.get()
    BurnEvent({"from": ctx.caller, "amount": amount})
    TransferEvent({"from": ctx.caller, "to": "burn", "amount": amount})


@export
def change_metadata(key: str, value: Any):
    require_governor()
    assert isinstance(key, str) and key != "", "key must be non-empty."
    assert key != "total_supply", "total_supply is managed by the contract."
    metadata[key] = value
