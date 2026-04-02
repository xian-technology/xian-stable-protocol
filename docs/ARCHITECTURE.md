# Architecture

## Goal

The protocol issues a stable asset against overcollateralized positions and
routes protocol fee income into a savings pool.

## Components

### `stable_token`

- standard fungible token
- governor-managed controller allowlist
- intended controller: `vaults`
- users can burn their own balance

### `oracle`

- governor-managed reporter set
- per-asset prices
- per-asset freshness threshold
- intentionally simple, but structured enough to replace later

### `vaults`

- vault type registry
- user vault lifecycle
- linear stability fee accrual on outstanding principal
- fast liquidation when collateral can still cover debt plus bonus
- auction liquidation when collateral cannot cover the fast path cleanly
- fee routing to `savings`, `treasury`, or `governor`
- bad debt accounting on auction shortfall

### `savings`

- share-based vault for the protocol stable asset
- deposits mint shares against current asset/share ratio
- routed protocol fees increase assets per share
- no rebasing; users hold transferable shares

## Major Redesign Decisions

### 1. No fake DAO wrapper

The old project called itself a DAO but the contracts were really operator-owned.
This redesign is explicit about that. There is a `governor` hook and transfer
process, but no pretend governance layer inside the protocol contracts.

### 2. Honest bad debt accounting

The old design tried to self-equalize debt pools through mutable ratios. This
version records `bad_debt` per vault type when auction proceeds do not cover the
vault debt. That is cleaner and easier to reason about.

### 3. Share-based savings instead of bespoke stake math

The old staking logic was a custom interest-bearing token with ad hoc pricing.
This version uses a standard share vault: deposits mint shares and fee inflows
raise the share price.

### 4. Safe elapsed-time math

The old contracts used Python's `timedelta.seconds` semantics, which break
across day boundaries. Xian's current runtime types already expose total elapsed
seconds through `Timedelta.seconds`, so this redesign uses that runtime-native
value directly instead of reconstructing elapsed time by hand.

## Limitations

- oracle security is still manual reporter based
- stability fee accrual is linear, not a global compounding rate accumulator
- auctions are English auctions, not Dutch or keeper-optimized
- there is no active peg module, PSM, or redemption queue
- there is no automated surplus / deficit recapitalization mechanism yet
