# xian-stable-protocol

`xian-stable-protocol` is a Xian-native redesign of the old `rubixdao` prototype.

It keeps the original high-level idea:

- overcollateralized vaults mint a stable asset
- vault debt accrues a stability fee
- protocol fees can be routed into a savings pool
- unsafe vaults can be liquidated quickly or auctioned

But it is intentionally **not** a literal port. The contracts were redesigned for
current Xian / Contracting patterns:

- standard token approvals use a dedicated `approvals` hash
- contracts emit structured `LogEvent`s for indexers and explorers
- fee math uses safe elapsed-time handling instead of the old `timedelta.seconds` bug
- admin hooks are explicit `governor` controls rather than raw mutable state backdoors
- auction settlement records bad debt honestly when collateral cannot cover system debt

## Contracts

- [contracts/stable_token.s.py](/Users/endogen/Projekte/xian/xian-stable-protocol/contracts/stable_token.s.py)
  A controller-minted fungible token intended for the protocol stable asset.
- [contracts/oracle.s.py](/Users/endogen/Projekte/xian/xian-stable-protocol/contracts/oracle.s.py)
  A governed reporter oracle with freshness controls.
- [contracts/savings.s.py](/Users/endogen/Projekte/xian/xian-stable-protocol/contracts/savings.s.py)
  A share-based savings vault whose share price increases when fees are routed in.
- [contracts/vaults.s.py](/Users/endogen/Projekte/xian/xian-stable-protocol/contracts/vaults.s.py)
  The CDP engine: vault types, borrowing, repayment, fast liquidation, and auctions.

## Deployment Flow

Canonical contract names used by the tests and examples:

- `stable_token`
- `oracle`
- `savings`
- `vaults`

Suggested deployment order:

1. Deploy `stable_token`
2. Deploy `oracle`
3. Deploy `savings`
4. Deploy `vaults`
5. Grant `vaults` controller rights on `stable_token`
6. Configure oracle reporters and publish feed prices
7. Add vault types on `vaults`

## Testing

Run the contract tests with:

```bash
uv sync --python 3.14 --group dev
uv run --python 3.14 pytest -q
```

The tests use the local `contracting` runtime and cover:

- stable token controller and allowance flows
- oracle reporter / freshness behavior
- savings share accounting
- vault creation, closing, fee accrual, collateral withdrawals
- fast liquidation
- liquidation auctions with bidder refunds and bad debt accounting

## Dependency Note

This repository tracks the current `xian-contracting` `main` branch via
`tool.uv.sources` and locks the resolved revision in `uv.lock`. That is
intentional: the protocol targets the latest Xian Contracting event and runtime
behavior, which may move ahead of the last PyPI release.

## Status

This repository should be treated as a **reference implementation** and a strong
starting point, not as a finished production protocol.

The main remaining work is listed in [docs/ROADMAP.md](/Users/endogen/Projekte/xian/xian-stable-protocol/docs/ROADMAP.md).
