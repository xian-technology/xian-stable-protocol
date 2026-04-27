# Architecture

## Goal

The protocol issues a stable asset against overcollateralized positions, offers
direct reserve-backed mint and redeem flows, and routes protocol fee income
into both a savings pool and an explicit surplus buffer.

## Components

### `masternodes` / `governance`

- production ownership is meant to live with Xian's current chain-level
  `masternodes` and `governance` contracts
- `masternodes` supplies the weighted membership interface
- `governance` executes protocol contract calls once proposals reach threshold
- the repo includes local harness contracts for standalone tests, but the target
  runtime is the real chain governance system

### `stable_token`

- standard fungible token
- governor-managed controller allowlist
- intended controllers: `vaults` and `psm`
- live-chain deployments use `con_stable_token`, `con_vaults`, and `con_psm`
- users can burn their own balance

### `oracle`

- governor-managed reporter allowlist
- per-asset quorum and freshness configuration
- medianized price selection across fresh reports
- still a committee-governed oracle, not a trustless feed

### `psm`

- peg stability module for reserve-backed mint and redeem flows
- symmetric 1:1 style conversions with configurable mint and redeem fees
- reserve fees route directly to treasury
- live-chain deployments typically use a reserve asset such as
  `con_reserve_token`
- provides a clean redeem path without touching CDP collateral

### `vaults`

- vault type registry
- user vault lifecycle
- debt-share accounting with per-type rate accumulators
- partial liquidation when a vault can be restored safely
- auction liquidation when partial cure cannot restore the vault
- auction cure and auction cancellation when the vault becomes safe again
- fee routing to `savings`, `treasury`, or `governor`
- live-chain deployments typically use `con_vaults`, `con_savings`, and a
  collateral asset such as `con_collateral_token`
- explicit surplus buffer, bad debt accounting, and recapitalization hooks

### `savings`

- share-based vault for the protocol stable asset
- deposits mint shares against current asset/share ratio
- routed protocol fees increase assets per share
- no rebasing; users hold transferable shares

## Major Redesign Decisions

### 1. Governance is explicit and chain-native

The old project called itself a DAO but the contracts were really operator-owned.
This redesign makes governance an explicit chain integration point. Bootstrap
still starts from a human governor, but production ownership is meant to move to
Xian's `governance` contract backed by `masternodes`, not to an isolated
protocol DAO.

### 2. Debt is tracked as shares, not stored debt snapshots

The old prototype mixed stored debt and rate assumptions at the vault level.
This redesign keeps per-type rate accumulators and per-vault debt shares. That
gives cleaner fee accrual, cleaner accounting around auctions, and safer vault
introspection.

### 3. Honest bad debt accounting and surplus handling

The protocol records bad debt explicitly when auctions do not clear the full
vault debt. Fee income can accumulate partly in a surplus buffer, that buffer
can cover bad debt directly, and external recapitalizers can inject stable
assets without mutating protocol state by hand.

### 4. Share-based savings instead of bespoke stake math

The old staking logic was a custom interest-bearing token with ad hoc pricing.
This version uses a standard share vault: deposits mint shares and fee inflows
raise the share price.

### 5. The peg layer is a separate module

The PSM is not merged into `vaults`. That keeps CDP risk and reserve-backed peg
operations separate, which makes both the accounting and governance boundary
cleaner.

## Limitations

- oracle security is still committee-governed reporter based
- governance still depends on the current Xian governance surface and its contract-call model, so future chain-governance changes need to be tracked
- auctions are English auctions and still need better keeper ergonomics
- there is no native collateral redemption path across vault types
- there are no invariant or fuzz tests yet
- there are no live-network integration tests yet
