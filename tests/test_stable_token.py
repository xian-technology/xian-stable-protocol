import pytest


def test_stable_token_controller_mint(protocol):
    protocol.stable_token.mint(amount=50, to="alice", signer="governor")

    assert protocol.stable_token.balance_of(address="alice") == 50
    assert protocol.stable_token.total_supply_of() == 50


def test_stable_token_transfer_from_uses_exact_approval(protocol):
    protocol.stable_token.mint(amount=100, to="alice", signer="governor")
    protocol.stable_token.approve(amount=40, to="bob", signer="alice")
    protocol.stable_token.transfer_from(
        amount=25,
        to="carol",
        main_account="alice",
        signer="bob",
    )

    assert protocol.stable_token.balance_of(address="alice") == 75
    assert protocol.stable_token.balance_of(address="carol") == 25
    assert protocol.stable_token.allowance(owner="alice", spender="bob") == 15


def test_stable_token_non_controller_cannot_mint(protocol):
    with pytest.raises(AssertionError):
        protocol.stable_token.mint(amount=1, to="alice", signer="alice")
