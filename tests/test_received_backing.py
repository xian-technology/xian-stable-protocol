from pathlib import Path

import pytest

TAXED_TOKEN = """
balances = Hash(default_value=0)
approvals = Hash(default_value=0)
fee_bps = Variable()

@construct
def seed():
    balances["alice"] = 1000
    fee_bps.set(0)

@export
def set_fee(value: int):
    assert ctx.caller == "sys"
    fee_bps.set(value)

@export
def balance_of(address: str):
    return balances[address]

@export
def approve(amount: decimal, to: str):
    approvals[ctx.caller, to] = amount

@export
def transfer(amount: decimal, to: str):
    assert amount > 0 and balances[ctx.caller] >= amount
    balances[ctx.caller] -= amount
    balances[to] += amount

@export
def transfer_from(amount: decimal, to: str, main_account: str):
    assert amount > 0 and balances[main_account] >= amount
    assert approvals[main_account, ctx.caller] >= amount
    approvals[main_account, ctx.caller] -= amount
    balances[main_account] -= amount
    balances[to] += amount * (10000 - fee_bps.get()) / 10000
"""


@pytest.fixture
def taxed_token(protocol):
    protocol.client.submit(TAXED_TOKEN, name="con_taxed")
    return protocol.client.get_contract_proxy("con_taxed")


@pytest.mark.parametrize("fee_bps", [5000, 10000])
@pytest.mark.parametrize("existing_reserves", [0, 200])
def test_psm_cannot_mint_against_reserves_it_did_not_receive(
    protocol, taxed_token, fee_bps, existing_reserves
):
    source = (Path(__file__).absolute().parents[1] / "contracts" / "con_psm.s.py").read_text()
    protocol.client.submit(
        source,
        name="con_tax_psm",
        constructor_args={
            "stable_token_contract_name": "con_stable_token",
            "reserve_token_contract_name": "con_taxed",
            "governor_address": "governor",
        },
    )
    psm = protocol.client.get_contract_proxy("con_tax_psm")
    protocol.stable_token.set_controller(account="con_tax_psm", enabled=True, signer="governor")
    if existing_reserves:
        taxed_token.transfer(amount=existing_reserves, to="con_tax_psm", signer="alice")
    taxed_token.set_fee(value=fee_bps, signer="sys")
    taxed_token.approve(amount=100, to="con_tax_psm", signer="alice")

    with pytest.raises(AssertionError, match="exact reserve transfer"):
        psm.mint_stable(reserve_amount=100, signer="alice")

    assert protocol.stable_token.total_supply_of() == 0
    assert taxed_token.balance_of(address="con_tax_psm") == existing_reserves
    assert taxed_token.balance_of(address="alice") == 1000 - existing_reserves


@pytest.fixture
def taxed_vault_type(protocol, taxed_token):
    return protocol.vaults.add_vault_type(
        collateral_contract_name="con_taxed",
        oracle_key="COL",
        min_collateral_ratio_bps=15000,
        liquidation_ratio_bps=13000,
        liquidation_bonus_bps=500,
        debt_ceiling=10000,
        min_debt=10,
        stability_fee_bps=0,
        auction_duration_seconds=86400,
        signer="governor",
    )


@pytest.mark.parametrize("fee_bps", [5000, 10000])
def test_vault_cannot_credit_unreceived_collateral_when_opening(
    protocol, taxed_token, taxed_vault_type, fee_bps
):
    taxed_token.set_fee(value=fee_bps, signer="sys")
    taxed_token.approve(amount=100, to="con_vaults", signer="alice")
    with pytest.raises(AssertionError, match="exact collateral transfer"):
        protocol.vaults.create_vault(
            vault_type_id=taxed_vault_type, collateral_amount=100, debt_amount=100, signer="alice"
        )
    assert protocol.stable_token.total_supply_of() == 0
    assert taxed_token.balance_of(address="con_vaults") == 0
    assert taxed_token.balance_of(address="alice") == 1000


@pytest.mark.parametrize("fee_bps", [5000, 10000])
def test_vault_cannot_credit_unreceived_collateral_on_later_deposits(
    protocol, taxed_token, taxed_vault_type, fee_bps
):
    taxed_token.approve(amount=200, to="con_vaults", signer="alice")
    vault_id = protocol.vaults.create_vault(
        vault_type_id=taxed_vault_type, collateral_amount=100, debt_amount=100, signer="alice"
    )
    taxed_token.set_fee(value=fee_bps, signer="sys")
    with pytest.raises(AssertionError, match="exact collateral transfer"):
        protocol.vaults.deposit_collateral(vault_id=vault_id, amount=100, signer="alice")
    assert protocol.vaults.get_vault(vault_id=vault_id)["collateral_amount"] == 100
    assert taxed_token.balance_of(address="con_vaults") == 100
    assert taxed_token.balance_of(address="alice") == 900
