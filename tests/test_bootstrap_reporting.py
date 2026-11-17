"""Operator reports use the contract's resolved clock/debt projection."""

from __future__ import annotations

import importlib.util
import sys
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest


def load_bootstrap():
    path = Path(__file__).absolute().parents[1] / "scripts/bootstrap_protocol.py"
    spec = importlib.util.spec_from_file_location("bootstrap_reporting", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ProjectionClient:
    def __init__(self, projection):
        self.projection = projection
        self.raw_reads = []
        self.calls = []

    def get_state(self, contract, variable, *keys):
        self.raw_reads.append((contract, variable, keys))
        return {"stability_fee_bps": 200, "rate_accumulator": 1, "principal_outstanding": 0}.get(
            keys[-1]
        )

    def contract(self, name):
        assert name == "con_vaults"
        return SimpleNamespace(call=self.call)

    def call(self, function, **kwargs):
        self.calls.append((function, kwargs))
        return self.projection


@pytest.mark.parametrize("pending", [False, True])
def test_report_uses_effective_fee_rate_and_full_principal_without_raw_clock_fields(pending):
    projection = {
        "stability_fee_bps": 200 if pending else 500,
        "pending_stability_fee_bps": 500 if pending else None,
        "pending_fee_height": 100 if pending else None,
        "rate_accumulator": Decimal("1.000000000000000000000001"),
        "live_normalized_debt_total": Decimal("1.25"),
        "live_principal_outstanding": 9007199254740993,
        "pending_debt_outstanding": 9007199254740993,
        "pending_debt_height": 101,
    }
    client = ProjectionClient(projection)
    snapshot = load_bootstrap()._snapshot_vault_type(client, "con_vaults", 7)
    assert snapshot["stability_fee_bps"] == projection["stability_fee_bps"]
    assert snapshot["rate_accumulator"] == projection["rate_accumulator"]
    assert snapshot["pending_fee_height"] == projection["pending_fee_height"]
    assert snapshot["principal_outstanding"] == projection["live_principal_outstanding"]
    assert snapshot["normalized_debt_total"] == projection["live_normalized_debt_total"]
    assert snapshot["pending_debt_outstanding"] == projection["pending_debt_outstanding"]
    assert client.calls == [("get_vault_type", {"vault_type_id": 7})]
    assert not client.raw_reads
    assert "principal_outstanding" not in projection


@pytest.mark.parametrize("projection", [None, [], "pending"])
def test_invalid_projection_fails_instead_of_falling_back_to_stale_storage(projection):
    with pytest.raises(RuntimeError, match="get_vault_type.*object"):
        load_bootstrap()._snapshot_vault_type(ProjectionClient(projection), "con_vaults", 7)
