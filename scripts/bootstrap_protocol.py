from __future__ import annotations

import argparse
import inspect
import json
import os
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from xian_py import RetryPolicy, Wallet, Xian, XianClientConfig
from xian_py.models import TransactionSubmission

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS_DIR = ROOT / "contracts"
DEFAULT_GOVERNANCE_CONTRACT = "governance"
DEFAULT_MEMBERSHIP_CONTRACT = "masternodes"
DEFAULT_STABLE_TOKEN_CONTRACT = "con_stable_token"
DEFAULT_ORACLE_CONTRACT = "con_oracle"
DEFAULT_SAVINGS_CONTRACT = "con_savings"
DEFAULT_VAULTS_CONTRACT = "con_vaults"
DEFAULT_PSM_CONTRACT = "con_psm"
DEFAULT_COLLATERAL_CONTRACT = "con_collateral_token"
DEFAULT_RESERVE_CONTRACT = "con_reserve_token"


@dataclass(frozen=True)
class BootstrapConfig:
    node_url: str
    chain_id: str | None
    operator_address: str
    governor_address: str
    treasury_address: str
    governance_contract_name: str
    membership_contract_name: str
    stable_token_name: str
    stable_token_symbol: str
    stable_token_contract_name: str
    oracle_contract_name: str
    savings_contract_name: str
    vaults_contract_name: str
    psm_contract_name: str
    collateral_contract_name: str
    reserve_contract_name: str
    collateral_token_name: str
    collateral_token_symbol: str
    reserve_token_name: str
    reserve_token_symbol: str
    sample_token_supply: int | Decimal
    asset_key: str
    asset_price: int | Decimal
    min_reporters_required: int
    max_price_age_seconds: int
    oracle_reporters: list[str]
    min_collateral_ratio_bps: int
    liquidation_ratio_bps: int
    liquidation_bonus_bps: int
    partial_liquidation_target_ratio_bps: int
    debt_ceiling: int | Decimal
    min_debt: int | Decimal
    stability_fee_bps: int
    auction_duration_seconds: int
    surplus_buffer_bps: int
    min_bid_increment_bps: int
    extension_window_seconds: int
    bid_extension_seconds: int
    mint_fee_bps: int
    redeem_fee_bps: int
    deploy_chi: int
    tx_chi: int


def _env_str(name: str, default: str) -> str:
    value = os.environ.get(name)
    if value is None:
        return default
    normalized = value.strip()
    return normalized if normalized else default


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    return int(value)


def _parse_numeric(value: str) -> int | Decimal:
    normalized = value.strip()
    if not normalized:
        raise ValueError("numeric value must not be empty")
    try:
        return int(normalized)
    except ValueError:
        return Decimal(normalized)


def _env_numeric(name: str, default: int | Decimal) -> int | Decimal:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    return _parse_numeric(value)


def _env_list(name: str, default: list[str]) -> list[str]:
    value = os.environ.get(name)
    if value is None:
        return default
    items = [item.strip() for item in value.split(",")]
    filtered = [item for item in items if item]
    return filtered or default


def _require_wallet() -> Wallet:
    private_key = os.environ.get("XIAN_WALLET_PRIVATE_KEY")
    if not private_key:
        raise RuntimeError(
            "XIAN_WALLET_PRIVATE_KEY is required to bootstrap the protocol."
        )
    return Wallet(private_key=private_key)


def _contract_source(file_name: str) -> str:
    return (CONTRACTS_DIR / file_name).read_text(encoding="utf-8")


def _require_user_contract_name(label: str, value: str) -> None:
    if value.startswith("con_"):
        return
    raise RuntimeError(
        f"{label} must start with 'con_' on current Xian networks; got "
        f"{value!r}."
    )


def _ensure_submission_succeeded(
    submission: TransactionSubmission, action: str
) -> TransactionSubmission:
    if not submission.submitted:
        raise RuntimeError(f"{action} was not submitted: {submission.message}")
    if submission.accepted is False:
        raise RuntimeError(f"{action} was rejected: {submission.message}")
    if not submission.finalized:
        raise RuntimeError(f"{action} was not finalized: {submission.message}")
    if submission.receipt is not None and not submission.receipt.success:
        raise RuntimeError(f"{action} failed: {submission.receipt.message}")
    return submission


def _budget_kwargs(callable_obj: Any, value: int) -> dict[str, int]:
    parameters = inspect.signature(callable_obj).parameters
    if "chi" in parameters:
        return {"chi": value}
    raise RuntimeError("write method does not expose chi parameter")


