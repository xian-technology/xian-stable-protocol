from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

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
        source=(ROOT / "contracts/con_stable_token.s.py").read_text(),
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
        source=(ROOT / "contracts/con_stable_token.s.py").read_text(),
        args={},
        chi=12345,
    )

    assert deployed is False
    assert contract == {"contract": "con_existing"}
    assert client.deployed is None


@pytest.fixture
def bundle_copy(tmp_path):
    shutil.copy(ROOT / "contract-bundle.json", tmp_path / "contract-bundle.json")
    shutil.copytree(ROOT / "contracts", tmp_path / "contracts")
    return tmp_path / "contract-bundle.json"


def test_plan_uses_bundle_sources_order_and_budgets(bundle_copy, monkeypatch):
    bootstrap = _load_bootstrap_module()
    monkeypatch.delenv("XIAN_STABLE_DEPLOY_CHI", raising=False)
    config = bootstrap._load_config(SimpleNamespace(public_key="a" * 64))
    manifest = json.loads(bundle_copy.read_text())
    manifest["contracts"][1]["deploy_order"] = 1
    manifest["contracts"][1]["default_chi"] = 123456
    bundle_copy.write_text(json.dumps(manifest))
    plan = bootstrap._build_deployment_plan(bundle_copy, config, skip_sample_tokens=True)
    assert plan[0]["name"] == config.oracle_contract_name
    assert plan[0]["chi"] == 123456
    assert len(plan) == 5
    assert plan[0]["source"] == (bundle_copy.parent / manifest["contracts"][1]["path"]).read_text()
    full = bootstrap._build_deployment_plan(bundle_copy, config, skip_sample_tokens=False)
    assert len(full) == 7
    sample = next(item for item in full if item["name"] == config.collateral_contract_name)
    assert sample["args"]["initial_supply"] == config.sample_token_supply
    override = bootstrap._build_deployment_plan(
        bundle_copy, replace(config, deploy_chi=999), skip_sample_tokens=True
    )
    assert all(item["chi"] == 999 for item in override)


@pytest.mark.parametrize("damage", ["hash", "missing_role"])
def test_invalid_bundle_fails_before_client_creation(bundle_copy, monkeypatch, damage):
    bootstrap = _load_bootstrap_module()
    manifest = json.loads(bundle_copy.read_text())
    if damage == "hash":
        source = bundle_copy.parent / manifest["contracts"][-1]["path"]
        source.write_text(source.read_text() + "\n# changed\n")
    else:
        manifest["contracts"].pop()
        bundle_copy.write_text(json.dumps(manifest))
    monkeypatch.setattr(bootstrap, "_require_wallet", lambda: SimpleNamespace(public_key="a" * 64))

    def forbidden_client(*args, **kwargs):
        pytest.fail("must validate all sources before connecting")

    monkeypatch.setattr(bootstrap, "Xian", forbidden_client)
    with pytest.raises(ValueError, match="sha256 mismatch|missing roles"):
        bootstrap.main(["--bundle", str(bundle_copy)])


def test_plan_keeps_exact_validated_source(bundle_copy):
    bootstrap = _load_bootstrap_module()
    config = bootstrap._load_config(SimpleNamespace(public_key="a" * 64))
    plan = bootstrap._build_deployment_plan(bundle_copy, config, skip_sample_tokens=True)
    source = bundle_copy.parent / "contracts/con_stable_token.s.py"
    source.write_text("modified after planning")
    client = FakeClient()
    bootstrap._deploy_contract(client, **plan[0])
    assert client.deployed["source"] == plan[0]["source"]
    assert "def seed(" in client.deployed["source"]
