balances = Hash(default_value=0)
approvals = Hash(default_value=0)
metadata = Hash(default_value=None)

share_supply = Variable()
stable_token_contract = Variable()
governor = Variable()
proposed_governor = Variable()

DepositEvent = LogEvent(
    event="Deposit",
    params={
        "account": {"type": str, "idx": True},
        "assets": (int, float, decimal),
        "shares": (int, float, decimal),
    },
)

WithdrawEvent = LogEvent(
    event="Withdraw",
    params={
        "account": {"type": str, "idx": True},
        "assets": (int, float, decimal),
        "shares": (int, float, decimal),
    },
)

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
    token_name: str = "Stable Savings Share",
    token_symbol: str = "xSAVE",
    token_logo_url: str = "",
    token_website: str = "",
    governor_address: str = None,
):
    assert isinstance(stable_token_contract_name, str) and stable_token_contract_name != "", "stable_token_contract_name must be non-empty."
    assert isinstance(token_name, str) and token_name != "", "token_name must be non-empty."
    assert isinstance(token_symbol, str) and token_symbol != "", "token_symbol must be non-empty."
    assert isinstance(token_logo_url, str), "token_logo_url must be a string."
    assert isinstance(token_website, str), "token_website must be a string."

    resolved_governor = governor_address
    if resolved_governor is None or resolved_governor == "":
        resolved_governor = ctx.caller

    stable_token_contract.set(stable_token_contract_name)
    governor.set(resolved_governor)
    proposed_governor.set(None)
    share_supply.set(0)

    metadata["token_name"] = token_name
    metadata["token_symbol"] = token_symbol
    metadata["token_logo_url"] = token_logo_url
    metadata["token_website"] = token_website


def stable_token():
    return importlib.import_module(stable_token_contract.get())


def require_governor():
    assert ctx.caller == governor.get(), "Only governor can call."


def current_share_supply():
    supply = share_supply.get()
    if supply is None:
        return 0
    return supply


def current_total_assets():
    return stable_token().balance_of(account=ctx.this)


@export
def governor_of():
    return governor.get()


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
def total_supply():
    return current_share_supply()


@export
def total_assets():
    return current_total_assets()


@export
def balance_of(account: str):
    return balances[account]


@export
def allowance(owner: str, spender: str):
    return approvals[owner, spender]


@export
def share_price():
    supply = current_share_supply()
    if supply <= 0:
        return 1
    return current_total_assets() / supply


@export
def preview_deposit(assets: Any):
    assert isinstance(assets, (int, float, decimal)), "assets must be numeric."
    assert assets > 0, "assets must be positive."

    supply = current_share_supply()
    total_assets_before = current_total_assets()
    if supply <= 0 or total_assets_before <= 0:
        return assets
    return assets * supply / total_assets_before


@export
def preview_redeem(shares: Any):
    assert isinstance(shares, (int, float, decimal)), "shares must be numeric."
    assert shares > 0, "shares must be positive."

    supply = current_share_supply()
    assert supply > 0, "No shares exist."
    return shares * current_total_assets() / supply


@export
def deposit(assets: Any):
    assert isinstance(assets, (int, float, decimal)), "assets must be numeric."
    assert assets > 0, "assets must be positive."

    shares = preview_deposit(assets=assets)
    stable_token().transfer_from(amount=assets, to=ctx.this, main_account=ctx.caller)
    balances[ctx.caller] += shares
    share_supply.set(current_share_supply() + shares)

    DepositEvent({"account": ctx.caller, "assets": assets, "shares": shares})
    TransferEvent({"from": "mint", "to": ctx.caller, "amount": shares})
    return shares


@export
def withdraw(shares: Any):
    assert isinstance(shares, (int, float, decimal)), "shares must be numeric."
    assert shares > 0, "shares must be positive."
    assert balances[ctx.caller] >= shares, "Not enough shares."

    assets = preview_redeem(shares=shares)
    balances[ctx.caller] -= shares
    share_supply.set(current_share_supply() - shares)
    stable_token().transfer(amount=assets, to=ctx.caller)

    WithdrawEvent({"account": ctx.caller, "assets": assets, "shares": shares})
    TransferEvent({"from": ctx.caller, "to": "burn", "amount": shares})
    return assets


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
def approve(amount: Any, to: str):
    assert isinstance(amount, (int, float, decimal)), "amount must be numeric."
    assert amount >= 0, "Cannot approve negative balances."
    assert isinstance(to, str) and to != "", "to must be non-empty."

    approvals[ctx.caller, to] = amount
    ApproveEvent({"owner": ctx.caller, "spender": to, "amount": amount})
    return approvals[ctx.caller, to]


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
def change_metadata(key: str, value: Any):
    require_governor()
    assert isinstance(key, str) and key != "", "key must be non-empty."
    metadata[key] = value
