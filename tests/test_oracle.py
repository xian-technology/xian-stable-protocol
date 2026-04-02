import pytest
from xian_runtime_types.time import Datetime


def test_oracle_governor_is_default_reporter(protocol):
    protocol.oracle.set_price(asset="BTC", price=100_000, signer="governor")
    assert protocol.oracle.get_price(asset="BTC") == 100_000


def test_oracle_non_reporter_cannot_publish(protocol):
    with pytest.raises(AssertionError):
        protocol.oracle.set_price(asset="BTC", price=90_000, signer="alice")


def test_oracle_freshness_limit_is_enforced(protocol):
    start = {"now": Datetime(year=2026, month=1, day=1)}
    later = {"now": Datetime(year=2026, month=1, day=3)}

    protocol.oracle.set_max_price_age(asset="COL", seconds=86400, signer="governor")
    protocol.oracle.set_price(asset="COL", price=2, signer="governor", environment=start)

    with pytest.raises(AssertionError):
        protocol.oracle.get_price(asset="COL", environment=later)
