"""Money timers start at immutable successor clocks, including after long idle."""

from decimal import Decimal, getcontext
from pathlib import Path

import pytest
from xian_runtime_types.time import Datetime

getcontext().prec = 120

T0 = Datetime(2026, 1, 1)
FRESH = Datetime(2026, 4, 11)
YEAR_LATER = Datetime(2027, 4, 11)


def env(height, when):
    return {"block_num": height, "now": when}


@pytest.fixture
def timed(protocol):
    p = protocol
    if p.client.get_contract_ir("time_checkpoints") is None:
        source = (
            Path(__file__).resolve().parents[2] / "xian-configs/contracts/time_checkpoints.s.py"
        )
        p.client.submit(source.read_text(), name="time_checkpoints", owner=None)
    p.clock = p.client.get_contract_proxy("time_checkpoints")
    p.client.environment.update(env(1, T0))
    p.clock.process_time_anchors(signer="__time_checkpoints__", environment=env(1, T0))
    return p


def anchor(p, height, when):
    return p.clock.process_time_anchors(
        signer="__time_checkpoints__", environment=env(height, when)
    )


def open_vault(p, who="alice", height=100, when=T0):
    return p.vaults.create_vault(
        vault_type_id=p.vault_type_id,
        collateral_amount=200,
        debt_amount=100,
        signer=who,
        environment=env(height, when),
    )


def test_fresh_debt_has_no_idle_gap_interest_but_accrues_after_its_anchor(timed):
    p = timed
    vault = open_vault(p)
    anchor(p, 101, FRESH)
    at_anchor = p.vaults.get_vault(vault_id=vault, environment=env(101, FRESH))
    assert at_anchor["debt"] == 100
    assert at_anchor["fee_due"] == 0
    later = p.vaults.get_vault(vault_id=vault, environment=env(102, YEAR_LATER))
    assert float(later["debt"]) == pytest.approx(105)


def test_fee_change_uses_old_rate_until_its_successor_anchor(timed):
    p = timed
    vault = open_vault(p, height=10)
    anchor(p, 11, T0)
    p.vaults.set_vault_type_fee(
        vault_type_id=p.vault_type_id,
        stability_fee_bps=5000,
        signer="governor",
        environment=env(100, T0),
    )
    anchor(p, 101, FRESH)
    old_fee_debt = Decimal(100) * (1 + Decimal("0.05") * Decimal(100) / 365)
    assert float(
        p.vaults.get_vault(vault_id=vault, environment=env(101, FRESH))["debt"]
    ) == pytest.approx(float(old_fee_debt))
    assert float(
        p.vaults.get_vault(vault_id=vault, environment=env(102, YEAR_LATER))["debt"]
    ) == pytest.approx(float(old_fee_debt * Decimal("1.5")))


def test_cross_vault_accrual_does_not_lose_pending_group_conversion_rate(timed):
    p = timed
    older = open_vault(p, height=10)
    anchor(p, 11, T0)
    newer = open_vault(p, who="bob")
    p.vaults.borrow(vault_id=older, amount=50, signer="alice", environment=env(100, T0))
    anchor(p, 101, FRESH)
    p.vaults.withdraw_collateral(
        vault_id=older, amount=1, signer="alice", environment=env(101, FRESH)
    )
    assert p.vaults.get_vault(vault_id=newer, environment=env(101, FRESH))["debt"] == 100
    a = p.vaults.get_vault(vault_id=older, environment=env(101, FRESH))
    b = p.vaults.get_vault(vault_id=newer, environment=env(101, FRESH))
    totals = p.vaults.get_vault_type(vault_type_id=p.vault_type_id, environment=env(101, FRESH))
    assert float(totals["live_debt_outstanding"]) == pytest.approx(float(a["debt"] + b["debt"]))
    assert totals["live_principal_outstanding"] == 250
    assert float(
        p.vaults.get_vault(vault_id=newer, environment=env(102, YEAR_LATER))["debt"]
    ) == pytest.approx(105)


def test_pending_debt_can_be_repaid_and_closed_without_resurrection(timed):
    p = timed
    vault = open_vault(p)
    p.stable_token.approve(amount=100, to="con_vaults", signer="alice")
    p.vaults.repay(vault_id=vault, amount=40, signer="alice", environment=env(100, T0))
    paid = p.vaults.get_vault(vault_id=vault, environment=env(100, T0))
    assert paid["debt"] == paid["principal"] == 60
    p.vaults.close_vault(vault_id=vault, signer="alice", environment=env(100, T0))
    anchor(p, 101, FRESH)
    assert p.stable_token.total_supply_of() == 0
    assert (
        p.vaults.get_vault_type(vault_type_id=p.vault_type_id, environment=env(101, FRESH))[
            "live_debt_outstanding"
        ]
        == 0
    )


