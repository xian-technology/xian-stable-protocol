members = Variable()
member_weights = Hash(default_value=0)

governor = Variable()
proposed_governor = Variable()

MemberUpdatedEvent = LogEvent(
    event="MemberUpdated",
    params={
        "account": {"type": str, "idx": True},
        "enabled": bool,
        "weight": int,
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
    initial_members: list,
    initial_weights: dict = None,
    governor_address: str = None,
):
    assert isinstance(initial_members, list), "initial_members must be a list."

    resolved_governor = governor_address
    if resolved_governor is None or resolved_governor == "":
        resolved_governor = ctx.caller

    if initial_weights is None:
        initial_weights = {}

    normalized_members = []
    for account in initial_members:
        assert isinstance(account, str) and account != "", "member must be non-empty."
        if account in normalized_members:
            continue

        weight = initial_weights.get(account)
        if weight is None:
            weight = 1

        assert isinstance(weight, int), "member weight must be an int."
        assert weight > 0, "member weight must be positive."

        normalized_members.append(account)
        member_weights[account] = weight

    governor.set(resolved_governor)
    proposed_governor.set(None)
    members.set(normalized_members)


def require_governor():
    assert ctx.caller == governor.get(), "Only governor can call."


def current_members():
    accounts = members.get()
    if accounts is None:
        return []
    return accounts


def is_listed(account: str):
    accounts = current_members()
    return account in accounts


@export
def governor_of():
    return governor.get()


@export
def get_members():
    return current_members()


@export
def is_member(account: str):
    return is_listed(account)


@export
def member_weight(account: str):
    if not is_listed(account):
        return 0
    return member_weights[account]


@export
def total_member_weight():
    total = 0
    for account in current_members():
        total += member_weights[account]
    return total


@export
def member_count():
    return len(current_members())


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
def set_member(account: str, enabled: bool, weight: int = 1):
    require_governor()
    assert isinstance(account, str) and account != "", "account must be non-empty."
    assert isinstance(weight, int), "weight must be an int."

    accounts = current_members()
    listed = account in accounts

    if enabled:
        assert weight > 0, "weight must be positive."
        if not listed:
            accounts.append(account)
            members.set(accounts)
        member_weights[account] = weight
        MemberUpdatedEvent(
            {
                "account": account,
                "enabled": True,
                "weight": weight,
            }
        )
        return

    if listed:
        accounts.remove(account)
        members.set(accounts)
    member_weights[account] = 0
    MemberUpdatedEvent(
        {
            "account": account,
            "enabled": False,
            "weight": 0,
        }
    )


@export
def set_member_weight(account: str, weight: int):
    require_governor()
    assert is_listed(account), "account is not a member."
    assert isinstance(weight, int), "weight must be an int."
    assert weight > 0, "weight must be positive."
    member_weights[account] = weight
    MemberUpdatedEvent(
        {
            "account": account,
            "enabled": True,
            "weight": weight,
        }
    )
