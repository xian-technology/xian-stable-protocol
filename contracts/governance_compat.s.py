membership_contract = Variable()
proposal_count = Variable()

metadata = Hash()
proposals = Hash(default_value=None)
proposal_votes = Hash(default_value=None)
proposal_vote_counts = Hash(default_value=0)
proposal_vote_weights = Hash(default_value=0)
patches = Hash(default_value=None)
scheduled_patches = Hash(default_value=False)

STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_EXECUTED = "executed"
STATUS_REJECTED = "rejected"
STATUS_EXPIRED = "expired"
STATUS_PROPOSED = "proposed"
STATUS_APPLIED = "applied"

KIND_STATE_PATCH = "state_patch"
KIND_CONTRACT_CALL = "contract_call"

ProposalSubmittedEvent = LogEvent(
    event="ProposalSubmitted",
    params={
        "proposal_id": {"type": int, "idx": True},
        "kind": {"type": str, "idx": True},
        "proposer": {"type": str, "idx": True},
        "summary": {"type": str},
    },
)

ProposalVotedEvent = LogEvent(
    event="ProposalVoted",
    params={
        "proposal_id": {"type": int, "idx": True},
        "voter": {"type": str, "idx": True},
        "vote": {"type": str, "idx": True},
        "yes_votes": {"type": int},
        "no_votes": {"type": int},
    },
)

ProposalApprovedEvent = LogEvent(
    event="ProposalApproved",
    params={
        "proposal_id": {"type": int, "idx": True},
        "kind": {"type": str, "idx": True},
        "approver": {"type": str, "idx": True},
    },
)

ProposalExecutedEvent = LogEvent(
    event="ProposalExecuted",
    params={
        "proposal_id": {"type": int, "idx": True},
        "target_contract": {"type": str, "idx": True},
        "target_function": {"type": str, "idx": True},
        "executor": {"type": str},
    },
)

StatePatchScheduledEvent = LogEvent(
    event="StatePatchScheduled",
    params={
        "proposal_id": {"type": int, "idx": True},
        "patch_id": {"type": str, "idx": True},
        "activation_height": {"type": int, "idx": True},
        "bundle_hash": {"type": str},
        "emergency": {"type": str},
    },
)


@construct
def seed(
    membership_contract_name: str,
    approval_threshold_numerator: int = 4,
    approval_threshold_denominator: int = 5,
    proposal_expiry_days: int = 7,
    min_patch_delay_blocks: int = 20,
    emergency_threshold_numerator: int = 1,
    emergency_threshold_denominator: int = 1,
    emergency_patch_delay_blocks: int = 5,
):
    validate_ratio(approval_threshold_numerator, approval_threshold_denominator)
    validate_ratio(
        emergency_threshold_numerator,
        emergency_threshold_denominator,
    )
    assert proposal_expiry_days > 0, "proposal_expiry_days must be positive."
    assert min_patch_delay_blocks > 0, "min_patch_delay_blocks must be positive."
    assert (
        emergency_patch_delay_blocks > 0
    ), "emergency_patch_delay_blocks must be positive."

    membership_contract.set(membership_contract_name)
    proposal_count.set(0)

    metadata["approval_threshold_numerator"] = approval_threshold_numerator
    metadata["approval_threshold_denominator"] = approval_threshold_denominator
    metadata["proposal_expiry_days"] = proposal_expiry_days
    metadata["min_patch_delay_blocks"] = min_patch_delay_blocks
    metadata["emergency_threshold_numerator"] = emergency_threshold_numerator
    metadata["emergency_threshold_denominator"] = emergency_threshold_denominator
    metadata["emergency_patch_delay_blocks"] = emergency_patch_delay_blocks


def validate_ratio(numerator: int, denominator: int):
    assert numerator > 0, "Threshold numerator must be positive."
    assert denominator > 0, "Threshold denominator must be positive."
    assert numerator <= denominator, "Threshold ratio cannot exceed 1."


def membership():
    return importlib.import_module(membership_contract.get())


def get_members_internal():
    return membership().get_members()


def uses_weighted_membership():
    membership_name = membership_contract.get()
    return importlib.has_export(
        membership_name, "member_weight"
    ) and importlib.has_export(membership_name, "total_member_weight")


