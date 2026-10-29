from __future__ import annotations

import json
from pathlib import Path

from tools import fetch_docling, fetch_models, license_audit, offline_audit

ROOT = Path(__file__).resolve().parents[1]


def load_lock() -> dict:
    return json.loads((ROOT / "models.lock.json").read_text(encoding="utf-8"))


def test_core_entries_are_selected_for_every_profile() -> None:
    lock = load_lock()
    for entry in lock["entries"]:
        if "core" in entry["profiles"]:
            assert fetch_models.selected(entry, "demo_gpu")
            assert fetch_models.selected(entry, "cpu")
            assert fetch_models.selected(entry, "indic")


def test_profile_selection_is_specific() -> None:
    lock = load_lock()
    qwen = next(e for e in lock["entries"] if e["id"] == "qwen3-4b-instruct-2507")
    phi = next(e for e in lock["entries"] if e["id"] == "phi4-mini-3.8b")
    assert fetch_models.selected(qwen, "demo_gpu")
    assert not fetch_models.selected(qwen, "safe_gpu")
    assert fetch_models.selected(phi, "safe_gpu")


def test_license_audit_has_no_failures() -> None:
    findings = license_audit.audit_models(load_lock())
    failures = [finding for finding in findings if finding.status == "fail"]
    assert not failures, failures


def test_offline_environment_blocks_hub_and_telemetry() -> None:
    env = offline_audit.offline_environment()
    assert env["HF_HUB_OFFLINE"] == "1"
    assert env["TRANSFORMERS_OFFLINE"] == "1"
    assert env["HF_DATASETS_OFFLINE"] == "1"
    assert env["HF_HUB_DISABLE_TELEMETRY"] == "1"


def test_offline_audit_reports_layout_and_models(tmp_path: Path) -> None:
    lock = {
        "profiles": {"core": "shared"},
        "entries": [
            {"id": "present", "profiles": ["core"], "source": {"type": "hf"}},
            {"id": "missing", "profiles": ["core"], "source": {"type": "hf"}},
            {"id": "optional", "profiles": ["indic"], "source": {"type": "hf"}},
        ],
    }

    def verify(entry: dict) -> tuple[bool, str]:
        return (entry["id"] == "present", "local" if entry["id"] == "present" else "absent")

    checks = offline_audit.audit("core", root=tmp_path, lock=lock, verify=verify)
    by_name = {check.name: check for check in checks}

    assert by_name["layout"].status == "fail"
    assert by_name["profile"].status == "ok"
    assert by_name["model:present"].status == "ok"
    assert by_name["model:missing"].status == "fail"
    assert "model:optional" not in by_name


def test_offline_audit_rejects_unknown_profile(tmp_path: Path) -> None:
    lock = {"profiles": {"core": "shared"}, "entries": []}
    checks = offline_audit.audit("nope", root=tmp_path, lock=lock, verify=lambda _: (True, "ok"))
    assert any(check.name == "profile" and check.status == "fail" for check in checks)


def test_docling_manifest_round_trip(tmp_path: Path) -> None:
    for spec in fetch_docling.SPECS:
        for required in spec.required:
            target = tmp_path / spec.folder / required
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"artifact")
    manifest_path = tmp_path / ".medha_docling.json"
    assert fetch_docling.verify(tmp_path) == [f"manifest missing: {manifest_path}"]
    fetch_docling.write_manifest(tmp_path)
    assert fetch_docling.verify(tmp_path) == []

    missing = tmp_path / fetch_docling.SPECS[0].folder / fetch_docling.SPECS[0].required[0]
    missing.unlink()
    assert any("missing" in problem for problem in fetch_docling.verify(tmp_path))
