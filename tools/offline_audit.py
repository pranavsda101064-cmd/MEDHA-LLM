"""Offline readiness audit.

Examples:
    python tools/offline_audit.py
    python tools/offline_audit.py --profile demo_gpu
    python tools/offline_audit.py --json --strict
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from tools import fetch_models  # noqa: E402

Status = Literal["ok", "warn", "fail"]
Verify = Callable[[dict[str, Any]], tuple[bool, str]]

REQUIRED_PATHS = (
    "config.py",
    "models.lock.json",
    "medha/__main__.py",
    "spec/board-action/v1/lesson.schema.json",
    "content/lessons/newton.json",
    "assets/fonts/hershey.json",
)


@dataclass
class Check:
    name: str
    status: Status
    detail: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def offline_environment() -> dict[str, str]:
    """Environment variables that stop Hugging Face and telemetry traffic."""
    return {
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "HF_DATASETS_OFFLINE": "1",
        "HF_HUB_DISABLE_TELEMETRY": "1",
        "DO_NOT_TRACK": "1",
    }


def check_layout(root: Path = config.ROOT) -> Check:
    missing = [name for name in REQUIRED_PATHS if not (root / name).exists()]
    if missing:
        return Check("layout", "fail", f"missing: {', '.join(missing[:3])}")
    return Check("layout", "ok", str(root))


def _load_lock(root: Path) -> tuple[Check, dict[str, Any] | None]:
    path = root / "models.lock.json"
    try:
        lock = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return Check("model_lock", "fail", f"cannot read models.lock.json: {exc}"), None
    if not isinstance(lock.get("entries"), list):
        return Check("model_lock", "fail", "models.lock.json has no entries list"), None
    return Check("model_lock", "ok", f"{len(lock['entries'])} entries"), lock


def check_models(
    profile: str,
    entries: list[dict[str, Any]],
    verify: Verify = fetch_models.verify_entry,
) -> list[Check]:
    checks: list[Check] = []
    selected = [entry for entry in entries if fetch_models.selected(entry, profile)]
    if not selected:
        return [Check("models", "fail", f"no models selected for profile {profile}")]
    for entry in selected:
        model_id = str(entry.get("id") or "unknown")
        try:
            ok, detail = verify(entry)
        except Exception as exc:  # pragma: no cover - defensive
            ok, detail = False, f"verification crashed: {exc}"
        checks.append(Check(f"model:{model_id}", "ok" if ok else "fail", detail))
    return checks


def audit(
    profile: str | None = None,
    *,
    root: Path = config.ROOT,
    lock: dict[str, Any] | None = None,
    verify: Verify = fetch_models.verify_entry,
) -> list[Check]:
    profile = profile or config.DEFAULT_PROFILE
    checks = [check_layout(root)]
    if lock is None:
        lock_check, lock = _load_lock(root)
        checks.append(lock_check)
    if lock is None:
        return checks
    if profile not in fetch_models.profile_names(lock):
        checks.append(Check("profile", "fail", f"unknown profile {profile!r}"))
        return checks
    checks.append(Check("profile", "ok", profile))
    checks.extend(check_models(profile, fetch_models.all_entries(lock), verify))
    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="offline-audit", description=__doc__)
    parser.add_argument("--profile", default=config.DEFAULT_PROFILE)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--strict", action="store_true", help="warnings are failures")
    args = parser.parse_args(argv)

    checks = audit(args.profile)
    if args.json:
        print(json.dumps([check.to_dict() for check in checks], indent=2))
    else:
        for check in checks:
            print(f"  {check.status.upper():<4} {check.name}: {check.detail}")
    failures = [check for check in checks if check.status == "fail"]
    if args.strict:
        failures += [check for check in checks if check.status == "warn"]
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
