import pytest
from xian_runtime_types.time import Datetime


def test_oracle_governor_is_default_reporter(protocol):
    protocol.oracle.submit_price(asset="BTC", price=100_000, signer="governor")
    assert protocol.oracle.get_price(asset="BTC") == 100_000


def test_oracle_non_reporter_cannot_publish(protocol):
    with pytest.raises(AssertionError):
        protocol.oracle.submit_price(asset="BTC", price=90_000, signer="alice")


def test_oracle_uses_median_with_quorum(protocol):
    protocol.oracle.set_reporter(account="oracle_2", enabled=True, signer="governor")
    protocol.oracle.set_reporter(account="oracle_3", enabled=True, signer="governor")
    protocol.oracle.set_asset_config(
        asset="BTC",
        min_reporters_required=2,
        max_price_age_seconds=86400,
        signer="governor",
    )

    protocol.oracle.submit_price(asset="BTC", price=100_000, signer="governor")
    protocol.oracle.submit_price(asset="BTC", price=110_000, signer="oracle_2")
    protocol.oracle.submit_price(asset="BTC", price=130_000, signer="oracle_3")

    assert protocol.oracle.get_price(asset="BTC") == 110_000


def test_oracle_freshness_limit_is_enforced(protocol):
    start = {"now": Datetime(year=2026, month=1, day=1)}
    later = {"now": Datetime(year=2026, month=1, day=3)}

    protocol.oracle.set_reporter(account="oracle_2", enabled=True, signer="governor")
    protocol.oracle.set_asset_config(
        asset="COL",
        min_reporters_required=2,
        max_price_age_seconds=86400,
        signer="governor",
    )
    protocol.oracle.submit_price(
        asset="COL",
        price=2,
        signer="governor",
        environment=start,
    )
    protocol.oracle.submit_price(
        asset="COL",
        price=2.2,
        signer="oracle_2",
        environment=start,
    )

    with pytest.raises(AssertionError):
        protocol.oracle.get_price(asset="COL", environment=later)
