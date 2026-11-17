from decimal import Decimal
from random import Random

import pytest
from xian_runtime_types.time import Datetime

TRACKED_ACCOUNTS = (
    "alice",
    "bob",
    "carol",
    "con_vaults",
    "con_psm",
    "con_savings",
    "treasury",
    "governor",
)


def _balance(token, address: str) -> float:
    return float(token.balance_of(address=address))


def _assert_stable_supply_is_accounted(protocol) -> None:
    balances = sum(_balance(protocol.stable_token, account) for account in TRACKED_ACCOUNTS)
    assert float(protocol.stable_token.total_supply_of()) == pytest.approx(balances)


def _assert_psm_reserves_are_accounted(protocol, expected_total_reserve: float) -> None:
    psm_state = protocol.psm.get_state()
    reserve_balances = sum(
        _balance(protocol.reserve_token, account) for account in TRACKED_ACCOUNTS
    )

    assert float(psm_state["reserve_balance"]) == pytest.approx(
        _balance(protocol.reserve_token, "con_psm")
    )
    assert reserve_balances == pytest.approx(expected_total_reserve)
    assert _balance(protocol.reserve_token, "con_psm") >= 0
    assert _balance(protocol.reserve_token, "treasury") >= 0


def _assert_vault_accounting(protocol, vault_ids: list[int]) -> None:
    vault_type = protocol.vaults.get_vault_type(vault_type_id=protocol.vault_type_id)
    live_principal = 0.0
    live_debt = 0.0
    min_ratio = float(vault_type["min_collateral_ratio_bps"])

    for vault_id in vault_ids:
        vault = protocol.vaults.get_vault(vault_id=vault_id)
        assert vault["open"] is True
        assert vault["auction_open"] is False
        assert float(vault["collateral_amount"]) >= 0
        assert float(vault["principal"]) >= 0
        assert float(vault["debt"]) >= 0
        assert float(vault["collateralization_bps"]) >= min_ratio

        live_principal += float(vault["principal"])
        live_debt += float(vault["debt"])

    assert float(vault_type["live_principal_outstanding"]) == pytest.approx(live_principal)
    assert float(vault_type["live_debt_outstanding"]) == pytest.approx(live_debt)


def _try_vault_change(method, vault_id, amount, owner):
    try:
        method(vault_id=vault_id, amount=amount, signer=owner)
    except AssertionError:
        pass


def test_psm_deterministic_operation_sequence_preserves_accounting(protocol):
    rng = Random(1729)
    expected_total_reserve = sum(
        _balance(protocol.reserve_token, account) for account in TRACKED_ACCOUNTS
    )

    protocol.reserve_token.approve(amount=1_000, to="con_psm", signer="alice")

    for _ in range(40):
        mint_amount = rng.randint(1, 35)
        if _balance(protocol.reserve_token, "alice") >= mint_amount:
            protocol.psm.mint_stable(
                reserve_amount=mint_amount,
                signer="alice",
            )

        stable_balance = _balance(protocol.stable_token, "alice")
        if stable_balance > 2 and _balance(protocol.reserve_token, "con_psm") > 2:
            redeem_amount = min(stable_balance, rng.randint(1, int(stable_balance)))
            protocol.stable_token.approve(
                amount=redeem_amount,
                to="con_psm",
                signer="alice",
            )
            protocol.psm.redeem_stable(
                stable_amount=redeem_amount,
                signer="alice",
            )

        _assert_stable_supply_is_accounted(protocol)
        _assert_psm_reserves_are_accounted(protocol, expected_total_reserve)


def test_vault_deterministic_operation_sequence_preserves_accounting(protocol):
    rng = Random(2718)
    vault_ids: list[int] = []
    when = Datetime(year=2026, month=1, day=1)
    protocol.step(10, when)

    for owner in ("alice", "bob", "carol"):
        protocol.stable_token.approve(amount=10_000, to="con_vaults", signer=owner)
        vault_ids.append(
            protocol.vaults.create_vault(
                vault_type_id=protocol.vault_type_id,
                collateral_amount=rng.randint(80, 140),
                debt_amount=rng.randint(50, 90),
                signer=owner,
            )
        )

    for index in range(45):
        protocol.step(11 + index, when)
        vault_id = vault_ids[index % len(vault_ids)]
        vault = protocol.vaults.get_vault(vault_id=vault_id)
        owner = vault["owner"]
        action = rng.choice(("deposit", "withdraw", "borrow", "repay"))

        if action == "deposit":
            protocol.vaults.deposit_collateral(
                vault_id=vault_id,
                amount=rng.randint(1, 15),
                signer=owner,
            )
        elif action == "withdraw":
            withdraw_amount = rng.randint(1, 6)
            _try_vault_change(protocol.vaults.withdraw_collateral, vault_id, withdraw_amount, owner)
        elif action == "borrow":
            _try_vault_change(protocol.vaults.borrow, vault_id, rng.randint(1, 8), owner)
        else:
            principal = float(vault["principal"])
            if principal > 12 and _balance(protocol.stable_token, owner) > 1:
                repay_amount = min(rng.randint(1, 8), principal - 10)
                protocol.vaults.repay(
                    vault_id=vault_id,
                    amount=repay_amount,
                    signer=owner,
                )

        _assert_vault_accounting(protocol, vault_ids)
        _assert_stable_supply_is_accounted(protocol)