def get_member_weight(account: str):
    if uses_weighted_membership():
        weight = membership().member_weight(account=account)
        if weight is None:
            return 0
        return weight
    return 1


def get_total_member_weight():
    if uses_weighted_membership():
        total_weight = membership().total_member_weight()
        if total_weight is None:
            return len(get_members_internal())
        if total_weight <= 0:
            return len(get_members_internal())
        return total_weight
    return len(get_members_internal())


def require_member():
    assert membership().is_member(account=ctx.caller), "Only members can govern."


def next_proposal_id():
    proposal_id = proposal_count.get() + 1
    proposal_count.set(proposal_id)
    return proposal_id


def ceil_div(value: int, divisor: int):
    return (value + divisor - 1) // divisor


def required_yes_votes(emergency: bool):
    member_total = len(get_members_internal())
    assert member_total > 0, "Governance requires at least one member."

    numerator = metadata["approval_threshold_numerator"]
    denominator = metadata["approval_threshold_denominator"]
    if emergency:
        numerator = metadata["emergency_threshold_numerator"]
        denominator = metadata["emergency_threshold_denominator"]

    return ceil_div(member_total * numerator, denominator)


def required_yes_votes_for_member_total(member_total: int, emergency: bool):
    assert member_total > 0, "Governance requires at least one member."

    numerator = metadata["approval_threshold_numerator"]
    denominator = metadata["approval_threshold_denominator"]
    if emergency:
        numerator = metadata["emergency_threshold_numerator"]
        denominator = metadata["emergency_threshold_denominator"]

    return ceil_div(member_total * numerator, denominator)


def required_yes_weight(emergency: bool):
    total_weight = get_total_member_weight()
    assert total_weight > 0, "Governance requires positive voting weight."

    numerator = metadata["approval_threshold_numerator"]
    denominator = metadata["approval_threshold_denominator"]
    if emergency:
        numerator = metadata["emergency_threshold_numerator"]
        denominator = metadata["emergency_threshold_denominator"]

    return ceil_div(total_weight * numerator, denominator)


def required_yes_weight_for_total(total_weight: int, emergency: bool):
    assert total_weight > 0, "Governance requires positive voting weight."

    numerator = metadata["approval_threshold_numerator"]
    denominator = metadata["approval_threshold_denominator"]
    if emergency:
        numerator = metadata["emergency_threshold_numerator"]
        denominator = metadata["emergency_threshold_denominator"]

    return ceil_div(total_weight * numerator, denominator)


def snapshot_member_weights(proposal_id: int):
    total_weight = 0
    for member in get_members_internal():
        weight = get_member_weight(member)
        proposal_vote_weights[proposal_id, member] = weight
        total_weight += weight
    return total_weight


def require_open_proposal(proposal_id: int):
    assert proposals[proposal_id, "kind"], "Proposal does not exist."
    assert (
        proposals[proposal_id, "status"] == STATUS_PENDING
    ), "Proposal is not open."
    assert now < proposals[proposal_id, "expires_at"], "Proposal expired."


def initialize_proposal(proposal_id: int, kind: str, summary: str, emergency: bool):
    if summary is None:
        summary = ""
    member_total = len(get_members_internal())
    total_weight = snapshot_member_weights(proposal_id)
    proposals[proposal_id, "kind"] = kind
    proposals[proposal_id, "summary"] = summary
    proposals[proposal_id, "proposer"] = ctx.caller
    proposals[proposal_id, "status"] = STATUS_PENDING
    proposals[proposal_id, "created_at"] = now
    proposals[proposal_id, "expires_at"] = now + datetime.timedelta(
        days=metadata["proposal_expiry_days"]
    )
    proposals[proposal_id, "emergency"] = emergency
    proposals[proposal_id, "member_count_snapshot"] = member_total
    proposals[proposal_id, "required_yes_votes"] = required_yes_votes_for_member_total(
        member_total, emergency
    )
    proposals[proposal_id, "total_weight_snapshot"] = total_weight
    proposals[proposal_id, "required_yes_weight"] = required_yes_weight_for_total(
        total_weight, emergency
    )
    proposal_vote_counts[proposal_id, "yes"] = 0
    proposal_vote_counts[proposal_id, "no"] = 0
    proposal_vote_counts[proposal_id, "yes_weight"] = 0
    proposal_vote_counts[proposal_id, "no_weight"] = 0
    ProposalSubmittedEvent(
        {
            "proposal_id": proposal_id,
            "kind": kind,
            "proposer": ctx.caller,
            "summary": summary,
        }
    )


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


