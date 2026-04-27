import pytest


def test_savings_deposit_and_withdraw(protocol):
    protocol.stable_token.mint(amount=100, to="alice", signer="governor")
    protocol.stable_token.approve(amount=100, to="savings", signer="alice")

    shares = protocol.savings.deposit(assets=100, signer="alice")
    assets = protocol.savings.withdraw(shares=shares, signer="alice")

    assert shares == 100
    assert assets == 100
    assert protocol.savings.total_assets() == 0
    assert protocol.savings.total_supply() == 0


def test_savings_share_price_rises_when_rewards_arrive(protocol):
    protocol.stable_token.mint(amount=100, to="alice", signer="governor")
    protocol.stable_token.approve(amount=100, to="savings", signer="alice")
    protocol.savings.deposit(assets=100, signer="alice")

    protocol.stable_token.mint(amount=20, to="savings", signer="governor")

    assert protocol.savings.share_price() == pytest.approx(1.2)
    redeemed = protocol.savings.withdraw(shares=50, signer="alice")
    assert redeemed == pytest.approx(60)
