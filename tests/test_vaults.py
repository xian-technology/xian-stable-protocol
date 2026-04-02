import pytest
from xian_runtime_types.time import Datetime


def test_create_and_close_vault_routes_fees_to_savings(protocol):
    start = {"now": Datetime(year=2026, month=1, day=1)}
    end = {"now": Datetime(year=2027, month=1, day=1)}

    vault_id = protocol.vaults.create_vault(
        vault_type_id=protocol.vault_type_id,
        collateral_amount=100,
        debt_amount=100,
        signer="alice",
        environment=start,
    )

    protocol.stable_token.mint(amount=10, to="alice", signer="governor")
    protocol.stable_token.approve(amount=200, to="vaults", signer="alice")

    returned_collateral = protocol.vaults.close_vault(
        vault_id=vault_id,
        signer="alice",
        environment=end,
    )

    assert returned_collateral == 100
    assert protocol.savings.total_assets() == pytest.approx(5)
    assert protocol.stable_token.balance_of(account="alice") == pytest.approx(5)
    assert protocol.collateral_token.balance_of(account="alice") == pytest.approx(1_000)
    assert (
        protocol.vaults.get_vault_type(vault_type_id=protocol.vault_type_id)[
            "principal_outstanding"
        ]
        == 0
    )


def test_withdraw_collateral_rejects_unsafe_state(protocol):
    vault_id = protocol.vaults.create_vault(
        vault_type_id=protocol.vault_type_id,
        collateral_amount=100,
        debt_amount=100,
        signer="alice",
    )

    with pytest.raises(AssertionError):
        protocol.vaults.withdraw_collateral(vault_id=vault_id, amount=30, signer="alice")


def test_fast_liquidation_pays_bonus_and_returns_remainder(protocol):
    vault_id = protocol.vaults.create_vault(
        vault_type_id=protocol.vault_type_id,
        collateral_amount=100,
        debt_amount=100,
        signer="alice",
    )
    protocol.oracle.set_price(asset="COL", price=1.2, signer="governor")
    protocol.stable_token.mint(amount=100, to="bob", signer="governor")
    protocol.stable_token.approve(amount=100, to="vaults", signer="bob")

    collateral_paid = protocol.vaults.liquidate_fast(vault_id=vault_id, signer="bob")

    assert collateral_paid == pytest.approx(87.5)
    assert protocol.collateral_token.balance_of(account="bob") == pytest.approx(1_087.5)
    assert protocol.collateral_token.balance_of(account="alice") == pytest.approx(912.5)
    assert protocol.vaults.get_vault(vault_id=vault_id)["open"] is False


def test_auction_records_bad_debt_and_allows_loser_refund(protocol):
    start = {"now": Datetime(year=2026, month=1, day=1)}
    end = {"now": Datetime(year=2026, month=1, day=3)}

    vault_id = protocol.vaults.create_vault(
        vault_type_id=protocol.vault_type_id,
        collateral_amount=100,
        debt_amount=100,
        signer="alice",
        environment=start,
    )
    protocol.oracle.set_price(asset="COL", price=0.5, signer="governor")
    protocol.stable_token.mint(amount=100, to="bob", signer="governor")
    protocol.stable_token.mint(amount=100, to="carol", signer="governor")
    protocol.stable_token.approve(amount=100, to="vaults", signer="bob")
    protocol.stable_token.approve(amount=100, to="vaults", signer="carol")

    protocol.vaults.open_liquidation_auction(
        vault_id=vault_id,
        signer="bob",
        environment=start,
    )
    protocol.vaults.bid(
        vault_id=vault_id,
        bid_amount=40,
        signer="bob",
        environment=start,
    )
    protocol.vaults.bid(
        vault_id=vault_id,
        bid_amount=45,
        signer="carol",
        environment=start,
    )
    settlement = protocol.vaults.settle_auction(
        vault_id=vault_id,
        signer="bob",
        environment=end,
    )

    refund = protocol.vaults.claim_refund(vault_id=vault_id, signer="bob")

    assert settlement["winner"] == "carol"
    assert settlement["winning_bid"] == 45
    assert settlement["bad_debt"] == pytest.approx(55)
    assert refund == 40
    assert protocol.collateral_token.balance_of(account="carol") == pytest.approx(1_100)
    assert (
        protocol.vaults.get_vault_type(vault_type_id=protocol.vault_type_id)[
            "bad_debt"
        ]
        == pytest.approx(55)
    )
    assert protocol.stable_token.total_supply_of() == pytest.approx(255)