def _bool_state(
    client: Xian,
    contract_name: str,
    variable: str,
    *keys: object,
) -> bool:
    value = client.get_state(contract_name, variable, *keys)
    return value is True


def _send(
    contract: Any,
    function: str,
    action: str,
    *,
    chi: int,
    **kwargs: Any,
) -> str:
    result = _ensure_submission_succeeded(
        contract.send(
            function,
            **_budget_kwargs(contract.send, chi),
            mode="checktx",
            wait_for_tx=True,
            **kwargs,
        ),
        action,
    )
    return result.tx_hash or ""


def _load_config(wallet: Wallet) -> BootstrapConfig:
    operator_address = wallet.public_key
    governor_address = _env_str("XIAN_STABLE_GOVERNOR", operator_address)
    treasury_address = _env_str("XIAN_STABLE_TREASURY", operator_address)
    oracle_reporters = _env_list(
        "XIAN_STABLE_ORACLE_REPORTERS", [operator_address]
    )
    return BootstrapConfig(
        node_url=_env_str("XIAN_NODE_URL", "http://127.0.0.1:26657"),
        chain_id=os.environ.get("XIAN_CHAIN_ID"),
        operator_address=operator_address,
        governor_address=governor_address,
        treasury_address=treasury_address,
        governance_contract_name=_env_str(
            "XIAN_STABLE_GOVERNANCE_CONTRACT",
            DEFAULT_GOVERNANCE_CONTRACT,
        ),
        membership_contract_name=_env_str(
            "XIAN_STABLE_MEMBERSHIP_CONTRACT",
            DEFAULT_MEMBERSHIP_CONTRACT,
        ),
        stable_token_name=_env_str(
            "XIAN_STABLE_TOKEN_NAME", "Xian Dollar"
        ),
        stable_token_symbol=_env_str("XIAN_STABLE_TOKEN_SYMBOL", "xUSD"),
        stable_token_contract_name=_env_str(
            "XIAN_STABLE_TOKEN_CONTRACT",
            DEFAULT_STABLE_TOKEN_CONTRACT,
        ),
        oracle_contract_name=_env_str(
            "XIAN_STABLE_ORACLE_CONTRACT",
            DEFAULT_ORACLE_CONTRACT,
        ),
        savings_contract_name=_env_str(
            "XIAN_STABLE_SAVINGS_CONTRACT",
            DEFAULT_SAVINGS_CONTRACT,
        ),
        vaults_contract_name=_env_str(
            "XIAN_STABLE_VAULTS_CONTRACT",
            DEFAULT_VAULTS_CONTRACT,
        ),
        psm_contract_name=_env_str(
            "XIAN_STABLE_PSM_CONTRACT",
            DEFAULT_PSM_CONTRACT,
        ),
        collateral_contract_name=_env_str(
            "XIAN_STABLE_COLLATERAL_CONTRACT",
            DEFAULT_COLLATERAL_CONTRACT,
        ),
        reserve_contract_name=_env_str(
            "XIAN_STABLE_RESERVE_CONTRACT",
            DEFAULT_RESERVE_CONTRACT,
        ),
        collateral_token_name=_env_str(
            "XIAN_STABLE_COLLATERAL_NAME", "Collateral Token"
        ),
        collateral_token_symbol=_env_str(
            "XIAN_STABLE_COLLATERAL_SYMBOL", "COL"
        ),
        reserve_token_name=_env_str(
            "XIAN_STABLE_RESERVE_NAME", "Reserve Dollar"
        ),
        reserve_token_symbol=_env_str(
            "XIAN_STABLE_RESERVE_SYMBOL", "rUSD"
        ),
        sample_token_supply=_env_numeric(
            "XIAN_STABLE_SAMPLE_TOKEN_SUPPLY", 1_000_000
        ),
        asset_key=_env_str("XIAN_STABLE_ASSET_KEY", "COL"),
        asset_price=_env_numeric("XIAN_STABLE_ASSET_PRICE", 2),
        min_reporters_required=_env_int(
            "XIAN_STABLE_MIN_REPORTERS_REQUIRED", 1
        ),
        max_price_age_seconds=_env_int(
            "XIAN_STABLE_MAX_PRICE_AGE_SECONDS", 3600
        ),
        oracle_reporters=oracle_reporters,
        min_collateral_ratio_bps=_env_int(
            "XIAN_STABLE_MIN_COLLATERAL_RATIO_BPS", 15000
        ),
        liquidation_ratio_bps=_env_int(
            "XIAN_STABLE_LIQUIDATION_RATIO_BPS", 13000
        ),
        liquidation_bonus_bps=_env_int(
            "XIAN_STABLE_LIQUIDATION_BONUS_BPS", 500
        ),
        partial_liquidation_target_ratio_bps=_env_int(
            "XIAN_STABLE_PARTIAL_TARGET_RATIO_BPS", 15000
        ),
        debt_ceiling=_env_numeric("XIAN_STABLE_DEBT_CEILING", 1_000_000),
        min_debt=_env_numeric("XIAN_STABLE_MIN_DEBT", 10),
        stability_fee_bps=_env_int("XIAN_STABLE_STABILITY_FEE_BPS", 500),
        auction_duration_seconds=_env_int(
            "XIAN_STABLE_AUCTION_DURATION_SECONDS", 86400
        ),
        surplus_buffer_bps=_env_int(
            "XIAN_STABLE_SURPLUS_BUFFER_BPS", 2000
        ),
        min_bid_increment_bps=_env_int(
            "XIAN_STABLE_MIN_BID_INCREMENT_BPS", 500
        ),
        extension_window_seconds=_env_int(
            "XIAN_STABLE_EXTENSION_WINDOW_SECONDS", 3600
        ),
        bid_extension_seconds=_env_int(
            "XIAN_STABLE_BID_EXTENSION_SECONDS", 3600
        ),
        mint_fee_bps=_env_int("XIAN_STABLE_PSM_MINT_FEE_BPS", 100),
        redeem_fee_bps=_env_int("XIAN_STABLE_PSM_REDEEM_FEE_BPS", 50),
        deploy_chi=_env_int("XIAN_STABLE_DEPLOY_CHI", 500_000),
        tx_chi=_env_int("XIAN_STABLE_TX_CHI", 200_000),
    )


