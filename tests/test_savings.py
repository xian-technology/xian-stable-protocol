from decimal import Decimal

import pytest


def test_savings_deposit_and_withdraw(protocol):
    protocol.stable_token.mint(amount=100, to="alice", signer="governor")
    protocol.stable_token.approve(amount=100, to="con_savings", signer="alice")

    shares = protocol.savings.deposit(assets=100, signer="alice")
    assets = protocol.savings.withdraw(shares=shares, signer="alice")

    assert shares == 100
    assert assets == 100
    assert protocol.savings.total_assets() == 0
    assert protocol.savings.total_supply() == 0


def test_savings_share_price_rises_when_rewards_arrive(protocol):
    protocol.stable_token.mint(amount=100, to="alice", signer="governor")
    protocol.stable_token.approve(amount=100, to="con_savings", signer="alice")
    protocol.savings.deposit(assets=100, signer="alice")

    protocol.stable_token.mint(amount=20, to="con_savings", signer="governor")

    assert protocol.savings.share_price() == pytest.approx(Decimal("1.2"))
    redeemed = protocol.savings.withdraw(shares=50, signer="alice")
    assert redeemed == pytest.approx(60)


def test_donation_cannot_inflate_shares_against_the_next_depositor(protocol):
    from xian_runtime_types.decimal import ContractingDecimal

    # The smallest deposit that still mints a share under the virtual offset.
    tiny = ContractingDecimal("0.000000000000000001")
    protocol.stable_token.mint(amount=1001, to="alice", signer="governor")
    protocol.stable_token.mint(amount=1500, to="bob", signer="governor")
    protocol.stable_token.approve(amount=1001, to="con_savings", signer="alice")
    protocol.stable_token.approve(amount=1500, to="con_savings", signer="bob")

    protocol.savings.deposit(assets=tiny, signer="alice")
    protocol.stable_token.transfer(amount=1000, to="con_savings", signer="alice")
    victim_shares = protocol.savings.deposit(assets=1500, signer="bob")

    attacker_assets = protocol.savings.withdraw(
        shares=protocol.savings.balance_of(address="alice"), signer="alice"
    )
    victim_assets = protocol.savings.withdraw(shares=victim_shares, signer="bob")

    assert victim_assets == pytest.approx(1500)
    assert attacker_assets < 1


def test_first_depositor_cannot_claim_assets_held_before_any_deposit(protocol):
    protocol.stable_token.mint(amount=1000, to="con_savings", signer="governor")
    protocol.stable_token.mint(amount=1000, to="alice", signer="governor")
    protocol.stable_token.approve(amount=1000, to="con_savings", signer="alice")

    shares = protocol.savings.deposit(assets=1000, signer="alice")
    redeemed = protocol.savings.withdraw(shares=shares, signer="alice")

    assert redeemed == pytest.approx(1000)


def test_deposit_rejects_assets_that_round_to_zero_shares(protocol):
    from xian_runtime_types.decimal import ContractingDecimal

    tiny = ContractingDecimal("0.000000000000000000000000000001")
    protocol.stable_token.mint(amount=1, to="alice", signer="governor")
    protocol.stable_token.approve(amount=1, to="con_savings", signer="alice")
    protocol.savings.deposit(assets=1, signer="alice")
    protocol.stable_token.mint(amount=1, to="con_savings", signer="governor")
    protocol.stable_token.mint(amount=tiny, to="bob", signer="governor")
    protocol.stable_token.approve(amount=tiny, to="con_savings", signer="bob")

    assert protocol.savings.preview_deposit(assets=tiny) == 0
    with pytest.raises(AssertionError, match="zero shares"):
        protocol.savings.deposit(assets=tiny, signer="bob")
    assert protocol.stable_token.balance_of(address="bob") == tiny
    assert protocol.stable_token.allowance(owner="bob", spender="con_savings") == tiny
    assert protocol.savings.balance_of(address="bob") == 0
    assert protocol.savings.total_assets() == 2
    assert protocol.savings.total_supply() == 1