def maybe_finalize(proposal_id: int):
    yes_votes = proposal_vote_counts[proposal_id, "yes"]
    no_votes = proposal_vote_counts[proposal_id, "no"]
    member_total = proposals[proposal_id, "member_count_snapshot"]
    required_votes = proposals[proposal_id, "required_yes_votes"]
    yes_weight = proposal_vote_counts[proposal_id, "yes_weight"]
    no_weight = proposal_vote_counts[proposal_id, "no_weight"]
    total_weight = proposals[proposal_id, "total_weight_snapshot"]
    required_weight = proposals[proposal_id, "required_yes_weight"]

    if yes_weight >= required_weight:
        approve_proposal(proposal_id)
        return

    remaining_weight = total_weight - yes_weight - no_weight
    if yes_weight + remaining_weight < required_weight:
        proposals[proposal_id, "status"] = STATUS_REJECTED
        return

    if no_votes > member_total - required_votes:
        proposals[proposal_id, "status"] = STATUS_REJECTED


def approve_proposal(proposal_id: int):
    proposals[proposal_id, "status"] = STATUS_APPROVED
    proposals[proposal_id, "approved_at"] = now
    ProposalApprovedEvent(
        {
            "proposal_id": proposal_id,
            "kind": proposals[proposal_id, "kind"],
            "approver": ctx.caller,
        }
    )

    if proposals[proposal_id, "kind"] == KIND_STATE_PATCH:
        approve_state_patch(proposal_id)
        return

    execute_contract_call(proposal_id)


def approve_state_patch(proposal_id: int):
    patch_id = proposals[proposal_id, "patch_id"]
    activation_height = proposals[proposal_id, "activation_height"]
    patches[patch_id, "status"] = STATUS_APPROVED
    patches[patch_id, "approved_at"] = now
    scheduled_patches[activation_height, patch_id] = True

    emergency_label = "false"
    if proposals[proposal_id, "emergency"]:
        emergency_label = "true"

    StatePatchScheduledEvent(
        {
            "proposal_id": proposal_id,
            "patch_id": patch_id,
            "bundle_hash": proposals[proposal_id, "bundle_hash"],
            "activation_height": activation_height,
            "emergency": emergency_label,
        }
    )


def execute_contract_call(proposal_id: int):
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


@export
def propose_state_patch(
    patch_id: str,
    bundle_hash: str,
    activation_height: int,
    summary: str = "",
    uri: str = "",
    emergency: bool = False,
):
    require_member()
    if summary is None:
        summary = ""
    if uri is None:
        uri = ""
    assert patches[patch_id, "proposal_id"] is None, "Patch already exists."
    assert bundle_hash, "bundle_hash is required."
    assert activation_height > block_num, "Patch must target a future block."

    min_delay = metadata["min_patch_delay_blocks"]
    if emergency:
        min_delay = metadata["emergency_patch_delay_blocks"]

    assert (
        activation_height >= block_num + min_delay
    ), "Patch activation height is too soon."

    proposal_id = next_proposal_id()
    initialize_proposal(proposal_id, KIND_STATE_PATCH, summary, emergency)

    proposals[proposal_id, "patch_id"] = patch_id
    proposals[proposal_id, "bundle_hash"] = bundle_hash
    proposals[proposal_id, "activation_height"] = activation_height
    proposals[proposal_id, "uri"] = uri

    patches[patch_id, "proposal_id"] = proposal_id
    patches[patch_id, "bundle_hash"] = bundle_hash
    patches[patch_id, "activation_height"] = activation_height
    patches[patch_id, "summary"] = summary
    patches[patch_id, "uri"] = uri
    patches[patch_id, "emergency"] = emergency
    patches[patch_id, "status"] = STATUS_PROPOSED
    patches[patch_id, "created_at"] = now

    record_vote(proposal_id, True)
    return get_proposal(proposal_id)