def auction(p, height=100, when=T0):
    vault = open_vault(p, height=10)
    anchor(p, 11, T0)
    p.oracle.submit_price(
        asset="COL", price=Decimal("0.25"), signer="governor", environment=env(height, when)
    )
    p.vaults.open_liquidation_auction(vault_id=vault, signer="bob", environment=env(height, when))
    return vault


def fund_bid(p, vault, height, when):
    minimum = p.vaults.get_auction(vault_id=vault, environment=env(height, when))["min_next_bid"]
    p.stable_token.mint(amount=minimum, to="bob", signer="governor")
    p.stable_token.approve(amount=minimum, to="con_vaults", signer="bob")
    p.vaults.bid(vault_id=vault, bid_amount=minimum, signer="bob", environment=env(height, when))


def test_new_auction_cannot_settle_at_first_fresh_successor(timed):
    p = timed
    vault = auction(p)
    fund_bid(p, vault, 100, T0)
    anchor(p, 101, FRESH)
    with pytest.raises(AssertionError, match="still open|anchor"):
        p.vaults.settle_auction(vault_id=vault, signer="bob", environment=env(101, FRESH))
    assert p.vaults.get_auction(vault_id=vault, environment=env(101, FRESH))[
        "auction_end_time"
    ] == Datetime(2026, 4, 12)


def test_later_height_draw_refuses_an_unresolved_older_debt_group(timed):
    p = timed
    vault = open_vault(p)
    supply = p.stable_token.total_supply_of()
    with pytest.raises(AssertionError, match="anchor|checkpoint"):
        p.vaults.borrow(vault_id=vault, amount=10, signer="alice", environment=env(101, FRESH))
    assert p.stable_token.total_supply_of() == supply


def test_restarted_auction_receives_its_full_window_after_a_long_idle(timed):
    p = timed
    vault = auction(p, height=20)
    anchor(p, 21, T0)
    restart_time = Datetime(2026, 1, 3)
    p.vaults.restart_auction(vault_id=vault, signer="carol", environment=env(100, restart_time))
    fund_bid(p, vault, 100, restart_time)
    anchor(p, 101, FRESH)
    with pytest.raises(AssertionError, match="still open|anchor"):
        p.vaults.settle_auction(vault_id=vault, signer="bob", environment=env(101, FRESH))
    assert p.vaults.get_auction(vault_id=vault, environment=env(101, FRESH))[
        "auction_end_time"
    ] == Datetime(2026, 4, 12)


def test_qualifying_bid_extension_is_not_consumed_by_idle_gap(timed):
    p = timed
    vault = auction(p, height=20)
    anchor(p, 21, T0)
    late = Datetime(2026, 1, 1, 23, 30)
    fund_bid(p, vault, 100, late)
    anchor(p, 101, FRESH)
    with pytest.raises(AssertionError, match="still open|anchor"):
        p.vaults.settle_auction(vault_id=vault, signer="bob", environment=env(101, FRESH))
    assert p.vaults.get_auction(vault_id=vault, environment=env(101, FRESH))[
        "auction_end_time"
    ] == Datetime(2026, 4, 11, 1)


def test_same_height_bid_extensions_preserve_each_captured_interval(timed):
    p = timed
    vault = auction(p, height=20)
    anchor(p, 21, T0)
    late = Datetime(2026, 1, 1, 23, 30)
    p.vaults.set_vault_type_auction_config(
        vault_type_id=p.vault_type_id,
        auction_duration_seconds=86400,
        min_bid_increment_bps=500,
        extension_window_seconds=3600,
        bid_extension_seconds=300,
        signer="governor",
        environment=env(100, late),
    )
    fund_bid(p, vault, 100, late)
    p.vaults.set_vault_type_auction_config(
        vault_type_id=p.vault_type_id,
        auction_duration_seconds=1,
        min_bid_increment_bps=500,
        extension_window_seconds=3600,
        bid_extension_seconds=600,
        signer="governor",
        environment=env(100, late),
    )
    fund_bid(p, vault, 100, late)
    anchor(p, 101, FRESH)
    record = p.vaults.get_auction(vault_id=vault, environment=env(101, FRESH))
    assert record["auction_end_time"] == Datetime(2026, 4, 11, minute=15)
    with pytest.raises(AssertionError, match="still open|anchor"):
        p.vaults.settle_auction(vault_id=vault, signer="bob", environment=env(101, FRESH))