def _validate_config(
    config: BootstrapConfig,
    *,
    skip_sample_tokens: bool,
) -> None:
    for label, name in (
        ("XIAN_STABLE_TOKEN_CONTRACT", config.stable_token_contract_name),
        ("XIAN_STABLE_ORACLE_CONTRACT", config.oracle_contract_name),
        ("XIAN_STABLE_SAVINGS_CONTRACT", config.savings_contract_name),
        ("XIAN_STABLE_VAULTS_CONTRACT", config.vaults_contract_name),
        ("XIAN_STABLE_PSM_CONTRACT", config.psm_contract_name),
    ):
        _require_user_contract_name(label, name)
    if skip_sample_tokens:
        return
    for label, name in (
        (
            "XIAN_STABLE_COLLATERAL_CONTRACT",
            config.collateral_contract_name,
        ),
        (
            "XIAN_STABLE_RESERVE_CONTRACT",
            config.reserve_contract_name,
        ),
    ):
        _require_user_contract_name(label, name)


def _deploy_contract(
    client: Xian,
    *,
    name: str,
    source_file: str,
    args: dict[str, Any],
    chi: int,
) -> tuple[Any, bool]:
    existing_source = client.get_contract(name)
    if existing_source is None:
        result = _ensure_submission_succeeded(
            client.submit_contract(
                name=name,
                code=_contract_source(source_file),
                args=args,
                **_budget_kwargs(client.submit_contract, chi),
                mode="checktx",
                wait_for_tx=True,
            ),
            f"deploy {name}",
        )
        print(f"Deployed {name}: {result.tx_hash}")
        return client.contract(name), True
    print(f"{name} already exists; skipping deployment.")
    return client.contract(name), False


def _ensure_chain_governance(client: Xian, config: BootstrapConfig) -> None:
    for contract_name in (
        config.membership_contract_name,
        config.governance_contract_name,
    ):
        if client.get_contract(contract_name) is None:
            raise RuntimeError(
                f"Required chain contract '{contract_name}' is missing."
            )


def _ensure_sample_token(
    client: Xian,
    *,
    name: str,
    token_name: str,
    token_symbol: str,
    supply: int | Decimal,
    governor_address: str,
    initial_holder: str,
    deploy_chi: int,
) -> Any:
    contract, _ = _deploy_contract(
        client,
        name=name,
        source_file="stable_token.s.py",
        args={
            "token_name": token_name,
            "token_symbol": token_symbol,
            "initial_supply": supply,
            "initial_holder": initial_holder,
            "governor_address": governor_address,
        },
        chi=deploy_chi,
    )
    return contract


