membership_contract = Variable()
proposal_count = Variable()

metadata = Hash(default_value=None)
proposals = Hash(default_value=None)
proposal_votes = Hash(default_value=None)
proposal_vote_counts = Hash(default_value=0)
proposal_vote_weights = Hash(default_value=0)

STATUS_PENDING = "pending"
STATUS_QUEUED = "queued"
STATUS_EXECUTED = "executed"
STATUS_REJECTED = "rejected"
STATUS_EXPIRED = "expired"
STATUS_CANCELLED = "cancelled"

ProposalSubmittedEvent = LogEvent(
    event="ProposalSubmitted",
    params={
        "proposal_id": {"type": int, "idx": True},
        "proposer": {"type": str, "idx": True},
        "target_contract": {"type": str, "idx": True},
        "target_function": str,
        "summary": str,
    },
)

ProposalVotedEvent = LogEvent(
    event="ProposalVoted",
    params={
        "proposal_id": {"type": int, "idx": True},
        "voter": {"type": str, "idx": True},
        "vote": {"type": str, "idx": True},
        "yes_votes": int,
        "no_votes": int,
    },
)

ProposalQueuedEvent = LogEvent(
    event="ProposalQueued",
    params={
        "proposal_id": {"type": int, "idx": True},
        "queued_by": {"type": str, "idx": True},
        "eta": str,
        "emergency": bool,
    },
)

ProposalExecutedEvent = LogEvent(
    event="ProposalExecuted",
    params={
        "proposal_id": {"type": int, "idx": True},
        "target_contract": {"type": str, "idx": True},
        "target_function": str,
        "executor": {"type": str, "idx": True},
    },
)

ProposalCancelledEvent = LogEvent(
    event="ProposalCancelled",
    params={
        "proposal_id": {"type": int, "idx": True},
        "canceller": {"type": str, "idx": True},
    },
)


@construct
def seed(
    membership_contract_name: str,
    approval_threshold_numerator: int = 2,
    approval_threshold_denominator: int = 3,
    proposal_expiry_days: int = 7,
    execution_delay_seconds: int = 86400,
    emergency_execution_delay_seconds: int = 3600,
):
    validate_ratio(approval_threshold_numerator, approval_threshold_denominator)
    assert isinstance(membership_contract_name, str) and membership_contract_name != "", "membership_contract_name must be non-empty."
    assert proposal_expiry_days > 0, "proposal_expiry_days must be positive."
    assert execution_delay_seconds >= 0, "execution_delay_seconds must be non-negative."
    assert emergency_execution_delay_seconds >= 0, "emergency_execution_delay_seconds must be non-negative."

    membership_contract.set(membership_contract_name)
    proposal_count.set(0)

    metadata["approval_threshold_numerator"] = approval_threshold_numerator
    metadata["approval_threshold_denominator"] = approval_threshold_denominator
    metadata["proposal_expiry_days"] = proposal_expiry_days
    metadata["execution_delay_seconds"] = execution_delay_seconds
    metadata["emergency_execution_delay_seconds"] = emergency_execution_delay_seconds


def validate_ratio(numerator: int, denominator: int):
    assert numerator > 0, "threshold numerator must be positive."
    assert denominator > 0, "threshold denominator must be positive."
    assert numerator <= denominator, "threshold ratio cannot exceed 1."


def membership():
    return importlib.import_module(membership_contract.get())


def uses_weighted_membership():
    membership_name = membership_contract.get()
    return importlib.has_export(
        membership_name, "member_weight"
    ) and importlib.has_export(membership_name, "total_member_weight")


def get_members_internal():
    return membership().get_members()


def get_member_weight(account: str):
    if uses_weighted_membership():
        weight = membership().member_weight(account=account)
        if weight is None:
            return 0
        return weight
    if membership().is_member(account=account):
        return 1
    return 0


def get_total_member_weight():
    if uses_weighted_membership():
        total_weight = membership().total_member_weight()
        if total_weight is None:
            return len(get_members_internal())
        return total_weight
    return len(get_members_internal())


def require_member():
    assert membership().is_member(account=ctx.caller), "Only members can govern."


def ceil_div(value: int, divisor: int):
    return (value + divisor - 1) // divisor


def required_yes_weight():
    total_weight = get_total_member_weight()
    assert total_weight > 0, "Governance requires at least one member."
    numerator = metadata["approval_threshold_numerator"]
    denominator = metadata["approval_threshold_denominator"]
    return ceil_div(total_weight * numerator, denominator)


