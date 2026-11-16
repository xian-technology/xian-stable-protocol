from pathlib import Path

import pytest
from contracting.local import ContractingClient

LOWER = "ab" * 32
UPPER = LOWER.upper()


@pytest.mark.parametrize("target", [UPPER, "aB" * 32])
@pytest.mark.parametrize("operation", ["transfer", "transfer_from", "mint", "approve"])
def test_stable_token_rejects_noncanonical_account_without_moving_value(
    protocol, operation, target
):
    token = protocol.stable_token
    token.mint(amount=20, to="alice", signer="governor")
    token.approve(amount=20, to="bob", signer="alice")
    arguments = {"amount": 5, "to": target}
    signer = "alice"
    if operation == "mint":
        signer = "governor"
    elif operation == "transfer_from":
        signer = "bob"
        arguments["main_account"] = "alice"

    with pytest.raises(AssertionError, match="canonical lowercase"):
        getattr(token, operation)(**arguments, signer=signer)

    assert token.balance_of(address="alice") == 20
    assert token.balance_of(address=target) == 0
    assert token.total_supply_of() == 20
    assert token.allowance(owner="alice", spender="bob") == 20


@pytest.mark.parametrize("operation", ["transfer", "transfer_from", "approve"])
def test_savings_shares_reject_noncanonical_destination(protocol, operation):
    protocol.seed_saver(amount=20, account="alice")
    protocol.savings.approve(amount=20, to="bob", signer="alice")
    arguments = {"amount": 5, "to": UPPER}
    signer = "alice"
    if operation == "transfer_from":
        signer = "bob"
        arguments["main_account"] = "alice"

    with pytest.raises(AssertionError, match="canonical lowercase"):
        getattr(protocol.savings, operation)(**arguments, signer=signer)

    assert protocol.savings.balance_of(address="alice") == 20
    assert protocol.savings.balance_of(address=UPPER) == 0
    assert protocol.savings.total_supply() == 20


@pytest.mark.parametrize("destination", ["NamedDestination", "G" * 64])
def test_stable_token_keeps_lowercase_keys_and_named_accounts(protocol, destination):
    protocol.stable_token.mint(amount=10, to=LOWER, signer="governor")
    protocol.stable_token.transfer(amount=4, to=destination, signer=LOWER)
    assert protocol.stable_token.balance_of(address=LOWER) == 6
    assert protocol.stable_token.balance_of(address=destination) == 4


@pytest.mark.parametrize("field", ["initial_holder", "governor_address"])
def test_token_constructor_cannot_lock_supply_or_authority_to_uppercase_key(tmp_path, field):
    source = (
        Path(__file__).resolve().parents[1] / "contracts" / "con_stable_token.s.py"
    ).read_text()
    client = ContractingClient(storage_home=tmp_path)
    with pytest.raises(AssertionError, match="canonical lowercase"):
        client.submit(
            source,
            name="con_token",
            constructor_args={"token_name": "Token", "token_symbol": "TOK", field: UPPER},
        )


@pytest.mark.parametrize(
    "operation,field",
    [("start_governance_transfer", "new_governor"), ("set_controller", "account")],
)
def test_token_authority_changes_reject_noncanonical_keys(protocol, operation, field):
    args = {field: UPPER}
    if operation == "set_controller":
        args["enabled"] = True
    with pytest.raises(AssertionError, match="canonical lowercase"):
        getattr(protocol.stable_token, operation)(**args, signer="governor")
    assert protocol.stable_token.governor_of() == "governor"
    assert protocol.stable_token.is_controller(account=UPPER) is False
