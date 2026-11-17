"""Bootstrap refuses to deploy against an absent or inactive chain clock."""

from types import SimpleNamespace

import pytest
from test_bootstrap_protocol import _load_bootstrap_module


@pytest.mark.parametrize(
    ("source", "owner", "version", "ready"),
    [
        (None, None, 1, True),
        ("source", "operator", 1, True),
        ("source", None, True, True),
        ("source", None, 2, True),
        ("source", None, 1, 1),
        ("source", None, 1, False),
    ],
)
def test_bootstrap_requires_immutable_protocol_one_and_ready_keeper(source, owner, version, ready):
    bootstrap = _load_bootstrap_module()
    state = {"__owner__": owner, "protocol_version": version, "keeper_ready": ready}
    client = SimpleNamespace(
        get_contract_source=lambda name: source,
        get_state=lambda name, variable: state[variable],
    )
    with pytest.raises(RuntimeError, match="time_checkpoints"):
        bootstrap._ensure_time_checkpoints(client)


def test_bootstrap_accepts_chain_checkpoint_service():
    bootstrap = _load_bootstrap_module()
    state = {"__owner__": None, "protocol_version": 1, "keeper_ready": True}
    client = SimpleNamespace(
        get_contract_source=lambda name: "source",
        get_state=lambda name, variable: state[variable],
    )
    bootstrap._ensure_time_checkpoints(client)


def test_main_checks_checkpoint_service_before_any_deployment(monkeypatch):
    from contextlib import nullcontext

    bootstrap = _load_bootstrap_module()
    monkeypatch.setattr(bootstrap, "_require_wallet", lambda: SimpleNamespace(public_key="a" * 64))
    client = SimpleNamespace(get_contract_source=lambda name: None)
    monkeypatch.setattr(bootstrap, "Xian", lambda *args, **kwargs: nullcontext(client))
    with pytest.raises(RuntimeError, match="time_checkpoints.*missing"):
        bootstrap.main([])


@pytest.mark.parametrize(
    ("skip", "missing"), [(False, None), (True, None), (True, "con_reserve_token")]
)
def test_bootstrap_checks_existing_sample_tokens_only_when_requested(skip, missing):
    bootstrap = _load_bootstrap_module()
    calls = []

    def source(name):
        calls.append(name)
        return None if name == missing else "source"

    config = SimpleNamespace(
        collateral_contract_name="con_collateral_token", reserve_contract_name="con_reserve_token"
    )
    client = SimpleNamespace(get_contract_source=source)
    if missing:
        with pytest.raises(RuntimeError, match=missing):
            bootstrap._ensure_sample_tokens(client, config, skip_sample_tokens=skip)
    else:
        bootstrap._ensure_sample_tokens(client, config, skip_sample_tokens=skip)
    assert calls == (["con_collateral_token", "con_reserve_token"] if skip else [])


def test_bootstrap_operator_identity_and_quorum_warning(monkeypatch, capsys):
    bootstrap = _load_bootstrap_module()
    monkeypatch.setattr(bootstrap, "_require_wallet", lambda: SimpleNamespace(public_key="a" * 64))
    args = SimpleNamespace(bundle=bootstrap.DEFAULT_BUNDLE, skip_sample_tokens=True)
    monkeypatch.setenv("XIAN_STABLE_GOVERNOR", "b" * 64)
    with pytest.raises(RuntimeError, match="wallet must match"):
        bootstrap._prepare_bootstrap(args)
    monkeypatch.setenv("XIAN_STABLE_GOVERNOR", "a" * 64)
    monkeypatch.setenv("XIAN_STABLE_MIN_REPORTERS_REQUIRED", "2")
    _, config, plan = bootstrap._prepare_bootstrap(args)
    assert config.min_reporters_required == 2 and len(plan) == 5
    assert "Additional reporters must submit" in capsys.readouterr().err


@pytest.mark.parametrize(
    "failure", ["not_submitted", "rejected", "not_finalized", "receipt_failed"]
)
def test_bootstrap_stops_on_an_unsuccessful_write(failure):
    bootstrap = _load_bootstrap_module()
    value = SimpleNamespace(
        submitted=True, accepted=True, finalized=True, receipt=None, message="failed"
    )
    if failure == "not_submitted":
        value.submitted = False
    if failure == "rejected":
        value.accepted = False
    if failure == "not_finalized":
        value.finalized = False
    if failure == "receipt_failed":
        value.receipt = SimpleNamespace(success=False, message="failed")
    with pytest.raises(RuntimeError, match="failed|rejected|submitted|finalized"):
        bootstrap._ensure_submission_succeeded(value, "bootstrap write")


def test_single_reporter_bootstrap_does_not_claim_more_reports_are_needed(monkeypatch, capsys):
    bootstrap = _load_bootstrap_module()
    monkeypatch.setattr(bootstrap, "_require_wallet", lambda: SimpleNamespace(public_key="a" * 64))
    monkeypatch.setenv("XIAN_STABLE_MIN_REPORTERS_REQUIRED", "1")
    args = SimpleNamespace(bundle=bootstrap.DEFAULT_BUNDLE, skip_sample_tokens=True)
    bootstrap._prepare_bootstrap(args)
    assert capsys.readouterr().err == ""
