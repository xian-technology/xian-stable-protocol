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


def test_stable_token_supply_matches_tracked_balances_after_mint_transfer_burn(protocol):
    protocol.stable_token.mint(amount=100, to="alice", signer="governor")
    protocol.stable_token.transfer(amount=35, to="bob", signer="alice")
    protocol.stable_token.burn(amount=15, signer="bob")

    tracked_balances = sum(
        protocol.stable_token.balance_of(address=account)
        for account in ("vaults", "alice", "bob")
    )
    assert protocol.stable_token.total_supply_of() == 85
    assert protocol.stable_token.total_supply_of() == tracked_balances


def test_stable_token_rejects_invalid_amounts_without_changing_supply(protocol):
    protocol.stable_token.mint(amount=10, to="alice", signer="governor")
    starting_supply = protocol.stable_token.total_supply_of()

    with pytest.raises(AssertionError):
        protocol.stable_token.mint(amount=0, to="alice", signer="governor")

    with pytest.raises(AssertionError):
        protocol.stable_token.transfer(amount=0, to="bob", signer="alice")

    with pytest.raises(AssertionError):
        protocol.stable_token.burn(amount=11, signer="alice")

    assert protocol.stable_token.total_supply_of() == starting_supply
    assert protocol.stable_token.balance_of(address="alice") == 10
    assert protocol.stable_token.balance_of(address="bob") == 0


def test_stable_token_non_controller_cannot_mint(protocol):
    with pytest.raises(AssertionError):
        protocol.stable_token.mint(amount=1, to="alice", signer="alice")