def test_ready_debt_group_moves_once_into_auction_totals(timed):
    p = timed
    auction(p, height=20)
    state = p.vaults.get_vault_type(vault_type_id=p.vault_type_id, environment=env(20, T0))
    assert state["live_debt_outstanding"] == 0
    assert state["live_principal_outstanding"] == 0
    assert state["pending_debt_outstanding"] == 0
    assert state["auction_debt_locked"] == 100
    assert state["auction_principal_locked"] == 100
    assert p.stable_token.total_supply_of() == 100


def test_subprecision_draw_cannot_poison_a_type_after_its_anchor(timed):
    p = timed
    vault = open_vault(p, height=10)
    anchor(p, 11, T0)
    p.vaults.withdraw_collateral(vault_id=vault, amount=1, signer="alice", environment=env(12, T0))
    supply = p.stable_token.total_supply_of()
    p.vaults.borrow(
        vault_id=vault, amount=Decimal("1e-30"), signer="alice", environment=env(100, T0)
    )
    assert p.stable_token.total_supply_of() == supply + Decimal("1e-30")
    anchor(p, 101, FRESH)
    state = p.vaults.get_vault_type(vault_type_id=p.vault_type_id, environment=env(101, FRESH))
    assert state["live_debt_outstanding"] > 100
    assert state["live_debt_carry_total"] == Decimal("1e-30")
    # Ready zero-share debt remains owed and cannot occupy the next group slot.
    p.vaults.borrow(vault_id=vault, amount=1, signer="alice", environment=env(101, FRESH))
    assert p.vaults.get_vault(vault_id=vault, environment=env(101, FRESH))[
        "principal"
    ] == 101 + Decimal("1e-30")


@pytest.mark.parametrize("in_auction", [False, True])
def test_positive_debt_dust_cannot_be_forgiven_or_left_in_type_totals(timed, in_auction):
    p = timed
    vault = auction(p, height=20) if in_auction else open_vault(p, height=20)
    p.stable_token.approve(amount=100, to="con_vaults", signer="alice")
    repay = p.vaults.cure_auction if in_auction else p.vaults.repay
    kwargs = {"repay_amount" if in_auction else "amount": Decimal("99.9999999999")}
    with pytest.raises(AssertionError, match="min_debt"):
        repay(vault_id=vault, signer="alice", environment=env(20, T0), **kwargs)
    assert p.stable_token.total_supply_of() == 100
    assert p.vaults.get_vault(vault_id=vault, environment=env(20, T0))["debt"] == 100
    if in_auction:
        p.vaults.cure_auction(
            vault_id=vault, repay_amount=100, signer="alice", environment=env(20, T0)
        )
    else:
        p.vaults.close_vault(vault_id=vault, signer="alice", environment=env(20, T0))
    state = p.vaults.get_vault_type(vault_type_id=p.vault_type_id, environment=env(20, T0))
    for key in (
        "live_debt_outstanding",
        "live_normalized_debt_total",
        "live_debt_carry_total",
        "live_principal_outstanding",
        "pending_debt_outstanding",
        "auction_debt_locked",
        "auction_principal_locked",
    ):
        assert state[key] == 0, key
    assert p.stable_token.total_supply_of() == 0


def test_fee_view_projects_only_the_effective_anchored_policy(timed):
    p = timed
    p.vaults.set_vault_type_fee(
        vault_type_id=p.vault_type_id,
        stability_fee_bps=1500,
        signer="governor",
        environment=env(100, T0),
    )
    before = p.vaults.get_vault_type(vault_type_id=p.vault_type_id, environment=env(100, T0))
    assert before["stability_fee_bps"] == 500
    assert before["pending_stability_fee_bps"] == 1500
    anchor(p, 101, FRESH)
    after = p.vaults.get_vault_type(vault_type_id=p.vault_type_id, environment=env(101, FRESH))
    assert after["stability_fee_bps"] == 1500
    assert after["pending_stability_fee_bps"] == 1500


