from random import Random

import pytest

TRACKED_ACCOUNTS = (
    "alice",
    "bob",
    "carol",
    "vaults",
    "psm",
    "savings",
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
    reserve_balances = sum(_balance(protocol.reserve_token, account) for account in TRACKED_ACCOUNTS)

    assert float(psm_state["reserve_balance"]) == pytest.approx(
        _balance(protocol.reserve_token, "psm")
    )
    assert reserve_balances == pytest.approx(expected_total_reserve)
    assert _balance(protocol.reserve_token, "psm") >= 0
    assert _balance(protocol.reserve_token, "treasury") >= 0


def _assert_vault_accounting(protocol, vault_ids: list[int]) -> None:
    vault_type = protocol.vaults.get_vault_type(
        vault_type_id=protocol.vault_type_id
    )
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

    assert float(vault_type["live_principal_outstanding"]) == pytest.approx(
        live_principal
    )
    assert float(vault_type["live_debt_outstanding"]) == pytest.approx(live_debt)


def test_psm_deterministic_operation_sequence_preserves_accounting(protocol):
    rng = Random(1729)
    expected_total_reserve = sum(
        _balance(protocol.reserve_token, account) for account in TRACKED_ACCOUNTS
    )

    protocol.reserve_token.approve(amount=1_000, to="psm", signer="alice")

    for _ in range(40):
        mint_amount = rng.randint(1, 35)
        if _balance(protocol.reserve_token, "alice") >= mint_amount:
            protocol.psm.mint_stable(
                reserve_amount=mint_amount,
                signer="alice",
            )

        stable_balance = _balance(protocol.stable_token, "alice")
        if stable_balance > 2 and _balance(protocol.reserve_token, "psm") > 2:
            redeem_amount = min(stable_balance, rng.randint(1, int(stable_balance)))
            protocol.stable_token.approve(
                amount=redeem_amount,
                to="psm",
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

    for owner in ("alice", "bob", "carol"):
        protocol.stable_token.approve(amount=10_000, to="vaults", signer=owner)
        vault_ids.append(
            protocol.vaults.create_vault(
                vault_type_id=protocol.vault_type_id,
                collateral_amount=rng.randint(80, 140),
                debt_amount=rng.randint(50, 90),
                signer=owner,
            )
        )

    for index in range(45):
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
            try:
                protocol.vaults.withdraw_collateral(
                    vault_id=vault_id,
                    amount=withdraw_amount,
                    signer=owner,
                )
            except AssertionError:
                pass
        elif action == "borrow":
            try:
                protocol.vaults.borrow(
                    vault_id=vault_id,
                    amount=rng.randint(1, 8),
                    signer=owner,
                )
            except AssertionError:
                pass
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
