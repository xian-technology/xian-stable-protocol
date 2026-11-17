# Roadmap

## Still Needed Before Production

- define a standard stable token symbol / branding / metadata strategy
- run the invariant and seeded-fuzz suite against a live `xian-abci` node and
  expand it into long-running stateful campaigns
- add integration tests against a live `xian-abci` node
- design and accept a stronger oracle freshness/attestation protocol before
  production use: consensus header age alone cannot establish external price
  freshness after a halt; successor debt/auction clocks do not solve this
- validate that oracle protocol on the actual node before enabling meaningful TVL
- add keeper automation and operational runbooks for auctions and oracle reporting
- design a cross-vault collateral redemption path if the protocol wants one

## Nice-to-Have Extensions

- safety shutdown / emergency pause module
- vault-type specific fee destinations
- portfolio / accounting views optimized for BDS indexing
- richer reserve management for the PSM