@pytest.mark.parametrize("order", [(0, 1), (1, 0)])
def test_fractional_group_ownership_survives_auction_restore_and_full_close(timed, order):
    p = timed
    p.vaults.set_vault_type_limits(
        vault_type_id=p.vault_type_id, debt_ceiling=1_000_000, min_debt=0, signer="governor"
    )
    # R=2.6: the 2q allocation can leave a signed archived component for q.
    p.vaults.set_vault_type_fee(
        vault_type_id=p.vault_type_id,
        stability_fee_bps=16000,
        signer="governor",
        environment=env(2, T0),
    )
    anchor(p, 3, T0)
    old = open_vault(p, height=10)
    anchor(p, 11, T0)
    owners = ("bob", "carol")
    quantum = Decimal("1e-30")
    amounts = (2 * quantum, quantum)
    ids = [
        p.vaults.create_vault(
            vault_type_id=p.vault_type_id,
            collateral_amount=2 * amount,
            debt_amount=amount,
            signer=who,
            environment=env(100, T0),
        )
        for who, amount in zip(owners, amounts, strict=True)
    ]
    for who in ("alice", *owners):
        p.stable_token.mint(amount=1000, to=who, signer="governor")
        p.stable_token.approve(amount=10000, to="con_vaults", signer=who)
    supply = p.stable_token.total_supply_of()
    fresh = Datetime(2027, 1, 1)
    anchor(p, 101, fresh)
    pure_totals = p.vaults.get_vault_type(
        vault_type_id=p.vault_type_id, environment=env(101, fresh)
    )
    pure_owed = sum(
        Decimal(str(p.vaults.get_vault(vault_id=v, environment=env(101, fresh))["debt"]))
        for v in (old, *ids)
    )
    assert Decimal(str(pure_totals["live_debt_outstanding"])) == pure_owed
    for i in order:
        assert (
            p.vaults.get_vault(vault_id=ids[i], environment=env(101, fresh))["debt"] == amounts[i]
        )
        p.oracle.submit_price(
            asset="COL", price=quantum, signer="governor", environment=env(101, fresh)
        )
        p.vaults.open_liquidation_auction(
            vault_id=ids[i], signer="alice", environment=env(101, fresh)
        )
        assert p.stable_token.total_supply_of() == supply
        ledger = p.vaults.get_vault_type(vault_type_id=p.vault_type_id, environment=env(101, fresh))
        owed = sum(
            Decimal(str(p.vaults.get_vault(vault_id=v, environment=env(101, fresh))["debt"]))
            for v in (old, *ids)
        )
        assert (
            Decimal(str(ledger["live_debt_outstanding"]))
            + Decimal(str(ledger["auction_debt_locked"]))
            == owed
        )
        p.oracle.submit_price(asset="COL", price=2, signer="governor", environment=env(101, fresh))
        p.vaults.cancel_auction_if_safe(
            vault_id=ids[i], signer="alice", environment=env(101, fresh)
        )
        assert p.stable_token.total_supply_of() == supply
    anchor(p, 102, fresh)
    for i in order:
        p.vaults.close_vault(vault_id=ids[i], signer=owners[i], environment=env(102, fresh))
    # Repeated active-debt partial payments preserve exact paid principal and fees.
    for amount in (Decimal("0.1"), Decimal("0.2"), Decimal("19.7")):
        p.vaults.repay(vault_id=old, amount=amount, signer="alice", environment=env(102, fresh))
    p.vaults.close_vault(vault_id=old, signer="alice", environment=env(102, fresh))
    state = p.vaults.get_vault_type(vault_type_id=p.vault_type_id, environment=env(102, fresh))
    for key in (
        "live_normalized_debt_total",
        "live_debt_carry_total",
        "live_debt_outstanding",
        "live_principal_outstanding",
        "pending_debt_outstanding",
        "auction_debt_locked",
        "auction_principal_locked",
        "bad_debt",
    ):
        assert state[key] == 0, (order, key)
    for group_height in (100, 101):
        for group_field in (
            "debt_group_rates",
            "debt_group_remaining",
            "debt_group_shares",
            "debt_group_carry",
        ):
            assert p.client.raw_driver.get(f"con_vaults.{group_field}:1:{group_height}") is None
    assert p.stable_token.total_supply_of() == 3000
    assert (
        sum(
            Decimal(str(p.stable_token.balance_of(address=who)))
            for who in (
                "alice",
                "bob",
                "carol",
                "con_vaults",
                "treasury",
                "con_savings",
                "governor",
            )
        )
        == 3000
    )


