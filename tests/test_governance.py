from xian_runtime_types.time import Datetime


def test_xian_governance_can_take_control_of_protocol_contracts(protocol):
    protocol.oracle.start_governance_transfer(
        new_governor="governance",
        signer="governor",
    )

    start = {"now": Datetime(year=2026, month=1, day=1)}

    proposal = protocol.governance.propose_contract_call(
        target_contract="oracle",
        target_function="accept_governance",
        summary="Move oracle to Xian governance",
        signer="alice",
        environment=start,
    )
    assert proposal["required_yes_weight"] == 3
    assert proposal["yes_weight"] == 2
    assert proposal["status"] == "pending"

    executed = protocol.governance.vote(
        proposal_id=proposal["proposal_id"],
        support=True,
        signer="bob",
        environment=start,
    )
    assert executed["status"] == "executed"
    assert protocol.oracle.governor_of() == "governance"

    reporter_proposal_start = {"now": Datetime(year=2026, month=1, day=3)}

    reporter_proposal = protocol.governance.propose_contract_call(
        target_contract="oracle",
        target_function="set_reporter",
        kwargs={"account": "oracle_2", "enabled": True},
        summary="Add second oracle reporter",
        signer="alice",
        environment=reporter_proposal_start,
    )
    reporter_update = protocol.governance.vote(
        proposal_id=reporter_proposal["proposal_id"],
        support=True,
        signer="bob",
        environment=reporter_proposal_start,
    )

    assert reporter_update["status"] == "executed"
    assert protocol.oracle.is_reporter(account="oracle_2") is True


def test_xian_governance_can_update_protocol_risk_parameters(protocol):
    protocol.vaults.start_governance_transfer(
        new_governor="governance",
        signer="governor",
    )

    start = {"now": Datetime(year=2026, month=2, day=1)}

    accept = protocol.governance.propose_contract_call(
        target_contract="vaults",
        target_function="accept_governance",
        summary="Move vault engine to Xian governance",
        signer="alice",
        environment=start,
    )
    protocol.governance.vote(
        proposal_id=accept["proposal_id"],
        support=True,
        signer="bob",
        environment=start,
    )

    fee_change = protocol.governance.propose_contract_call(
        target_contract="vaults",
        target_function="set_vault_type_fee",
        kwargs={
            "vault_type_id": protocol.vault_type_id,
            "stability_fee_bps": 750,
        },
        summary="Raise stability fee",
        signer="alice",
        environment=start,
    )
    updated = protocol.governance.vote(
        proposal_id=fee_change["proposal_id"],
        support=True,
        signer="bob",
        environment=start,
    )

    assert updated["status"] == "executed"
    assert (
        protocol.vaults.get_vault_type(vault_type_id=protocol.vault_type_id)[
            "stability_fee_bps"
        ]
        == 750
    )
