# Roadmap

## Still Needed Before Production

- define a standard stable token symbol / branding / metadata strategy
- run the invariant and seeded-fuzz suite against a live `xian-abci` node and
  expand it into long-running stateful campaigns
- add integration tests against a live `xian-abci` node
- accept the proposed
  [Oracle Authorization V2 design and acceptance gates](https://github.com/xian-technology/xian-meta/blob/main/docs/ORACLE_AUTHORIZATION_V2.md#acceptance-gates),
  including authorization-time versus delayed-settlement semantics, source/clock
  trust and exposure limits; it is not implemented, enabled or production-approved
- implement and validate the accepted oracle protocol on the actual node before
  enabling meaningful TVL; consensus header age and successor debt/auction clocks
  alone do not establish external price freshness after a halt
- add keeper automation and operational runbooks for auctions and oracle reporting
- design a cross-vault collateral redemption path if the protocol wants one

## Nice-to-Have Extensions

- safety shutdown / emergency pause module
- vault-type specific fee destinations
- portfolio / accounting views optimized for BDS indexing
- richer reserve management for the PSM