def _maybe_set_controller(
    client: Xian,
    stable_token_contract_name: str,
    stable_token: Any,
    *,
    account: str,
    enabled: bool,
    chi: int,
) -> str | None:
    current = _bool_state(
        client,
        stable_token_contract_name,
        "controllers",
        account,
    )
    if current is enabled:
        return None
    return _send(
        stable_token,
        "set_controller",
        f"set controller {account}={enabled}",
        chi=chi,
        account=account,
        enabled=enabled,
    )


def _ensure_oracle_state(
    client: Xian, oracle: Any, config: BootstrapConfig
) -> list[str]:
    tx_hashes: list[str] = []
    tx_hashes.append(
        _send(
            oracle,
            "set_asset_config",
            f"configure oracle asset {config.asset_key}",
            chi=config.tx_chi,
            asset=config.asset_key,
            min_reporters_required=config.min_reporters_required,
            max_price_age_seconds=config.max_price_age_seconds,
        )
    )
    for reporter in config.oracle_reporters:
        if _bool_state(
            client,
            config.oracle_contract_name,
            "reporters",
            reporter,
        ):
            continue
        tx_hashes.append(
            _send(
                oracle,
                "set_reporter",
                f"enable oracle reporter {reporter}",
                chi=config.tx_chi,
                account=reporter,
                enabled=True,
            )
        )
    if config.operator_address in config.oracle_reporters:
        tx_hashes.append(
            _send(
                oracle,
                "submit_price",
                f"submit oracle price for {config.asset_key}",
                chi=config.tx_chi,
                asset=config.asset_key,
                price=config.asset_price,
            )
        )
    return tx_hashes


def _ensure_fee_destinations(
    vaults: Any,
    psm: Any,
    config: BootstrapConfig,
) -> list[str]:
    tx_hashes = [
        _send(
            vaults,
            "set_savings_contract",
            "set vaults savings contract",
            chi=config.tx_chi,
            target_contract=config.savings_contract_name,
        ),
        _send(
            vaults,
            "set_treasury_address",
            "set vaults treasury address",
            chi=config.tx_chi,
            address=config.treasury_address,
        ),
        _send(
            psm,
            "set_treasury_address",
            "set psm treasury address",
            chi=config.tx_chi,
            address=config.treasury_address,
        ),
        _send(
            psm,
            "set_fees",
            "set psm fees",
            chi=config.tx_chi,
            mint_fee_bps_value=config.mint_fee_bps,
            redeem_fee_bps_value=config.redeem_fee_bps,
        ),
    ]
    return tx_hashes


def _ensure_default_vault_type(
    client: Xian, vaults: Any, config: BootstrapConfig
) -> tuple[int, str | None]:
    existing_collateral = client.get_state(
        config.vaults_contract_name,
        "vault_types",
        1,
        "collateral_contract",
    )
    if existing_collateral is not None:
        print("Vault type 1 already exists; leaving it unchanged.")
        return 1, None
    tx_hash = _send(
        vaults,
        "add_vault_type",
        "add default vault type",
        chi=config.tx_chi,
        collateral_contract_name=config.collateral_contract_name,
        oracle_key=config.asset_key,
        min_collateral_ratio_bps=config.min_collateral_ratio_bps,
        liquidation_ratio_bps=config.liquidation_ratio_bps,
        liquidation_bonus_bps=config.liquidation_bonus_bps,
        debt_ceiling=config.debt_ceiling,
        min_debt=config.min_debt,
        stability_fee_bps=config.stability_fee_bps,
        auction_duration_seconds=config.auction_duration_seconds,
        partial_liquidation_target_ratio_bps=(
            config.partial_liquidation_target_ratio_bps
        ),
        surplus_buffer_bps=config.surplus_buffer_bps,
        min_bid_increment_bps=config.min_bid_increment_bps,
        extension_window_seconds=config.extension_window_seconds,
        bid_extension_seconds=config.bid_extension_seconds,
    )
    return 1, tx_hash


def _maybe_start_governance_handoff(
    client: Xian,
    contracts: dict[str, Any],
    config: BootstrapConfig,
) -> list[str]:
    tx_hashes: list[str] = []
    for contract_name, contract in contracts.items():
        current_governor = client.get_state(contract_name, "governor")
        if current_governor == config.governance_contract_name:
            continue
        tx_hashes.append(
            _send(
                contract,
                "start_governance_transfer",
                f"start governance transfer for {contract_name}",
                chi=config.tx_chi,
                new_governor=config.governance_contract_name,
            )
        )
    return tx_hashes


