from decimal import Decimal

import pytest
from xian_runtime_types.time import Datetime


@pytest.mark.parametrize("vault_type_id", [-1, 999])
def test_recapitalization_rejects_nonexistent_vault_type_without_spending(protocol, vault_type_id):
    protocol.stable_token.mint(amount=10, to="alice", signer="governor")
    protocol.stable_token.approve(amount=10, to="con_vaults", signer="alice")
    supply = protocol.stable_token.total_supply_of()

    with pytest.raises(AssertionError, match="Vault type does not exist"):
        protocol.vaults.recapitalize(vault_type_id=vault_type_id, amount=10, signer="alice")

    assert protocol.stable_token.balance_of(address="alice") == 10
    assert protocol.stable_token.balance_of(address="con_vaults") == 0
    assert protocol.stable_token.allowance(owner="alice", spender="con_vaults") == 10
    assert protocol.stable_token.total_supply_of() == supply
    assert (
        protocol.client.raw_driver.get(f"con_vaults.vault_types:{vault_type_id}:surplus_buffer")
        is None
    )


def test_inactive_existing_vault_type_can_still_be_recapitalized(protocol):
    protocol.stable_token.mint(amount=10, to="alice", signer="governor")
    protocol.stable_token.approve(amount=10, to="con_vaults", signer="alice")
    protocol.vaults.set_vault_type_active(
        vault_type_id=protocol.vault_type_id, active=False, signer="governor"
    )

    result = protocol.vaults.recapitalize(
        vault_type_id=protocol.vault_type_id, amount=10, signer="alice"
    )

    assert result == {"bad_debt_reduced": 0, "surplus_added": 10}
    assert protocol.stable_token.balance_of(address="alice") == 0
    state = protocol.vaults.get_vault_type(vault_type_id=protocol.vault_type_id)
    assert state["active"] is False
    assert state["surplus_buffer"] == 10


def test_create_and_close_vault_routes_fees_to_savings_and_surplus(protocol):
    start = {"now": Datetime(year=2026, month=1, day=1)}
    end = {"now": Datetime(year=2027, month=1, day=1)}
    saved = protocol.seed_saver()

    vault_id = protocol.vaults.create_vault(
        vault_type_id=protocol.vault_type_id,
        collateral_amount=100,
        debt_amount=100,
        signer="alice",
        environment=start,
    )

    protocol.stable_token.mint(amount=10, to="alice", signer="governor")
    protocol.stable_token.approve(amount=200, to="con_vaults", signer="alice")

    returned_collateral = protocol.vaults.close_vault(
        vault_id=vault_id,
        signer="alice",
        environment=end,
    )
    vault_type = protocol.vaults.get_vault_type(vault_type_id=protocol.vault_type_id)

    assert returned_collateral == 100
    assert protocol.savings.total_assets() - saved == pytest.approx(4)
    assert vault_type["surplus_buffer"] == pytest.approx(1)
    assert protocol.stable_token.balance_of(address="alice") == pytest.approx(5)
    assert protocol.collateral_token.balance_of(address="alice") == pytest.approx(1_000)
    assert vault_type["live_principal_outstanding"] == 0


def test_fees_route_to_treasury_while_savings_has_no_depositors(protocol):
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
    protocol.stable_token.approve(amount=200, to="con_vaults", signer="alice")

    protocol.vaults.close_vault(vault_id=vault_id, signer="alice", environment=end)

    assert protocol.savings.total_assets() == 0
    assert protocol.stable_token.balance_of(address="treasury") == pytest.approx(4)


def test_savings_contract_must_expose_share_supply(protocol):
    with pytest.raises(AssertionError, match="savings contract"):
        protocol.vaults.set_savings_contract(target_contract="con_oracle", signer="governor")

    protocol.vaults.set_savings_contract(target_contract="", signer="governor")
    protocol.vaults.set_savings_contract(target_contract="con_savings", signer="governor")


def test_withdraw_collateral_rejects_unsafe_state(protocol):
    vault_id = protocol.vaults.create_vault(
        vault_type_id=protocol.vault_type_id,
        collateral_amount=100,
        debt_amount=100,
        signer="alice",
    )

    with pytest.raises(AssertionError):
        protocol.vaults.withdraw_collateral(vault_id=vault_id, amount=30, signer="alice")


def test_fast_liquidation_performs_partial_cure(protocol):
    vault_id = protocol.vaults.create_vault(
        vault_type_id=protocol.vault_type_id,
        collateral_amount=100,
        debt_amount=100,
        signer="alice",
    )
    protocol.oracle.submit_price(asset="COL", price=Decimal("1.2"), signer="governor")
    protocol.stable_token.mint(amount=100, to="bob", signer="governor")
    protocol.stable_token.approve(amount=100, to="con_vaults", signer="bob")

    quote = protocol.vaults.get_liquidation_quote(vault_id=vault_id)
    collateral_paid = protocol.vaults.liquidate_fast(vault_id=vault_id, signer="bob")
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
    protocol.oracle.submit_price(asset="COL", price=Decimal("0.5"), signer="governor")
    protocol.stable_token.approve(amount=100, to="con_vaults", signer="alice")

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
    assert float(vault["collateralization_bps"]) == pytest.approx(16666.666666666668)