def snapshot_weights(proposal_id: int):
    total_weight = 0
    for member in get_members_internal():
        weight = get_member_weight(member)
        proposal_vote_weights[proposal_id, member] = weight
        total_weight += weight
    return total_weight


def next_proposal_id():
    proposal_id = proposal_count.get() + 1
    proposal_count.set(proposal_id)
    return proposal_id


def current_status(proposal_id: int):
    return proposals[proposal_id, "status"]


def proposal_exists(proposal_id: int):
    return proposals[proposal_id, "target_contract"] is not None


def require_open_proposal(proposal_id: int):
    assert proposal_exists(proposal_id), "Proposal does not exist."
    assert current_status(proposal_id) == STATUS_PENDING, "Proposal is not open."
    assert now < proposals[proposal_id, "expires_at"], "Proposal expired."


def required_delay_seconds(emergency: bool):
    if emergency:
        return metadata["emergency_execution_delay_seconds"]
    return metadata["execution_delay_seconds"]


def initialize_proposal(
    proposal_id: int,
    target_contract: str,
    target_function: str,
    kwargs: dict,
    summary: str,
    emergency: bool,
):
    total_weight = snapshot_weights(proposal_id)
    proposals[proposal_id, "proposer"] = ctx.caller
    proposals[proposal_id, "summary"] = summary
    proposals[proposal_id, "target_contract"] = target_contract
    proposals[proposal_id, "target_function"] = target_function
    proposals[proposal_id, "kwargs"] = kwargs
    proposals[proposal_id, "emergency"] = emergency
    proposals[proposal_id, "status"] = STATUS_PENDING
    proposals[proposal_id, "created_at"] = now
    proposals[proposal_id, "expires_at"] = now + datetime.timedelta(
        days=metadata["proposal_expiry_days"]
    )
    proposals[proposal_id, "required_yes_weight"] = required_yes_weight()
    proposals[proposal_id, "total_weight_snapshot"] = total_weight
    proposal_vote_counts[proposal_id, "yes"] = 0
    proposal_vote_counts[proposal_id, "no"] = 0
    proposal_vote_counts[proposal_id, "yes_weight"] = 0
    proposal_vote_counts[proposal_id, "no_weight"] = 0

    ProposalSubmittedEvent(
        {
            "proposal_id": proposal_id,
            "proposer": ctx.caller,
            "target_contract": target_contract,
            "target_function": target_function,
            "summary": summary,
        }
    )


def queue_proposal(proposal_id: int):
    emergency = proposals[proposal_id, "emergency"] == True
    eta = now + datetime.timedelta(seconds=required_delay_seconds(emergency))
    proposals[proposal_id, "status"] = STATUS_QUEUED
    proposals[proposal_id, "queued_at"] = now
    proposals[proposal_id, "eta"] = eta

    ProposalQueuedEvent(
        {
            "proposal_id": proposal_id,
            "queued_by": ctx.caller,
            "eta": str(eta),
            "emergency": emergency,
        }
    )


def maybe_finalize(proposal_id: int):
    yes_weight = proposal_vote_counts[proposal_id, "yes_weight"]
    no_weight = proposal_vote_counts[proposal_id, "no_weight"]
    total_weight = proposals[proposal_id, "total_weight_snapshot"]
    required_weight = proposals[proposal_id, "required_yes_weight"]

    if yes_weight >= required_weight:
        queue_proposal(proposal_id)
        return

    remaining_weight = total_weight - yes_weight - no_weight
    if yes_weight + remaining_weight < required_weight:
        proposals[proposal_id, "status"] = STATUS_REJECTED


def record_vote(proposal_id: int, support: bool):
    require_open_proposal(proposal_id)
    assert proposal_votes[proposal_id, ctx.caller] is None, "Already voted."

    voter_weight = proposal_vote_weights[proposal_id, ctx.caller]
    assert voter_weight > 0, "Not eligible to vote on this proposal."

    vote_label = "yes"
    if not support:
        vote_label = "no"

    proposal_votes[proposal_id, ctx.caller] = vote_label
    proposal_vote_counts[proposal_id, vote_label] += 1
    proposal_vote_counts[proposal_id, vote_label + "_weight"] += voter_weight

    ProposalVotedEvent(
        {
            "proposal_id": proposal_id,
            "voter": ctx.caller,
            "vote": vote_label,
            "yes_votes": proposal_vote_counts[proposal_id, "yes"],
            "no_votes": proposal_vote_counts[proposal_id, "no"],
        }
    )

    maybe_finalize(proposal_id)


