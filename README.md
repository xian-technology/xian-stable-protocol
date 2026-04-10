# xian-stable-protocol

`xian-stable-protocol` is a Xian-native redesign of the old `rubixdao`
prototype.

It keeps the original high-level idea:

- overcollateralized vaults mint a stable asset
- vault debt accrues a stability fee
- protocol fees can be routed into a savings pool
- unsafe vaults can be liquidated quickly or auctioned
- governance changes execute through Xian's `members` and `governance`
  contracts
- a peg stability module offers direct mint and redeem flows against reserve
  assets

But it is intentionally **not** a literal port. The contracts were redesigned
for current Xian / Contracting patterns:

- standard token approvals use a dedicated `approvals` hash
- contracts emit structured `LogEvent`s for indexers and explorers
- the debt engine uses per-type rate accumulators and debt shares instead of
  per-vault ad hoc debt math
- governance is explicit and delayed instead of implicit owner backdoors
- liquidation supports partial cure, auction cancellation, and owner cure flows
- auction settlement records bad debt honestly when collateral cannot cover
  system debt
- a surplus buffer and recapitalization path keep protocol losses explicit

## Xian Stack Integration

The stable protocol is now packaged as a first-class Xian solution pack:

- `xian-configs/solution-packs/stable-protocol/` contains the canonical pack
  manifest and mirrored contract assets used by `xian-cli`
- `xian-cli` can surface the pack with:
  - `uv run xian solution-pack show stable-protocol`
  - `uv run xian solution-pack starter stable-protocol`
  - `uv run xian solution-pack starter stable-protocol --flow remote`
- `xian-deploy/docs/SOLUTION_PACKS.md` mirrors the recommended remote operator
  posture for the pack

The protocol repository itself remains the canonical bootstrap and operator
entrypoint. The starter flows point here for deployment and wiring.

## Contracts

- [contracts/members_compat.s.py](/Users/endogen/Projekte/xian/xian-stable-protocol/contracts/members_compat.s.py)
  A lightweight compatibility harness for the `members` membership interface
  used in standalone tests.
- [contracts/governance_compat.s.py](/Users/endogen/Projekte/xian/xian-stable-protocol/contracts/governance_compat.s.py)
  A standalone compatibility harness mirroring Xian's contract-call governance
  flow.
- [contracts/stable_token.s.py](/Users/endogen/Projekte/xian/xian-stable-protocol/contracts/stable_token.s.py)
  A controller-minted fungible token intended for the protocol stable asset.
- [contracts/oracle.s.py](/Users/endogen/Projekte/xian/xian-stable-protocol/contracts/oracle.s.py)
  A governed multi-reporter oracle with freshness and quorum controls.
- [contracts/savings.s.py](/Users/endogen/Projekte/xian/xian-stable-protocol/contracts/savings.s.py)
  A share-based savings vault whose share price increases when fees are routed
  in.
- [contracts/vaults.s.py](/Users/endogen/Projekte/xian/xian-stable-protocol/contracts/vaults.s.py)
  The CDP engine: vault types, borrowing, debt-share accrual, partial
  liquidation, auctions, and bad-debt handling.
- [contracts/psm.s.py](/Users/endogen/Projekte/xian/xian-stable-protocol/contracts/psm.s.py)
  A peg stability module that mints and redeems the stable asset against
  reserve assets with configurable fees.

## Bootstrap

The repository now includes an executable bootstrap path for the Xian stack:

```bash
uv sync --group dev --group deploy
uv run pytest -q
uv run python scripts/bootstrap_protocol.py
```

The bootstrap script:

- deploys `stable_token`, `oracle`, `savings`, `vaults`, and `psm` if they are
  missing
- optionally deploys sample `collateral_token` and `reserve_token` contracts
  for local or staging use
- enables `vaults` and `psm` as stable-token controllers
- configures oracle reporters and an initial price feed
- sets the required fee-routing addresses on `vaults` and `psm`
- seeds a default vault type only when one does not already exist

During bootstrap, the operator wallet must match the configured initial
governor. After handoff starts, further governance-managed changes should go
through the chain `governance` contract instead of this script.

To start governance handoff after bootstrap:

```bash
uv run python scripts/bootstrap_protocol.py --start-governance-handoff
```

That only starts transfer to the chain `governance` contract. Acceptance still
has to happen through ordinary governance proposals that call
`accept_governance()` on each protocol contract.

Full operator guidance and the environment variable surface are in
[docs/DEPLOYMENT.md](/Users/endogen/Projekte/xian/xian-stable-protocol/docs/DEPLOYMENT.md).

## Required Wiring

The protocol is not correctly wired unless fee destinations are configured.
These are the minimum required relationships:

```python
stable_token.set_controller(account='vaults', enabled=True)
stable_token.set_controller(account='psm', enabled=True)

vaults.set_savings_contract(target_contract='savings')
vaults.set_treasury_address(address='treasury')
psm.set_treasury_address(address='treasury')
```

If `vaults` has no `savings_contract` and no `treasury_address`, or `psm` has
no `treasury_address`, fees fall back to the current governor. That is valid
contract behavior but not the intended production setup.

The public operational surface also includes the governance-managed functions
that materially affect day-2 operations:

- `vaults.set_vault_type_auction_config(...)`
- `vaults.set_vault_type_surplus_buffer_bps(...)`
- `vaults.set_savings_contract(...)`
- `vaults.set_treasury_address(...)`
- `vaults.claim_refund(...)`
- `vaults.liquidate_fast(...)`
- `psm.set_treasury_address(...)`
- `psm.get_state()`

## Canonical Production Contract Names

- `members`
- `governance`
- `stable_token`
- `oracle`
- `savings`
- `vaults`
- `psm`

## Testing

Run the contract tests with:

```bash
uv sync --group dev
uv run pytest -q
```

The tests use the local `contracting` runtime and cover:

- stable token controller and allowance flows
- weighted governance using Xian governance semantics
- oracle reporter, quorum, medianization, and freshness behavior
- savings share accounting
- vault creation, closing, fee accrual, collateral withdrawals, and debt-share
  accounting
- partial liquidation and owner-cured auctions
- liquidation auctions with bid extension, bidder refunds, bad debt accounting,
  and recapitalization
- PSM mint and redeem flows

## Dependency Note

This repository tracks the current `xian-contracting` `main` branch via
`tool.uv.sources` and locks the resolved revision in `uv.lock`. That is
intentional: the protocol targets the latest Xian Contracting event and runtime
behavior, which may move ahead of the last PyPI release.

The optional `deploy` dependency group tracks `xian-py` so the bootstrap script
can exercise the same public SDK surface that the rest of the Xian stack uses.

## Status

This repository should be treated as a strong reference implementation with a
real Xian-stack bootstrap path, not as a fully automated production protocol.

The main remaining production-hardening work is listed in
[docs/ROADMAP.md](/Users/endogen/Projekte/xian/xian-stable-protocol/docs/ROADMAP.md).
