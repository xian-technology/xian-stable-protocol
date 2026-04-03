from pathlib import Path
from types import SimpleNamespace

import pytest
from contracting.client import ContractingClient


ROOT = Path(__file__).resolve().parents[1]
CONTRACTS_DIR = ROOT / "contracts"


def submit_contract(
    client: ContractingClient,
    name: str,
    file_name: str,
    constructor_args=None,
):
    source = (CONTRACTS_DIR / file_name).read_text(encoding="utf-8")
    client.submit(source, name=name, constructor_args=constructor_args or {})
    return client.get_contract(name)


@pytest.fixture
def protocol(tmp_path):
    storage_home = tmp_path / "xian"
    storage_home.mkdir(parents=True, exist_ok=True)

    client = ContractingClient(storage_home=storage_home)
    client.flush()

    committee = submit_contract(
        client,
        "committee",
        "committee.s.py",
        {
            "initial_members": ["alice", "bob", "carol"],
            "initial_weights": {
                "alice": 2,
                "bob": 1,
                "carol": 1,
            },
            "governor_address": "governor",
        },
    )
    protocol_governance = submit_contract(
        client,
        "protocol_governance",
        "protocol_governance.s.py",
        {
            "membership_contract_name": "committee",
            "approval_threshold_numerator": 2,
            "approval_threshold_denominator": 3,
            "proposal_expiry_days": 7,
            "execution_delay_seconds": 86400,
            "emergency_execution_delay_seconds": 3600,
        },
    )
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
    reserve_token = submit_contract(
        client,
        "reserve_token",
        "stable_token.s.py",
        {
            "token_name": "Reserve Dollar",
            "token_symbol": "rUSD",
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
    psm = submit_contract(
        client,
        "psm",
        "psm.s.py",
        {
            "stable_token_contract_name": "stable_token",
            "reserve_token_contract_name": "reserve_token",
            "governor_address": "governor",
            "treasury_address_value": "treasury",
            "mint_fee_bps_value": 100,
            "redeem_fee_bps_value": 50,
        },
    )

    stable_token.set_controller(account="vaults", enabled=True, signer="governor")
    stable_token.set_controller(account="governor", enabled=True, signer="governor")
    stable_token.set_controller(account="psm", enabled=True, signer="governor")
    reserve_token.set_controller(account="governor", enabled=True, signer="governor")

    oracle.set_asset_config(
        asset="COL",
        min_reporters_required=1,
        max_price_age_seconds=0,
        signer="governor",
    )
    oracle.submit_price(asset="COL", price=2, signer="governor")

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
        partial_liquidation_target_ratio_bps=15000,
        surplus_buffer_bps=2000,
        min_bid_increment_bps=500,
        extension_window_seconds=3600,
        bid_extension_seconds=3600,
        signer="governor",
    )

    for account in ("alice", "bob", "carol"):
        collateral_token.transfer(to=account, amount=1_000)
        collateral_token.approve(to="vaults", amount=1_000, signer=account)
        reserve_token.transfer(to=account, amount=1_000)

    return SimpleNamespace(
        client=client,
        committee=committee,
        protocol_governance=protocol_governance,
        stable_token=stable_token,
        collateral_token=collateral_token,
        reserve_token=reserve_token,
        oracle=oracle,
        savings=savings,
        vaults=vaults,
        psm=psm,
        vault_type_id=vault_type_id,
    )
