# Roadmap

## Still Needed Before Production

- define a standard stable token symbol / branding / metadata strategy
- add invariant-heavy tests and fuzzing around fee accrual and auction settlement
- add deployment scripts for the current Xian stack
- add integration tests against a live `xian-abci` node
- add a stronger oracle sourcing and attestation model on top of reporter quorum
- add keeper automation and operational runbooks for auctions and oracle reporting
- design a cross-vault collateral redemption path if the protocol wants one

## Nice-to-Have Extensions

- safety shutdown / emergency pause module
- vault-type specific fee destinations
- portfolio / accounting views optimized for BDS indexing
- richer reserve management for the PSM