def _snapshot_vault_type(
    client: Xian,
    contract_name: str,
    vault_type_id: int,
) -> dict[str, Any]:
    fields = (
        "active",
        "collateral_contract",
        "oracle_key",
        "min_collateral_ratio_bps",
        "liquidation_ratio_bps",
        "liquidation_bonus_bps",
        "partial_liquidation_target_ratio_bps",
        "debt_ceiling",
        "min_debt",
        "stability_fee_bps",
        "auction_duration_seconds",
        "min_bid_increment_bps",
        "extension_window_seconds",
        "bid_extension_seconds",
        "surplus_buffer_bps",
        "rate_accumulator",
        "normalized_debt_total",
        "principal_outstanding",
        "auction_debt_locked",
        "auction_principal_locked",
        "fees_distributed",
        "surplus_buffer",
        "bad_debt",
    )
    return {
        field: client.get_state(contract_name, "vault_types", vault_type_id, field)
        for field in fields
    }


def _snapshot_psm_state(client: Xian, contract_name: str) -> dict[str, Any]:
    return {
        "stable_token_contract": client.get_state(
            contract_name, "stable_token_contract"
        ),
        "reserve_token_contract": client.get_state(
            contract_name, "reserve_token_contract"
        ),
        "governor": client.get_state(contract_name, "governor"),
        "treasury_address": client.get_state(
            contract_name, "treasury_address"
        ),
        "mint_fee_bps": client.get_state(contract_name, "mint_fee_bps"),
        "redeem_fee_bps": client.get_state(contract_name, "redeem_fee_bps"),
        "paused": client.get_state(contract_name, "paused"),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Deploy and wire the Xian stable protocol reference contracts."
        )
    )
    parser.add_argument(
        "--skip-sample-tokens",
        action="store_true",
        help=(
            "Expect the configured collateral and reserve token contracts to "
            "already exist instead of deploying sample tokens."
        ),
    )
    parser.add_argument(
        "--start-governance-handoff",
        action="store_true",
        help=(
            "Start governance transfer for protocol contracts to the chain "
            "governance contract after bootstrap completes."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    wallet = _require_wallet()
    config = _load_config(wallet)
    _validate_config(config, skip_sample_tokens=args.skip_sample_tokens)
    if config.governor_address != config.operator_address:
        raise RuntimeError(
            "The bootstrap wallet must match XIAN_STABLE_GOVERNOR while "
            "deployment and wiring are still governor-managed."
        )
    if config.min_reporters_required > 1:
        print(
            "Warning: bootstrap only submits an initial price from the "
            "operator reporter. Additional reporters must submit before the "
            "oracle reaches quorum.",
            file=sys.stderr,
        )

    client_config = XianClientConfig(
        retry=RetryPolicy(max_attempts=3, initial_delay_seconds=0.25)
    )

    with Xian(
        config.node_url,
        chain_id=config.chain_id,
        wallet=wallet,
        config=client_config,
    ) as client:
        _ensure_chain_governance(client, config)
        status = client.get_node_status()
        print(
            f"Connected to {status.network} at height "
            f"{status.latest_block_height}"
        )

        stable_token, _ = _deploy_contract(
            client,
            name=config.stable_token_contract_name,
            source_file="stable_token.s.py",
            args={
                "token_name": config.stable_token_name,
                "token_symbol": config.stable_token_symbol,
                "initial_supply": 0,
                "initial_holder": config.operator_address,
                "governor_address": config.governor_address,
            },
            chi=config.deploy_chi,
        )

        if args.skip_sample_tokens:
            for name in (
                config.collateral_contract_name,
                config.reserve_contract_name,
            ):
                if client.get_contract(name) is None:
                    raise RuntimeError(
                        f"Configured token contract '{name}' does not exist."
                    )
        else:
            _ensure_sample_token(
                client,
                name=config.collateral_contract_name,
                token_name=config.collateral_token_name,
                token_symbol=config.collateral_token_symbol,
                supply=config.sample_token_supply,
                governor_address=config.governor_address,
                initial_holder=config.operator_address,
                deploy_chi=config.deploy_chi,
            )
            _ensure_sample_token(
                client,
                name=config.reserve_contract_name,
                token_name=config.reserve_token_name,
                token_symbol=config.reserve_token_symbol,
                supply=config.sample_token_supply,
                governor_address=config.governor_address,
                initial_holder=config.operator_address,
                deploy_chi=config.deploy_chi,
            )

        oracle, _ = _deploy_contract(
            client,
            name=config.oracle_contract_name,
            source_file="oracle.s.py",
            args={"governor_address": config.governor_address},
            chi=config.deploy_chi,
        )
        savings, _ = _deploy_contract(
            client,
            name=config.savings_contract_name,
            source_file="savings.s.py",
            args={
                "stable_token_contract_name": config.stable_token_contract_name,
                "governor_address": config.governor_address,
            },
            chi=config.deploy_chi,
        )
        vaults, _ = _deploy_contract(
            client,
            name=config.vaults_contract_name,
            source_file="vaults.s.py",
            args={
                "stable_token_contract_name": config.stable_token_contract_name,
                "oracle_contract_name": config.oracle_contract_name,
                "governor_address": config.governor_address,
                "savings_contract_name": config.savings_contract_name,
                "treasury_address_value": config.treasury_address,
            },
            chi=config.deploy_chi,
        )
        psm, _ = _deploy_contract(
            client,
            name=config.psm_contract_name,
            source_file="psm.s.py",
            args={
                "stable_token_contract_name": config.stable_token_contract_name,
                "reserve_token_contract_name": config.reserve_contract_name,
                "governor_address": config.governor_address,
                "treasury_address_value": config.treasury_address,
                "mint_fee_bps_value": config.mint_fee_bps,
                "redeem_fee_bps_value": config.redeem_fee_bps,
            },
            chi=config.deploy_chi,
        )

        tx_hashes: dict[str, list[str]] = {
            "controllers": [],
            "oracle": [],
            "fee_routing": [],
            "vault_type": [],
            "governance_handoff": [],
        }

        for account in (
            config.vaults_contract_name,
            config.psm_contract_name,
        ):
            tx_hash = _maybe_set_controller(
                client,
                config.stable_token_contract_name,
                stable_token,
                account=account,
                enabled=True,
                chi=config.tx_chi,
            )
            if tx_hash:
                tx_hashes["controllers"].append(tx_hash)

        tx_hashes["oracle"] = _ensure_oracle_state(client, oracle, config)
        tx_hashes["fee_routing"] = _ensure_fee_destinations(
            vaults, psm, config
        )
        _, vault_type_tx_hash = _ensure_default_vault_type(
            client, vaults, config
        )
        if vault_type_tx_hash:
            tx_hashes["vault_type"].append(vault_type_tx_hash)

        protocol_contracts = {
            config.stable_token_contract_name: stable_token,
            config.oracle_contract_name: oracle,
            config.savings_contract_name: savings,
            config.vaults_contract_name: vaults,
            config.psm_contract_name: psm,
        }
        if args.start_governance_handoff:
            tx_hashes["governance_handoff"] = _maybe_start_governance_handoff(
                client,
                protocol_contracts, config
            )

        summary = {
            "network": status.network,
            "latest_block_height": status.latest_block_height,
            "operator_address": config.operator_address,
            "governor_address": config.governor_address,
            "governance_contract": config.governance_contract_name,
            "membership_contract": config.membership_contract_name,
            "contracts": {
                "stable_token": config.stable_token_contract_name,
                "oracle": config.oracle_contract_name,
                "savings": config.savings_contract_name,
                "vaults": config.vaults_contract_name,
                "psm": config.psm_contract_name,
                "collateral": config.collateral_contract_name,
                "reserve": config.reserve_contract_name,
            },
            "oracle": {
                "asset_key": config.asset_key,
                "reporters": config.oracle_reporters,
                "min_reporters_required": config.min_reporters_required,
                "asset_price": str(config.asset_price),
            },
            "default_vault_type": _snapshot_vault_type(
                client,
                config.vaults_contract_name,
                1,
            ),
            "psm_state": _snapshot_psm_state(
                client,
                config.psm_contract_name,
            ),
            "tx_hashes": {
                key: [value for value in values if value]
                for key, values in tx_hashes.items()
                if values
            },
            "next_steps": (
                [
                    "Use the configured collateral and reserve tokens for local testing.",
                    "Propose accept_governance() calls through the chain governance contract if you started the governance handoff.",
                ]
                if args.start_governance_handoff
                else [
                    "Run this script with --start-governance-handoff once you want chain governance to take ownership.",
                    "Add or update vault types, oracle reporters, and PSM fees through governance proposals after handoff.",
                ]
            ),
        }
        print(json.dumps(summary, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
