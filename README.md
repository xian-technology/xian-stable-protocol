# xian-stable-protocol

`xian-stable-protocol` is a Xian-native redesign of the old `rubixdao` prototype.

It keeps the original high-level idea:

- overcollateralized vaults mint a stable asset
- vault debt accrues a stability fee
- protocol fees can be routed into a savings pool
- unsafe vaults can be liquidated quickly or auctioned
- governance changes are intended to execute through Xian's `members` and `governance` contracts
- a peg stability module offers direct mint and redeem flows against reserve assets

But it is intentionally **not** a literal port. The contracts were redesigned for
current Xian / Contracting patterns:

- standard token approvals use a dedicated `approvals` hash
- contracts emit structured `LogEvent`s for indexers and explorers
- the debt engine uses per-type rate accumulators and debt shares instead of per-vault ad hoc debt math
- governance is explicit and delayed instead of implicit owner backdoors
- liquidation supports partial cure, auction cancellation, and owner cure flows
- auction settlement records bad debt honestly when collateral cannot cover system debt
- a surplus buffer and recapitalization path keep protocol losses explicit

## Contracts

- [contracts/members_compat.s.py](/Users/endogen/Projekte/xian/xian-stable-protocol/contracts/members_compat.s.py)
  A lightweight compatibility harness for the `members` membership interface used in standalone tests.
- [contracts/governance_compat.s.py](/Users/endogen/Projekte/xian/xian-stable-protocol/contracts/governance_compat.s.py)
  A standalone compatibility harness mirroring Xian's contract-call governance flow.
- [contracts/stable_token.s.py](/Users/endogen/Projekte/xian/xian-stable-protocol/contracts/stable_token.s.py)
  A controller-minted fungible token intended for the protocol stable asset.
- [contracts/oracle.s.py](/Users/endogen/Projekte/xian/xian-stable-protocol/contracts/oracle.s.py)
  A governed multi-reporter oracle with freshness and quorum controls.
- [contracts/savings.s.py](/Users/endogen/Projekte/xian/xian-stable-protocol/contracts/savings.s.py)
  A share-based savings vault whose share price increases when fees are routed in.
- [contracts/vaults.s.py](/Users/endogen/Projekte/xian/xian-stable-protocol/contracts/vaults.s.py)
  The CDP engine: vault types, borrowing, debt-share accrual, partial liquidation, auctions, and bad-debt handling.
- [contracts/psm.s.py](/Users/endogen/Projekte/xian/xian-stable-protocol/contracts/psm.s.py)
  A peg stability module that mints and redeems the stable asset against reserve assets with configurable fees.

## Deployment Flow

Canonical production contract names:

- `members`
- `governance`
- `stable_token`
- `oracle`
- `savings`
- `vaults`
- `psm`

Suggested deployment order:

1. Use the chain's existing `members` and `governance` contracts
2. Deploy `stable_token`
3. Deploy reserve-asset token contracts
4. Deploy `oracle`
5. Deploy `savings`
6. Deploy `vaults`
7. Deploy `psm`
8. Grant controller rights on `stable_token` to `vaults` and `psm`
9. Configure oracle reporters and publish feed prices
10. Add vault types on `vaults`
11. Transfer protocol contract governance to `governance`

## Testing

Run the contract tests with:

```bash
uv sync --python 3.14 --group dev
uv run --python 3.14 pytest -q
```

The tests use the local `contracting` runtime and cover:

- stable token controller and allowance flows
- weighted governance using Xian governance semantics
- oracle reporter, quorum, medianization, and freshness behavior
- savings share accounting
- vault creation, closing, fee accrual, collateral withdrawals, and debt-share accounting
- partial liquidation and owner-cured auctions
- liquidation auctions with bid extension, bidder refunds, bad debt accounting, and recapitalization
- PSM mint and redeem flows

## Dependency Note

This repository tracks the current `xian-contracting` `main` branch via
`tool.uv.sources` and locks the resolved revision in `uv.lock`. That is
intentional: the protocol targets the latest Xian Contracting event and runtime
behavior, which may move ahead of the last PyPI release.

## Status

This repository should be treated as a **reference implementation** and a strong
starting point, not as a finished production protocol.

The main remaining work is listed in [docs/ROADMAP.md](/Users/endogen/Projekte/xian/xian-stable-protocol/docs/ROADMAP.md).
