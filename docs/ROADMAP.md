# Roadmap

## Still Needed Before Production

- replace the manual reporter oracle with a stronger feed design
- add a formal governance integration contract instead of plain `governor`
- move from per-vault linear fee accrual to a cleaner global rate accumulator
- add partial liquidation support
- add auction cancellation / cure flows when a vault becomes safe again
- add a surplus buffer and explicit bad-debt resolution path
- define a standard stable token symbol / branding / metadata strategy
- add invariant-heavy tests and fuzzing around fee accrual and auction settlement
- add deployment scripts for the current Xian stack
- add integration tests against a live `xian-abci` node

## Nice-to-Have Extensions

- multiple oracle reporters with medianization
- safety shutdown / emergency pause module
- vault-type specific fee destinations
- keeper helper contracts or off-chain bots
- portfolio / accounting views optimized for BDS indexing