def test_auction_restore_keeps_unpaid_fees_distinct_from_principal(timed):
    p = timed
    vault = open_vault(p, height=10)
    anchor(p, 11, T0)
    p.stable_token.mint(amount=1000, to="alice", signer="governor")
    p.stable_token.approve(amount=10000, to="con_vaults", signer="alice")
    p.oracle.submit_price(
        asset="COL", price=Decimal("0.25"), signer="governor", environment=env(100, FRESH)
    )
    p.vaults.open_liquidation_auction(vault_id=vault, signer="bob", environment=env(100, FRESH))
    snapshot = p.vaults.get_auction(vault_id=vault, environment=env(100, FRESH))
    assert snapshot["debt_snapshot"] > snapshot["principal_snapshot"] == 100
    p.oracle.submit_price(asset="COL", price=2, signer="governor", environment=env(100, FRESH))
    p.vaults.cure_auction(
        vault_id=vault, repay_amount=1, signer="alice", environment=env(100, FRESH)
    )
    restored = p.vaults.get_vault(vault_id=vault, environment=env(100, FRESH))
    assert restored["pending_debt"] == snapshot["debt_snapshot"] - 1
    assert restored["pending_principal"] == restored["principal"] == 100
    assert p.stable_token.total_supply_of() == 1100  # Fee payment did not burn principal.
    anchor(p, 101, YEAR_LATER)
    ready = p.vaults.get_vault(vault_id=vault, environment=env(101, YEAR_LATER))
    assert ready["debt"] == restored["pending_debt"]
    p.vaults.close_vault(vault_id=vault, signer="alice", environment=env(101, YEAR_LATER))
    assert p.stable_token.total_supply_of() == 1000
    totals = p.vaults.get_vault_type(
        vault_type_id=p.vault_type_id, environment=env(101, YEAR_LATER)
    )
    for field in (
        "live_normalized_debt_total",
        "live_debt_carry_total",
        "live_debt_outstanding",
        "live_principal_outstanding",
        "pending_debt_outstanding",
        "auction_debt_locked",
        "auction_principal_locked",
    ):
        assert totals[field] == 0


def test_fee_anchor_before_debt_anchor_keeps_old_and_new_rate_intervals(timed):
    p = timed
    old = open_vault(p, height=10)
    anchor(p, 11, T0)
    p.vaults.set_vault_type_fee(
        vault_type_id=p.vault_type_id,
        stability_fee_bps=5000,
        signer="governor",
        environment=env(100, T0),
    )
    new = open_vault(p, who="bob", height=101)
    assert (
        p.clock.process_time_anchors(
            signer="__time_checkpoints__", max_work=1, environment=env(102, FRESH)
        )
        == 1
    )
    # Another vault moves the global base after the fee anchor but before the
    # new debt's own immutable anchor is available.
    p.vaults.withdraw_collateral(
        vault_id=old, amount=1, signer="alice", environment=env(102, FRESH)
    )
    next_day = Datetime(2026, 4, 12)
    anchor(p, 103, next_day)
    assert p.vaults.get_vault(vault_id=new, environment=env(103, next_day))["debt"] == 100
    expected = Decimal(100) * (1 + Decimal("0.05") * 100 / 365) * (1 + Decimal("0.5") / 365)
    actual = p.vaults.get_vault(vault_id=old, environment=env(103, next_day))["debt"]
    assert abs(Decimal(str(actual)) - expected) < Decimal("1e-25")


def test_auction_cure_rejects_excess_payment_before_transferring_custody(timed):
    p = timed
    vault = auction(p, height=20)
    p.stable_token.mint(amount=50, to="alice", signer="governor")
    p.stable_token.approve(amount=150, to="con_vaults", signer="alice")
    before = p.stable_token.balance_of(address="alice")
    with pytest.raises(AssertionError, match="exceeds.*debt"):
        p.vaults.cure_auction(
            vault_id=vault, repay_amount=150, signer="alice", environment=env(20, T0)
        )
    assert p.stable_token.balance_of(address="alice") == before == 150
    assert p.stable_token.balance_of(address="con_vaults") == 0
    assert p.vaults.get_auction(vault_id=vault, environment=env(20, T0))["debt_snapshot"] == 100