@pytest.mark.parametrize(
    ("end_time", "elapsed_seconds"),
    (
        (Datetime(year=2026, month=1, day=2), 86_400),
        (Datetime(year=2026, month=2, day=1), 31 * 86_400),
        (Datetime(year=2026, month=7, day=1), 181 * 86_400),
        (Datetime(year=2027, month=1, day=1), 365 * 86_400),
    ),
)
def test_fee_accrual_routes_and_accounts_for_every_minted_token(
    protocol,
    end_time,
    elapsed_seconds,
):
    principal = 100
    start = protocol.step(10, Datetime(year=2026, month=1, day=1))
    saved = protocol.seed_saver()
    vault_id = protocol.vaults.create_vault(
        vault_type_id=protocol.vault_type_id,
        collateral_amount=100,
        debt_amount=principal,
        signer="alice",
        environment=start,
    )
    protocol.step(11, start["now"])
    expected_fee = principal * 500 / 10_000 * elapsed_seconds / (365 * 86_400)

    # Six tokens cover the largest fee in these scenarios (five tokens).
    protocol.stable_token.mint(amount=6, to="alice", signer="governor")
    protocol.stable_token.approve(
        amount=principal + 6,
        to="con_vaults",
        signer="alice",
    )
    end = protocol.step(1000, end_time)
    protocol.vaults.close_vault(
        vault_id=vault_id,
        signer="alice",
        environment=end,
    )

    vault_type = protocol.vaults.get_vault_type(vault_type_id=protocol.vault_type_id)
    assert float(protocol.savings.total_assets() - saved) == pytest.approx(expected_fee * 0.8)
    assert float(vault_type["surplus_buffer"]) == pytest.approx(expected_fee * 0.2)
    assert float(vault_type["live_principal_outstanding"]) == pytest.approx(0)
    assert float(vault_type["live_debt_outstanding"]) == pytest.approx(0)
    _assert_stable_supply_is_accounted(protocol)


@pytest.mark.parametrize("seed", range(8))
def test_auction_settlement_fuzz_preserves_debt_and_supply_accounting(
    protocol,
    seed,
):
    rng = Random(seed)
    # Opening bids must cover the reserve: 100 COL at 0.5 less the 5% bonus.
    winning_bid = rng.randint(48, 150)
    start = protocol.step(10, Datetime(year=2026, month=1, day=1))

    vault_id = protocol.vaults.create_vault(
        vault_type_id=protocol.vault_type_id,
        collateral_amount=100,
        debt_amount=100,
        signer="alice",
        environment=start,
    )
    protocol.oracle.submit_price(asset="COL", price=Decimal("0.5"), signer="governor")
    protocol.stable_token.mint(amount=winning_bid, to="bob", signer="governor")
    protocol.stable_token.approve(
        amount=winning_bid,
        to="con_vaults",
        signer="bob",
    )
    protocol.vaults.open_liquidation_auction(
        vault_id=vault_id,
        signer="carol",
        environment=start,
    )
    protocol.vaults.bid(
        vault_id=vault_id,
        bid_amount=winning_bid,
        signer="bob",
        environment=start,
    )
    protocol.step(11, start["now"])
    supply_before_settlement = float(protocol.stable_token.total_supply_of())

    end = protocol.step(1000, Datetime(year=2026, month=1, day=2, second=1))
    settlement = protocol.vaults.settle_auction(
        vault_id=vault_id,
        signer="carol",
        environment=end,
    )
    vault_type = protocol.vaults.get_vault_type(vault_type_id=protocol.vault_type_id)

    principal_paid = min(winning_bid, 100)
    assert float(settlement["bad_debt"]) == pytest.approx(max(100 - winning_bid, 0))
    assert float(vault_type["bad_debt"]) == pytest.approx(max(100 - winning_bid, 0))
    assert float(vault_type["auction_debt_locked"]) == pytest.approx(0)
    assert float(vault_type["auction_principal_locked"]) == pytest.approx(0)
    assert float(protocol.stable_token.total_supply_of()) == pytest.approx(
        supply_before_settlement - principal_paid
    )
    assert float(protocol.stable_token.balance_of(address="con_vaults")) == pytest.approx(0)
    assert float(protocol.collateral_token.balance_of(address="bob")) == pytest.approx(1_100)
    _assert_stable_supply_is_accounted(protocol)
