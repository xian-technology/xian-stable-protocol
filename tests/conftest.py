from pathlib import Path
from types import SimpleNamespace

import pytest
from contracting.client import ContractingClient


ROOT = Path(__file__).resolve().parents[1]
CONTRACTS_DIR = ROOT / "contracts"


def submit_contract(client: ContractingClient, name: str, file_name: str, constructor_args=None):
    source = (CONTRACTS_DIR / file_name).read_text(encoding="utf-8")
    client.submit(source, name=name, constructor_args=constructor_args or {})
    return client.get_contract(name)


@pytest.fixture
def protocol(tmp_path):
    storage_home = tmp_path / "xian"
    storage_home.mkdir(parents=True, exist_ok=True)

    client = ContractingClient(storage_home=storage_home)
    client.flush()

    stable_token = submit_contract(
        client,
        "stable_token",
        "stable_token.s.py",
        {
            "token_name": "Xian Dollar",
            "token_symbol": "xUSD",
            "initial_supply": 0,
            "initial_holder": "vaults",
            "governor_address": "governor",
        },
    )
    collateral_token = submit_contract(
        client,
        "collateral_token",
        "stable_token.s.py",
        {
            "token_name": "Collateral Token",
            "token_symbol": "COL",
            "initial_supply": 1_000_000,
            "initial_holder": "sys",
            "governor_address": "governor",
        },
    )
    oracle = submit_contract(
        client,
        "oracle",
        "oracle.s.py",
        {"governor_address": "governor"},
    )
    savings = submit_contract(
        client,
        "savings",
        "savings.s.py",
        {
            "stable_token_contract_name": "stable_token",
            "governor_address": "governor",
        },
    )
    vaults = submit_contract(
        client,
        "vaults",
        "vaults.s.py",
        {
            "stable_token_contract_name": "stable_token",
            "oracle_contract_name": "oracle",
            "governor_address": "governor",
            "savings_contract_name": "savings",
            "treasury_address_value": "treasury",
        },
    )

    stable_token.set_controller(account="vaults", enabled=True, signer="governor")
    stable_token.set_controller(account="governor", enabled=True, signer="governor")
    oracle.set_price(asset="COL", price=2, signer="governor")

    vault_type_id = vaults.add_vault_type(
        collateral_contract_name="collateral_token",
        oracle_key="COL",
        min_collateral_ratio_bps=15000,
        liquidation_ratio_bps=13000,
        liquidation_bonus_bps=500,
        debt_ceiling=1_000_000,
        min_debt=10,
        stability_fee_bps=500,
        auction_duration_seconds=86400,
        signer="governor",
    )

    collateral_token.transfer(to="alice", amount=1_000)
    collateral_token.transfer(to="bob", amount=1_000)
    collateral_token.transfer(to="carol", amount=1_000)

    collateral_token.approve(to="vaults", amount=1_000, signer="alice")
    collateral_token.approve(to="vaults", amount=1_000, signer="bob")
    collateral_token.approve(to="vaults", amount=1_000, signer="carol")

    return SimpleNamespace(
        client=client,
        stable_token=stable_token,
        collateral_token=collateral_token,
        oracle=oracle,
        savings=savings,
        vaults=vaults,
        vault_type_id=vault_type_id,
    )
