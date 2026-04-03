import pytest


def test_psm_mint_and_redeem_apply_fees(protocol):
    protocol.reserve_token.approve(amount=100, to="psm", signer="alice")

    mint_quote = protocol.psm.mint_stable(reserve_amount=100, signer="alice")
    protocol.stable_token.approve(amount=50, to="psm", signer="alice")
    redeem_quote = protocol.psm.redeem_stable(stable_amount=50, signer="alice")

    assert mint_quote["stable_out"] == pytest.approx(99)
    assert mint_quote["fee"] == pytest.approx(1)
    assert redeem_quote["reserve_out"] == pytest.approx(49.75)
    assert redeem_quote["fee"] == pytest.approx(0.25)
    assert protocol.stable_token.balance_of(account="alice") == pytest.approx(49)
    assert protocol.reserve_token.balance_of(account="alice") == pytest.approx(949.75)
    assert protocol.reserve_token.balance_of(account="treasury") == pytest.approx(1.25)
    assert protocol.psm.get_state()["reserve_balance"] == pytest.approx(49)


def test_psm_pause_blocks_mint_and_redeem(protocol):
    protocol.psm.set_paused(value=True, signer="governor")
    protocol.reserve_token.approve(amount=10, to="psm", signer="alice")

    with pytest.raises(AssertionError):
        protocol.psm.mint_stable(reserve_amount=10, signer="alice")