def test_auction_can_be_cancelled_after_price_recovery_without_bids(protocol):
    start = {"now": Datetime(year=2026, month=1, day=1)}

    vault_id = protocol.vaults.create_vault(
        vault_type_id=protocol.vault_type_id,
        collateral_amount=100,
        debt_amount=100,
        signer="alice",
        environment=start,
    )
    protocol.oracle.submit_price(asset="COL", price=Decimal("0.5"), signer="governor")
    protocol.vaults.open_liquidation_auction(
        vault_id=vault_id,
        signer="bob",
        environment=start,
    )

    protocol.oracle.submit_price(asset="COL", price=2, signer="governor")
    restored = protocol.vaults.cancel_auction_if_safe(vault_id=vault_id, signer="carol")

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
    protocol.oracle.submit_price(asset="COL", price=Decimal("0.5"), signer="governor")
    protocol.stable_token.mint(amount=100, to="bob", signer="governor")
    protocol.stable_token.mint(amount=100, to="carol", signer="governor")
    protocol.stable_token.approve(amount=100, to="con_vaults", signer="bob")
    protocol.stable_token.approve(amount=100, to="con_vaults", signer="carol")

    protocol.vaults.open_liquidation_auction(
        vault_id=vault_id,
        signer="bob",
        environment=start,
    )
    protocol.vaults.bid(
        vault_id=vault_id,
        bid_amount=48,
        signer="bob",
        environment=start,
    )
    protocol.vaults.bid(
        vault_id=vault_id,
        bid_amount=Decimal("50.4"),
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
    assert settlement["winning_bid"] == Decimal("50.4")
    assert settlement["bad_debt"] == pytest.approx(Decimal("49.6"))
    assert refund == 48
    assert protocol.collateral_token.balance_of(address="carol") == pytest.approx(1_100)
    assert protocol.vaults.get_vault_type(vault_type_id=protocol.vault_type_id)[
        "bad_debt"
    ] == pytest.approx(Decimal("49.6"))
    assert protocol.stable_token.total_supply_of() == pytest.approx(Decimal("249.6"))


def test_surplus_can_cover_bad_debt_and_recapitalization_adds_buffer(protocol):
    fee_start = {"now": Datetime(year=2026, month=1, day=1)}
    fee_end = {"now": Datetime(year=2027, month=1, day=1)}
    saved = protocol.seed_saver()

    fee_vault_id = protocol.vaults.create_vault(
        vault_type_id=protocol.vault_type_id,
        collateral_amount=100,
        debt_amount=100,
        signer="alice",
        environment=fee_start,
    )
    protocol.stable_token.mint(amount=10, to="alice", signer="governor")
    protocol.stable_token.approve(amount=200, to="con_vaults", signer="alice")
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
    protocol.oracle.submit_price(asset="COL", price=Decimal("0.5"), signer="governor")
    protocol.stable_token.mint(amount=100, to="carol", signer="governor")
    protocol.stable_token.approve(amount=100, to="con_vaults", signer="carol")

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

    covered = protocol.vaults.cover_bad_debt(vault_type_id=protocol.vault_type_id)
    protocol.stable_token.mint(amount=10, to="carol", signer="governor")
    protocol.stable_token.approve(amount=10, to="con_vaults", signer="carol")
    recapitalized = protocol.vaults.recapitalize(
        vault_type_id=protocol.vault_type_id,
        amount=10,
        signer="carol",
    )
    swept = protocol.vaults.sweep_surplus(vault_type_id=protocol.vault_type_id, signer="governor")

    vault_type = protocol.vaults.get_vault_type(vault_type_id=protocol.vault_type_id)
    assert covered == pytest.approx(1)
    assert recapitalized["bad_debt_reduced"] == 0
    assert recapitalized["surplus_added"] == pytest.approx(10)
    assert swept == pytest.approx(10)
    assert vault_type["bad_debt"] == 0
    assert vault_type["surplus_buffer"] == 0
    assert protocol.savings.total_assets() - saved == pytest.approx(14)


def test_stability_fee_change_applies_only_from_the_change_time(protocol):
    start = {"now": Datetime(year=2026, month=1, day=1)}
    change = {"now": Datetime(year=2027, month=1, day=1)}

    vault_id = protocol.vaults.create_vault(
        vault_type_id=protocol.vault_type_id,
        collateral_amount=300,
        debt_amount=100,
        signer="alice",
        environment=start,
    )

    protocol.vaults.set_vault_type_fee(
        vault_type_id=protocol.vault_type_id,
        stability_fee_bps=5000,
        signer="governor",
        environment=change,
    )

    vault = protocol.vaults.get_vault(vault_id=vault_id, environment=change)
    assert vault["debt"] == pytest.approx(105)


def test_stability_fee_change_rejects_nonexistent_vault_type(protocol):
    with pytest.raises(AssertionError, match="Vault type does not exist"):
        protocol.vaults.set_vault_type_fee(
            vault_type_id=999, stability_fee_bps=100, signer="governor"
        )

    assert protocol.client.raw_driver.get("con_vaults.vault_types:999:stability_fee_bps") is None


def open_unsafe_auction(protocol, price, environment):
    vault_id = protocol.vaults.create_vault(
        vault_type_id=protocol.vault_type_id,
        collateral_amount=100,
        debt_amount=100,
        signer="alice",
        environment=environment,
    )
    protocol.oracle.submit_price(asset="COL", price=price, signer="governor")
    protocol.vaults.open_liquidation_auction(
        vault_id=vault_id, signer="bob", environment=environment
    )
    protocol.stable_token.mint(amount=200, to="bob", signer="governor")
    protocol.stable_token.approve(amount=200, to="con_vaults", signer="bob")
    return vault_id


def test_first_bid_must_cover_debt_when_collateral_covers_it(protocol):
    start = {"now": Datetime(year=2026, month=1, day=1)}
    # 129% collateralized: below the 130% liquidation ratio but not underwater.
    vault_id = open_unsafe_auction(protocol, Decimal("1.29"), start)

    assert protocol.vaults.get_auction(vault_id=vault_id)["min_next_bid"] == 100
    with pytest.raises(AssertionError, match="Bid is too low"):
        protocol.vaults.bid(
            vault_id=vault_id, bid_amount=Decimal("99.99"), signer="bob", environment=start
        )

    assert (
        protocol.vaults.bid(vault_id=vault_id, bid_amount=100, signer="bob", environment=start)
        == 100
    )


def test_first_bid_on_underwater_vault_must_cover_discounted_collateral_value(protocol):
    start = {"now": Datetime(year=2026, month=1, day=1)}
    # Collateral is worth 50 against 100 debt; the 5% liquidation bonus is the discount.
    vault_id = open_unsafe_auction(protocol, Decimal("0.5"), start)

    assert protocol.vaults.get_auction(vault_id=vault_id)["min_next_bid"] == Decimal("47.5")
    with pytest.raises(AssertionError, match="Bid is too low"):
        protocol.vaults.bid(vault_id=vault_id, bid_amount=47, signer="bob", environment=start)

    protocol.vaults.bid(
        vault_id=vault_id, bid_amount=Decimal("47.5"), signer="bob", environment=start
    )


def test_auction_without_bids_can_be_restarted_and_settled(protocol):
    start = {"now": Datetime(year=2026, month=1, day=1)}
    ended = {"now": Datetime(year=2026, month=1, day=3)}
    restarted_end = {"now": Datetime(year=2026, month=1, day=4, hour=1)}
    vault_id = open_unsafe_auction(protocol, Decimal("0.5"), start)

    with pytest.raises(AssertionError, match="Auction already ended"):
        protocol.vaults.bid(vault_id=vault_id, bid_amount=60, signer="bob", environment=ended)

    end_time = protocol.vaults.restart_auction(vault_id=vault_id, signer="carol", environment=ended)
    assert str(end_time).startswith("2026-01-04 00:00:00")
    auction = protocol.vaults.get_auction(vault_id=vault_id)
    assert auction["auction_open"] is True
    assert auction["debt_snapshot"] == 100

    protocol.vaults.bid(vault_id=vault_id, bid_amount=60, signer="bob", environment=ended)
    settlement = protocol.vaults.settle_auction(
        vault_id=vault_id, signer="carol", environment=restarted_end
    )
    assert settlement["winner"] == "bob"
    assert settlement["bad_debt"] == 40


def test_auction_restart_requires_an_ended_auction_without_bids(protocol):
    start = {"now": Datetime(year=2026, month=1, day=1)}
    ended = {"now": Datetime(year=2026, month=1, day=3)}
    vault_id = open_unsafe_auction(protocol, Decimal("0.5"), start)

    with pytest.raises(AssertionError, match="Auction is still open"):
        protocol.vaults.restart_auction(vault_id=vault_id, signer="carol", environment=start)

    protocol.vaults.bid(vault_id=vault_id, bid_amount=60, signer="bob", environment=start)
    with pytest.raises(AssertionError, match="Auction already has bids"):
        protocol.vaults.restart_auction(vault_id=vault_id, signer="carol", environment=ended)

    other_vault = protocol.vaults.create_vault(
        vault_type_id=protocol.vault_type_id,
        collateral_amount=300,
        debt_amount=100,
        signer="carol",
        environment=start,
    )
    with pytest.raises(AssertionError, match="Auction is not open"):
        protocol.vaults.restart_auction(vault_id=other_vault, signer="carol", environment=ended)
