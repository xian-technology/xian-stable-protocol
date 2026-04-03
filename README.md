# xian-stable-protocol

`xian-stable-protocol` is a Xian-native redesign of the old `rubixdao` prototype.

It keeps the original high-level idea:

- overcollateralized vaults mint a stable asset
- vault debt accrues a stability fee
- protocol fees can be routed into a savings pool
- unsafe vaults can be liquidated quickly or auctioned
- governance changes execute through a timelocked weighted committee
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

- [contracts/committee.s.py](/Users/endogen/Projekte/xian/xian-stable-protocol/contracts/committee.s.py)
  A simple weighted membership contract used by governance.
- [contracts/protocol_governance.s.py](/Users/endogen/Projekte/xian/xian-stable-protocol/contracts/protocol_governance.s.py)
  A timelocked contract-call governance layer for protocol administration.
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

Canonical contract names used by the tests and examples:

- `committee`
- `protocol_governance`
- `stable_token`
- `oracle`
- `savings`
- `vaults`
- `psm`

Suggested deployment order:

1. Deploy `committee`
2. Deploy `protocol_governance`
3. Deploy `stable_token`
4. Deploy reserve-asset token contracts
5. Deploy `oracle`
6. Deploy `savings`
7. Deploy `vaults`
8. Deploy `psm`
9. Grant controller rights on `stable_token` to `vaults` and `psm`
10. Configure oracle reporters and publish feed prices
11. Add vault types on `vaults`
12. Transfer protocol contract governance to `protocol_governance`

## Testing

Run the contract tests with:

```bash
uv sync --python 3.14 --group dev
uv run --python 3.14 pytest -q
```

The tests use the local `contracting` runtime and cover:

- stable token controller and allowance flows
- weighted governance with timelocked execution
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
