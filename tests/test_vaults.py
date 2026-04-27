import pytest
from xian_runtime_types.time import Datetime


def test_create_and_close_vault_routes_fees_to_savings_and_surplus(protocol):
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
    vault_type = protocol.vaults.get_vault_type(
        vault_type_id=protocol.vault_type_id
    )

    assert returned_collateral == 100
    assert protocol.savings.total_assets() == pytest.approx(4)
    assert vault_type["surplus_buffer"] == pytest.approx(1)
    assert protocol.stable_token.balance_of(address="alice") == pytest.approx(5)
    assert protocol.collateral_token.balance_of(
        address="alice"
    ) == pytest.approx(1_000)
    assert vault_type["live_principal_outstanding"] == 0


def test_withdraw_collateral_rejects_unsafe_state(protocol):
    vault_id = protocol.vaults.create_vault(
        vault_type_id=protocol.vault_type_id,
        collateral_amount=100,
        debt_amount=100,
        signer="alice",
    )

    with pytest.raises(AssertionError):
        protocol.vaults.withdraw_collateral(
            vault_id=vault_id, amount=30, signer="alice"
        )


def test_fast_liquidation_performs_partial_cure(protocol):
    vault_id = protocol.vaults.create_vault(
        vault_type_id=protocol.vault_type_id,
        collateral_amount=100,
        debt_amount=100,
        signer="alice",
    )
    protocol.oracle.submit_price(asset="COL", price=1.2, signer="governor")
    protocol.stable_token.mint(amount=100, to="bob", signer="governor")
    protocol.stable_token.approve(amount=100, to="vaults", signer="bob")

    quote = protocol.vaults.get_liquidation_quote(vault_id=vault_id)
    collateral_paid = protocol.vaults.liquidate_fast(
        vault_id=vault_id, signer="bob"
    )
    vault = protocol.vaults.get_vault(vault_id=vault_id)

    assert quote["partial_possible"] is True
    assert collateral_paid == pytest.approx(quote["collateral_out"])
    assert vault["open"] is True
    assert vault["auction_open"] is False
    assert float(vault["debt"]) == pytest.approx(33.33333333333333)
    assert float(vault["collateralization_bps"]) == pytest.approx(15000)
    assert protocol.collateral_token.balance_of(address="bob") == pytest.approx(
        1000 + collateral_paid
    )


def test_auction_can_be_cured_by_owner_before_bids(protocol):
    vault_id = protocol.vaults.create_vault(
        vault_type_id=protocol.vault_type_id,
        collateral_amount=100,
        debt_amount=100,
        signer="alice",
    )
    protocol.oracle.submit_price(asset="COL", price=0.5, signer="governor")
    protocol.stable_token.approve(amount=100, to="vaults", signer="alice")

    protocol.vaults.open_liquidation_auction(vault_id=vault_id, signer="bob")
    remaining_debt = protocol.vaults.cure_auction(
        vault_id=vault_id,
        repay_amount=70,
        signer="alice",
    )

    vault = protocol.vaults.get_vault(vault_id=vault_id)
    assert remaining_debt == pytest.approx(30)
    assert vault["open"] is True
    assert vault["auction_open"] is False
    assert float(vault["debt"]) == pytest.approx(30)
    assert float(vault["collateralization_bps"]) == pytest.approx(
        16666.666666666668
    )


def test_auction_can_be_cancelled_after_price_recovery_without_bids(protocol):
    start = {"now": Datetime(year=2026, month=1, day=1)}

    vault_id = protocol.vaults.create_vault(
        vault_type_id=protocol.vault_type_id,
        collateral_amount=100,
        debt_amount=100,
        signer="alice",
        environment=start,
    )
    protocol.oracle.submit_price(asset="COL", price=0.5, signer="governor")
    protocol.vaults.open_liquidation_auction(
        vault_id=vault_id,
        signer="bob",
        environment=start,
    )

    protocol.oracle.submit_price(asset="COL", price=2, signer="governor")
    restored = protocol.vaults.cancel_auction_if_safe(
        vault_id=vault_id, signer="carol"
    )

    assert restored["open"] is True
    assert restored["auction_open"] is False