def test_mixed_active_fees_and_unanchored_principal_pay_the_correct_bucket(timed):
    p = timed
    vault = open_vault(p, height=10)
    anchor(p, 11, T0)
    p.vaults.borrow(vault_id=vault, amount=50, signer="alice", environment=env(100, FRESH))
    quoted = p.vaults.get_vault(vault_id=vault, environment=env(100, FRESH))
    totals = p.vaults.get_vault_type(vault_type_id=p.vault_type_id, environment=env(100, FRESH))
    assert totals["live_debt_outstanding"] == quoted["debt"]
    assert totals["live_principal_outstanding"] == quoted["principal"] == 150
    p.stable_token.approve(amount=150, to="con_vaults", signer="alice")
    paid = p.vaults.repay(vault_id=vault, amount=1, signer="alice", environment=env(100, FRESH))
    assert paid["fee_paid"] == 1
    assert paid["principal_paid"] == 0
    after = p.vaults.get_vault(vault_id=vault, environment=env(100, FRESH))
    assert after["pending_debt"] == after["pending_principal"] == 50
    assert after["principal"] == 150
    assert after["debt"] == quoted["debt"] - 1
    assert p.stable_token.total_supply_of() == 150
    assert (
        p.vaults.get_auction(vault_id=vault, environment=env(100, FRESH))["auction_end_time"]
        is None
    )


@pytest.mark.parametrize(
    ("minute", "second", "extension", "extended"),
    [(0, 0, 3600, True), (59, 59, 3600, False), (0, 0, 0, False)],
)
def test_bid_extension_window_boundary_and_disabled_policy(
    timed, minute, second, extension, extended
):
    p = timed
    vault = auction(p, height=20)
    anchor(p, 21, T0)
    p.vaults.set_vault_type_auction_config(
        vault_type_id=p.vault_type_id,
        auction_duration_seconds=86400,
        min_bid_increment_bps=500,
        extension_window_seconds=3600,
        bid_extension_seconds=extension,
        signer="governor",
    )
    hour = 23 if minute == 0 else 22
    late = Datetime(2026, 1, 1, hour=hour, minute=minute, second=second)
    fund_bid(p, vault, 100, late)
    if extended:
        assert (
            p.vaults.get_auction(vault_id=vault, environment=env(100, late))["auction_end_time"]
            is None
        )
    anchor(p, 101, FRESH)
    expected = Datetime(2026, 4, 11, hour=1) if extended else Datetime(2026, 1, 2)
    assert (
        p.vaults.get_auction(vault_id=vault, environment=env(101, FRESH))["auction_end_time"]
        == expected
    )


def test_subunit_unanchored_repayment_removes_exact_owed_principal(timed):
    p = timed
    p.vaults.set_vault_type_limits(
        vault_type_id=p.vault_type_id, debt_ceiling=1_000_000, min_debt=0, signer="governor"
    )
    q = Decimal("1e-30")
    vault = p.vaults.create_vault(
        vault_type_id=p.vault_type_id,
        collateral_amount=4 * q,
        debt_amount=2 * q,
        signer="alice",
        environment=env(100, T0),
    )
    p.stable_token.approve(amount=2 * q, to="con_vaults", signer="alice")
    p.vaults.repay(vault_id=vault, amount=q, signer="alice", environment=env(100, T0))
    record = p.vaults.get_vault(vault_id=vault, environment=env(100, T0))
    assert (
        record["debt"]
        == record["principal"]
        == record["pending_debt"]
        == record["pending_principal"]
        == q
    )
    assert p.stable_token.total_supply_of() == q
    p.vaults.close_vault(vault_id=vault, signer="alice", environment=env(100, T0))
    assert p.stable_token.total_supply_of() == 0


@pytest.mark.parametrize(("window", "microsecond", "extended"), [(0, 500000, False), (1, 0, True)])
def test_zero_and_one_second_auction_extension_policy(timed, window, microsecond, extended):
    p = timed
    vault = auction(p, height=20)
    anchor(p, 21, T0)
    p.vaults.set_vault_type_auction_config(
        vault_type_id=p.vault_type_id,
        auction_duration_seconds=86400,
        min_bid_increment_bps=500,
        extension_window_seconds=window,
        bid_extension_seconds=1,
        signer="governor",
    )
    late = Datetime(2026, 1, 1, hour=23, minute=59, second=59, microsecond=microsecond)
    fund_bid(p, vault, 100, late)
    anchor(p, 101, FRESH)
    expected = Datetime(2026, 4, 11, second=1) if extended else Datetime(2026, 1, 2)
    assert (
        p.vaults.get_auction(vault_id=vault, environment=env(101, FRESH))["auction_end_time"]
        == expected
    )
