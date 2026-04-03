import pytest
from xian_runtime_types.time import Datetime


def test_weighted_governance_can_take_control_and_execute_timelocked_change(protocol):
    protocol.oracle.start_governance_transfer(
        new_governor="protocol_governance",
        signer="governor",
    )

    start = {"now": Datetime(year=2026, month=1, day=1)}
    execute_time = {"now": Datetime(year=2026, month=1, day=2, hour=0, minute=0, second=1)}

    proposal = protocol.protocol_governance.propose_contract_call(
        target_contract="oracle",
        target_function="accept_governance",
        summary="Move oracle to protocol governance",
        signer="alice",
        environment=start,
    )
    assert proposal["required_yes_weight"] == 3
    assert proposal["yes_weight"] == 2
    assert proposal["status"] == "pending"

    queued = protocol.protocol_governance.vote(
        proposal_id=proposal["proposal_id"],
        support=True,
        signer="bob",
        environment=start,
    )
    assert queued["status"] == "queued"

    with pytest.raises(AssertionError):
        protocol.protocol_governance.execute(
            proposal_id=proposal["proposal_id"],
            signer="carol",
            environment=start,
        )

    executed = protocol.protocol_governance.execute(
        proposal_id=proposal["proposal_id"],
        signer="carol",
        environment=execute_time,
    )
    assert executed["status"] == "executed"
    assert protocol.oracle.governor_of() == "protocol_governance"

    reporter_proposal_start = {"now": Datetime(year=2026, month=1, day=3)}
    reporter_execute_time = {
        "now": Datetime(year=2026, month=1, day=4, hour=0, minute=0, second=1)
    }

    reporter_proposal = protocol.protocol_governance.propose_contract_call(
        target_contract="oracle",
        target_function="set_reporter",
        kwargs={"account": "oracle_2", "enabled": True},
        summary="Add second oracle reporter",
        signer="alice",
        environment=reporter_proposal_start,
    )
    protocol.protocol_governance.vote(
        proposal_id=reporter_proposal["proposal_id"],
        support=True,
        signer="bob",
        environment=reporter_proposal_start,
    )
    protocol.protocol_governance.execute(
        proposal_id=reporter_proposal["proposal_id"],
        signer="carol",
        environment=reporter_execute_time,
    )

    assert protocol.oracle.is_reporter(account="oracle_2") is True
