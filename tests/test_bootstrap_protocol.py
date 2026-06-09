from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("xian_py")

ROOT = Path(__file__).resolve().parents[1]


def _load_bootstrap_module():
    path = ROOT / "scripts" / "bootstrap_protocol.py"
    spec = importlib.util.spec_from_file_location("bootstrap_protocol", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeClient:
    def __init__(self, *, existing_source: str | None = None):
        self.existing_source = existing_source
        self.deployed: dict | None = None
        self.contracts: list[str] = []

    def get_contract_source(self, name: str) -> str | None:
        return self.existing_source

    def deploy_contract(
        self,
        *,
        name: str,
        source: str,
        args: dict,
        chi: int,
        mode: str,
        wait_for_tx: bool,
    ):
        self.deployed = {
            "name": name,
            "source": source,
            "args": args,
            "chi": chi,
            "mode": mode,
            "wait_for_tx": wait_for_tx,
        }
        return SimpleNamespace(
            submitted=True,
            accepted=True,
            finalized=True,
            receipt=None,
            message=None,
            tx_hash="ABC123",
        )

    def submit_contract(self, *args, **kwargs):
        raise AssertionError("bootstrap should use deploy_contract with current xian-py")

    def contract(self, name: str):
        self.contracts.append(name)
        return {"contract": name}


def test_deploy_contract_uses_current_xian_py_deploy_api():
    bootstrap = _load_bootstrap_module()
    client = FakeClient()

    contract, deployed = bootstrap._deploy_contract(
        client,
        name="con_bootstrap_smoke",
        source_file="stable_token.s.py",
        args={"token_name": "Smoke", "token_symbol": "SMK"},
        chi=12345,
    )

    assert deployed is True
    assert contract == {"contract": "con_bootstrap_smoke"}
    assert client.deployed is not None
    assert client.deployed["name"] == "con_bootstrap_smoke"
    assert "def seed(" in client.deployed["source"]
    assert client.deployed["args"] == {"token_name": "Smoke", "token_symbol": "SMK"}
    assert client.deployed["chi"] == 12345
    assert client.deployed["mode"] == "checktx"
    assert client.deployed["wait_for_tx"] is True


def test_deploy_contract_skips_existing_contract():
    bootstrap = _load_bootstrap_module()
    client = FakeClient(existing_source="already deployed")

    contract, deployed = bootstrap._deploy_contract(
        client,
        name="con_existing",
        source_file="stable_token.s.py",
        args={},
        chi=12345,
    )

    assert deployed is False
    assert contract == {"contract": "con_existing"}
    assert client.deployed is None