def test_auction_extends_records_bad_debt_and_allows_loser_refund(protocol):
    start = {"now": Datetime(year=2026, month=1, day=1)}
    near_end = {"now": Datetime(year=2026, month=1, day=1, hour=23, minute=30)}
    end = {"now": Datetime(year=2026, month=1, day=2, hour=1, minute=1)}

    vault_id = protocol.vaults.create_vault(
        vault_type_id=protocol.vault_type_id,
        collateral_amount=100,
        debt_amount=100,
        signer="alice",
        environment=start,
    )
    protocol.oracle.submit_price(asset="COL", price=0.5, signer="governor")
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
        environment=near_end,
    )

    auction = protocol.vaults.get_auction(vault_id=vault_id)
    settlement = protocol.vaults.settle_auction(
        vault_id=vault_id,
        signer="bob",
        environment=end,
    )
    refund = protocol.vaults.claim_refund(vault_id=vault_id, signer="bob")

    assert str(auction["auction_end_time"]).startswith("2026-01-02 01:00:00")
    assert settlement["winner"] == "carol"
    assert settlement["winning_bid"] == 45
    assert settlement["bad_debt"] == pytest.approx(55)
    assert refund == 40
    assert protocol.collateral_token.balance_of(
        address="carol"
    ) == pytest.approx(1_100)
    assert protocol.vaults.get_vault_type(vault_type_id=protocol.vault_type_id)[
        "bad_debt"
    ] == pytest.approx(55)
    assert protocol.stable_token.total_supply_of() == pytest.approx(255)


def test_surplus_can_cover_bad_debt_and_recapitalization_adds_buffer(protocol):
    fee_start = {"now": Datetime(year=2026, month=1, day=1)}
    fee_end = {"now": Datetime(year=2027, month=1, day=1)}

    fee_vault_id = protocol.vaults.create_vault(
        vault_type_id=protocol.vault_type_id,
        collateral_amount=100,
        debt_amount=100,
        signer="alice",
        environment=fee_start,
    )
    protocol.stable_token.mint(amount=10, to="alice", signer="governor")
    protocol.stable_token.approve(amount=200, to="vaults", signer="alice")
    protocol.vaults.close_vault(
        vault_id=fee_vault_id,
        signer="alice",
        environment=fee_end,
    )

    auction_start = {"now": Datetime(year=2026, month=2, day=1)}
    auction_end = {"now": Datetime(year=2026, month=2, day=2)}
    auction_vault_id = protocol.vaults.create_vault(
        vault_type_id=protocol.vault_type_id,
        collateral_amount=100,
        debt_amount=100,
        signer="bob",
        environment=auction_start,
    )
    protocol.oracle.submit_price(asset="COL", price=0.5, signer="governor")
    protocol.stable_token.mint(amount=100, to="carol", signer="governor")
    protocol.stable_token.approve(amount=100, to="vaults", signer="carol")

    protocol.vaults.open_liquidation_auction(
        vault_id=auction_vault_id,
        signer="alice",
        environment=auction_start,
    )
    protocol.vaults.bid(
        vault_id=auction_vault_id,
        bid_amount=99,
        signer="carol",
        environment=auction_start,
    )
    protocol.vaults.settle_auction(
        vault_id=auction_vault_id,
        signer="alice",
        environment=auction_end,
    )

    covered = protocol.vaults.cover_bad_debt(
        vault_type_id=protocol.vault_type_id
    )
    protocol.stable_token.mint(amount=10, to="carol", signer="governor")
    protocol.stable_token.approve(amount=10, to="vaults", signer="carol")
    recapitalized = protocol.vaults.recapitalize(
        vault_type_id=protocol.vault_type_id,
        amount=10,
        signer="carol",
    )
    swept = protocol.vaults.sweep_surplus(
        vault_type_id=protocol.vault_type_id, signer="governor"
    )

    vault_type = protocol.vaults.get_vault_type(
        vault_type_id=protocol.vault_type_id
    )
    assert covered == pytest.approx(1)
    assert recapitalized["bad_debt_reduced"] == 0
    assert recapitalized["surplus_added"] == pytest.approx(10)
    assert swept == pytest.approx(10)
    assert vault_type["bad_debt"] == 0
    assert vault_type["surplus_buffer"] == 0
    assert protocol.savings.total_assets() == pytest.approx(14)