@export
def propose_contract_call(
    target_contract: str,
    target_function: str,
    kwargs: dict = None,
    summary: str = "",
):
    require_member()
    if summary is None:
        summary = ""
    assert target_contract, "target_contract is required."
    assert target_function, "target_function is required."

    proposal_id = next_proposal_id()
    initialize_proposal(proposal_id, KIND_CONTRACT_CALL, summary, False)

    proposals[proposal_id, "target_contract"] = target_contract
    proposals[proposal_id, "target_function"] = target_function
    proposals[proposal_id, "kwargs"] = kwargs

    record_vote(proposal_id, True)
    return get_proposal(proposal_id)


@export
def vote(proposal_id: int, support: bool):
    record_vote(proposal_id, support)
    return get_proposal(proposal_id)


@export
def expire_proposal(proposal_id: int):
    assert proposals[proposal_id, "kind"], "Proposal does not exist."
    assert proposals[proposal_id, "status"] == STATUS_PENDING, "Proposal is not pending."
    assert now >= proposals[proposal_id, "expires_at"], "Proposal has not expired."
    proposals[proposal_id, "status"] = STATUS_EXPIRED
    proposals[proposal_id, "expired_at"] = now
    return get_proposal(proposal_id)


@export
def get_proposal(proposal_id: int):
    kind = proposals[proposal_id, "kind"]
    assert kind, "Proposal does not exist."
    emergency = proposals[proposal_id, "emergency"] == True

    return {
        "proposal_id": proposal_id,
        "kind": kind,
        "summary": proposals[proposal_id, "summary"],
        "proposer": proposals[proposal_id, "proposer"],
        "status": proposals[proposal_id, "status"],
        "created_at": proposals[proposal_id, "created_at"],
        "expires_at": proposals[proposal_id, "expires_at"],
        "approved_at": proposals[proposal_id, "approved_at"],
        "executed_at": proposals[proposal_id, "executed_at"],
        "emergency": emergency,
        "yes_votes": proposal_vote_counts[proposal_id, "yes"],
        "no_votes": proposal_vote_counts[proposal_id, "no"],
        "yes_weight": proposal_vote_counts[proposal_id, "yes_weight"],
        "no_weight": proposal_vote_counts[proposal_id, "no_weight"],
        "required_yes_votes": proposals[proposal_id, "required_yes_votes"],
        "required_yes_weight": proposals[proposal_id, "required_yes_weight"],
        "total_weight_snapshot": proposals[proposal_id, "total_weight_snapshot"],
        "patch_id": proposals[proposal_id, "patch_id"],
        "bundle_hash": proposals[proposal_id, "bundle_hash"],
        "activation_height": proposals[proposal_id, "activation_height"],
        "uri": proposals[proposal_id, "uri"],
        "target_contract": proposals[proposal_id, "target_contract"],
        "target_function": proposals[proposal_id, "target_function"],
        "kwargs": proposals[proposal_id, "kwargs"],
    }


@export
def get_patch(patch_id: str):
    proposal_id = patches[patch_id, "proposal_id"]
    assert proposal_id is not None, "Patch does not exist."
    return {
        "patch_id": patch_id,
        "proposal_id": proposal_id,
        "bundle_hash": patches[patch_id, "bundle_hash"],
        "activation_height": patches[patch_id, "activation_height"],
        "summary": patches[patch_id, "summary"],
        "uri": patches[patch_id, "uri"],
        "emergency": patches[patch_id, "emergency"] == True,
        "status": patches[patch_id, "status"],
        "created_at": patches[patch_id, "created_at"],
        "approved_at": patches[patch_id, "approved_at"],
        "applied_at_nanos": patches[patch_id, "applied_at_nanos"],
        "applied_block_height": patches[patch_id, "applied_block_height"],
        "applied_block_hash": patches[patch_id, "applied_block_hash"],
        "execution_hash": patches[patch_id, "execution_hash"],
    }


@export
def is_patch_approved(patch_id: str):
    status = patches[patch_id, "status"]
    return status == STATUS_APPROVED or status == STATUS_APPLIED


@export
def get_members():
    return get_members_internal()


@export
def required_votes_for(emergency: bool = False):
    return required_yes_votes(emergency)


@export
def required_vote_weight_for(emergency: bool = False):
    return required_yes_weight(emergency)
