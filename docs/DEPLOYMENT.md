# Deployment

## Purpose

This repository is the canonical bootstrap entrypoint for the Stable Protocol
solution pack.

The Xian stack integration is split cleanly:

- `xian-configs` packages the machine-readable solution-pack manifest plus the
  mirrored contract assets
- `xian-cli` exposes the local and remote starter flows
- `xian-deploy` documents the recommended remote operator posture
- this repository performs the actual protocol bootstrap and wiring

## Recommended Local Flow

From the `xian-cli` checkout:

```bash
uv run xian network create stable-protocol-local --template single-node-indexed --chain-id stable-protocol-local-1 --generate-validator-key --init-node
uv run xian node start validator-1
uv run xian node endpoints validator-1
```

From this repository:

```bash
uv sync --group dev --group deploy
uv run pytest -q
uv run python scripts/bootstrap_protocol.py
```

The `deploy` group expects the standard Xian workspace layout, including the
sibling `xian-py` and `xian-contracting` checkouts.

By default the bootstrap script also deploys sample
`con_collateral_token` and `con_reserve_token` contracts so the local
environment is immediately usable for:

- opening a vault
- minting the stable asset
- depositing into savings
- minting and redeeming through the PSM

## Recommended Remote Flow

From the `xian-cli` checkout:

```bash
uv run xian solution-pack starter stable-protocol --flow remote
```

That starter flow mirrors the expected `consortium-3` remote posture. After the
network is deployed and healthy, run this repository against the remote RPC:

```bash
export XIAN_NODE_URL=http://<rpc-host>:26657
export XIAN_CHAIN_ID=<remote-chain-id>
export XIAN_WALLET_PRIVATE_KEY=<bootstrap-wallet>

uv sync --group dev --group deploy
uv run python scripts/bootstrap_protocol.py --skip-sample-tokens
```

Use `--skip-sample-tokens` when the collateral and reserve token contracts
already exist and you only want to deploy the protocol core.

## Bootstrap Script Behavior

`scripts/bootstrap_protocol.py` is intentionally idempotent within a normal
operator workflow:

- existing protocol contracts are left in place
- controller allowlist entries are only added when missing
- the default vault type is only created when vault type `1` does not exist
- fee-routing targets on `con_vaults` and `con_psm` are re-applied explicitly
- oracle asset configuration is re-applied explicitly

The script does **not** try to mutate an existing vault type in place. If
vault type `1` already exists, the script reports that and leaves it unchanged.

## Environment Variables

Required:

- `XIAN_WALLET_PRIVATE_KEY`: bootstrap operator key
- `XIAN_NODE_URL`: defaults to `http://127.0.0.1:26657`
- `XIAN_CHAIN_ID`: optional for local flows, usually required for remote flows

Common overrides:

- `XIAN_STABLE_GOVERNOR`: initial governor address for protocol contracts
- `XIAN_STABLE_TREASURY`: treasury address used by `con_vaults` and `con_psm`
- `XIAN_STABLE_TOKEN_CONTRACT`
- `XIAN_STABLE_ORACLE_CONTRACT`
- `XIAN_STABLE_SAVINGS_CONTRACT`
- `XIAN_STABLE_VAULTS_CONTRACT`
- `XIAN_STABLE_PSM_CONTRACT`
- `XIAN_STABLE_COLLATERAL_CONTRACT`
- `XIAN_STABLE_RESERVE_CONTRACT`
- `XIAN_STABLE_ORACLE_REPORTERS`: comma-separated reporter accounts
- `XIAN_STABLE_ASSET_KEY`
- `XIAN_STABLE_ASSET_PRICE`
- `XIAN_STABLE_MIN_REPORTERS_REQUIRED`
- `XIAN_STABLE_MAX_PRICE_AGE_SECONDS`
- `XIAN_STABLE_DEBT_CEILING`
- `XIAN_STABLE_MIN_DEBT`
- `XIAN_STABLE_STABILITY_FEE_BPS`
- `XIAN_STABLE_PSM_MINT_FEE_BPS`
- `XIAN_STABLE_PSM_REDEEM_FEE_BPS`
- `XIAN_STABLE_DEPLOY_CHI`
- `XIAN_STABLE_TX_CHI`

The defaults are aimed at a usable local/staging protocol, not final production
risk settings.

For the protocol core, current Xian submission rules require user-deployed
contract names to start with `con_`. The bootstrap defaults already use:

- `con_stable_token`
- `con_oracle`
- `con_savings`
- `con_vaults`
- `con_psm`

When sample assets are enabled, the default local/staging token names are:

- `con_collateral_token`
- `con_reserve_token`

During bootstrap, `XIAN_STABLE_GOVERNOR` should match the wallet you are using
to run the script. Governor-managed configuration only moves to chain
governance after you explicitly start the handoff.

The bootstrap script supplies explicit chi budgets for writes so it can still
run on network profiles where readonly simulation is disabled or unavailable.

## Governance Handoff

After verifying bootstrap state, start governance transfer with:

```bash
uv run python scripts/bootstrap_protocol.py --start-governance-handoff
```

That sends `start_governance_transfer(new_governor='governance')` to:

- `con_stable_token`
- `con_oracle`
- `con_savings`
- `con_vaults`
- `con_psm`

It does not complete the transfer. The chain `governance` contract must still
call `accept_governance()` on each target through ordinary governance
proposals.

## Required Post-Bootstrap Checks

Verify at minimum:

- `con_stable_token.is_controller('con_vaults')` is `True`
- `con_stable_token.is_controller('con_psm')` is `True`
- `con_oracle.price_info('<asset-key>')` returns a live price with enough fresh
  reports
- `con_vaults.get_vault_type(1)` returns the expected collateral and fee
  settings
- `con_psm.get_state()` reports the intended reserve token, fee settings, and
  treasury address

## Notes

- Production ownership is expected to move to the current chain
  `masternodes` / `governance` pair, not to stay with a human bootstrap key.
- The local compatibility harnesses in this repository are only for standalone
  unit tests.
- Fee routing is part of correct deployment, not an optional polish step.