@export
def propose_contract_call(
    target_contract: str,
    target_function: str,
    kwargs: dict = None,
    summary: str = "",
    emergency: bool = False,
):
    require_member()
    assert isinstance(target_contract, str) and target_contract != "", "target_contract is required."
    assert isinstance(target_function, str) and target_function != "", "target_function is required."
    assert importlib.has_export(target_contract, target_function), "Target export does not exist."

    if kwargs is None:
        kwargs = {}
    if summary is None:
        summary = ""

    proposal_id = next_proposal_id()
    initialize_proposal(
        proposal_id,
        target_contract,
        target_function,
        kwargs,
        summary,
        emergency,
    )
    record_vote(proposal_id, True)
    return get_proposal(proposal_id)


@export
def vote(proposal_id: int, support: bool):
    record_vote(proposal_id, support)
    return get_proposal(proposal_id)


@export
def execute(proposal_id: int):
    assert proposal_exists(proposal_id), "Proposal does not exist."
    assert current_status(proposal_id) == STATUS_QUEUED, "Proposal is not queued."
    assert now >= proposals[proposal_id, "eta"], "Proposal is timelocked."

    target_contract = proposals[proposal_id, "target_contract"]
    target_function = proposals[proposal_id, "target_function"]
    kwargs = proposals[proposal_id, "kwargs"]
    if kwargs is None:
        kwargs = {}

    importlib.call(target_contract, target_function, kwargs)
    proposals[proposal_id, "status"] = STATUS_EXECUTED
    proposals[proposal_id, "executed_at"] = now

    ProposalExecutedEvent(
        {
            "proposal_id": proposal_id,
            "target_contract": target_contract,
            "target_function": target_function,
            "executor": ctx.caller,
        }
    )

    return get_proposal(proposal_id)


@export
def expire_proposal(proposal_id: int):
    assert proposal_exists(proposal_id), "Proposal does not exist."
    assert current_status(proposal_id) == STATUS_PENDING, "Proposal is not pending."
    assert now >= proposals[proposal_id, "expires_at"], "Proposal has not expired."
    proposals[proposal_id, "status"] = STATUS_EXPIRED
    proposals[proposal_id, "expired_at"] = now
    return get_proposal(proposal_id)


@export
def cancel_proposal(proposal_id: int):
    require_member()
    assert proposal_exists(proposal_id), "Proposal does not exist."
    status = current_status(proposal_id)
    assert status == STATUS_PENDING or status == STATUS_QUEUED, "Proposal cannot be cancelled."
    proposals[proposal_id, "status"] = STATUS_CANCELLED
    proposals[proposal_id, "cancelled_at"] = now

    ProposalCancelledEvent(
        {
            "proposal_id": proposal_id,
            "canceller": ctx.caller,
        }
    )

    return get_proposal(proposal_id)


@export
def get_proposal(proposal_id: int):
    assert proposal_exists(proposal_id), "Proposal does not exist."
    return {
        "proposal_id": proposal_id,
        "proposer": proposals[proposal_id, "proposer"],
        "summary": proposals[proposal_id, "summary"],
        "target_contract": proposals[proposal_id, "target_contract"],
        "target_function": proposals[proposal_id, "target_function"],
        "kwargs": proposals[proposal_id, "kwargs"],
        "emergency": proposals[proposal_id, "emergency"] == True,
        "status": proposals[proposal_id, "status"],
        "created_at": proposals[proposal_id, "created_at"],
        "expires_at": proposals[proposal_id, "expires_at"],
        "queued_at": proposals[proposal_id, "queued_at"],
        "eta": proposals[proposal_id, "eta"],
        "executed_at": proposals[proposal_id, "executed_at"],
        "cancelled_at": proposals[proposal_id, "cancelled_at"],
        "required_yes_weight": proposals[proposal_id, "required_yes_weight"],
        "total_weight_snapshot": proposals[proposal_id, "total_weight_snapshot"],
        "yes_votes": proposal_vote_counts[proposal_id, "yes"],
        "no_votes": proposal_vote_counts[proposal_id, "no"],
        "yes_weight": proposal_vote_counts[proposal_id, "yes_weight"],
        "no_weight": proposal_vote_counts[proposal_id, "no_weight"],
    }
