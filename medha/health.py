"""Environment health check.

Run with:
    python -m medha.health
    python -m medha.health --json
    python -m medha.health --strict
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from typing import Any, Literal

import httpx
import psutil

import config

Status = Literal["ok", "warn", "skip", "fail"]

STATUS_RANK: dict[Status, int] = {"ok": 0, "warn": 1, "skip": 2, "fail": 3}


@dataclass
class Check:
    name: str
    status: Status
    detail: str
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _module_present(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _run(cmd: list[str], timeout: float = 8.0) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        return proc.returncode, (proc.stdout or proc.stderr or "").strip()
    except FileNotFoundError:
        return 127, f"{cmd[0]} not found"
    except subprocess.TimeoutExpired:
        return 124, f"{cmd[0]} timed out"
    except OSError as exc:
        return 1, str(exc)


def check_python() -> Check:
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info < (3, 12):  # noqa: UP036 - explicit runtime guard
        return Check("python", "fail", f"{version}; Medha needs >= 3.12")
    return Check("python", "ok", version)


def check_venv() -> Check:
    if sys.prefix == sys.base_prefix:
        return Check("venv", "fail", "not running inside .venv")
    return Check("venv", "ok", sys.prefix)


def check_paths() -> Check:
    config.ensure_dirs()
    missing = [str(p) for p in config.DIRECTORIES if not p.exists()]
    if missing:
        return Check("paths", "fail", f"missing: {', '.join(missing[:3])}")
    probe = config.DATA_DIR / ".write_probe"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return Check("paths", "fail", f"data dir not writable: {exc}")
    return Check("paths", "ok", str(config.ROOT))


def check_config() -> Check:
    try:
        summary = config.as_dict()
    except Exception as exc:  # pragma: no cover - defensive
        return Check("config", "fail", f"cannot load: {exc}")
    profile = summary["profile"]
    return Check("config", "ok", f"profile={profile} llm={summary['llm']}")


def check_lockfile() -> Check:
    path = config.MODEL_LOCK_PATH
    if not path.exists():
        return Check("model_lock", "fail", f"{path.name} missing")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return Check("model_lock", "fail", f"cannot parse: {exc}")

    entries = data.get("entries") or []
    if not entries:
        return Check("model_lock", "fail", "no entries")

    problems: list[str] = []
    for entry in entries:
        eid = entry.get("id", "<unknown>")
        for key in ("id", "job", "profiles", "source", "license"):
            if key not in entry:
                problems.append(f"{eid}: missing {key}")
        source = entry.get("source") or {}
        if source.get("type") == "hf":
            if not source.get("repo") or not source.get("revision"):
                problems.append(f"{eid}: unpinned hf source")
        elif source.get("type") == "ollama":
            if not source.get("model"):
                problems.append(f"{eid}: missing ollama model")
        else:
            problems.append(f"{eid}: unknown source type")
        lic_file = entry.get("license_file")
        if lic_file and not (config.LICENSES_DIR / lic_file).exists():
            problems.append(f"{eid}: license file missing ({lic_file})")

    if problems:
        return Check("model_lock", "fail", "; ".join(problems[:4]))
    gated = sum(1 for e in entries if e.get("gated"))
    return Check("model_lock", "ok", f"{len(entries)} entries, {gated} gated")


def check_licenses() -> Check:
    needed = [
        "Apache-2.0.txt",
        "MIT.txt",
        "CC-BY-4.0.txt",
        "LGPL-3.0-only.txt",
        "Community-Data-License-Agreement-Permissive-2.0.txt",
        "Llama-3.2-Community.txt",
    ]
    missing = [n for n in needed if not (config.LICENSES_DIR / n).exists()]
    if missing:
        return Check("licenses", "fail", f"missing: {', '.join(missing)}")
    return Check("licenses", "ok", f"{len(needed)} texts present")


def check_ollama() -> Check:
    url = config.OLLAMA_BASE_URL.rstrip("/")
    try:
        with httpx.Client(timeout=3.0) as client:
            tags = client.get(f"{url}/api/tags").json()
            version = client.get(f"{url}/api/version").json().get("version", "?")
    except Exception as exc:
        return Check(
            "ollama",
            "fail",
            f"unreachable at {url} ({type(exc).__name__}). Run: ollama serve",
        )

    models = [m.get("name", "") for m in tags.get("models", [])]
    wanted = config.active_llm().model
    normalized = {m if ":" in m else f"{m}:latest" for m in models}
    if wanted not in normalized:
        return Check(
            "ollama",
            "warn",
            f"v{version}; model {wanted} not pulled (ollama pull {wanted})",
        )
    return Check("ollama", "ok", f"v{version}; {len(models)} model(s); {wanted} ready")


def check_gpu() -> Check:
    if config.CPU_ONLY:
        return Check("gpu", "skip", "MEDHA_CPU_ONLY=1")
    code, out = _run(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total,memory.free,driver_version",
            "--format=csv,noheader,nounits",
        ]
    )
    if code != 0:
        return Check("gpu", "fail", out)
    first = out.splitlines()[0]
    parts = [p.strip() for p in first.split(",")]
    if len(parts) < 4:
        return Check("gpu", "warn", first)
    name, total, free, driver = parts[:4]
    try:
        free_gb = float(free) / 1024
        total_gb = float(total) / 1024
    except ValueError:
        return Check("gpu", "warn", first)
    if free_gb < config.VRAM_MIN_FREE_GB:
        return Check(
            "gpu",
            "warn",
            f"{name}: {free_gb:.1f}/{total_gb:.1f} GB free; close browser/GPU apps",
        )
    return Check("gpu", "ok", f"{name}: {free_gb:.1f}/{total_gb:.1f} GB free; driver {driver}")


def check_compute_apps() -> Check:
    if config.CPU_ONLY:
        return Check("gpu_users", "skip", "CPU-only mode")
    code, out = _run(
        [
            "nvidia-smi",
            "--query-compute-apps=pid,process_name,used_memory",
            "--format=csv,noheader,nounits",
        ]
    )
    if code != 0:
        return Check("gpu_users", "skip", out)
    lines = [
        line
        for line in out.splitlines()
        if line.strip() and "N/A" not in line
    ]
    if not lines:
        return Check("gpu_users", "ok", "no active compute processes")
    detail = " | ".join(lines[:4])
    if any("ollama" not in line.lower() for line in lines):
        return Check("gpu_users", "warn", f"non-Ollama VRAM users: {detail}")
    return Check("gpu_users", "ok", detail)


def check_resources() -> Check:
    ram_gb = psutil.virtual_memory().total / 1e9
    swap_gb = psutil.swap_memory().total / 1e9
    free_gb = shutil.disk_usage(config.ROOT).free / 1e9
    status: Status = "ok"
    notes: list[str] = [
        f"RAM {ram_gb:.1f} GB",
        f"pagefile {swap_gb:.1f} GB",
        f"disk free {free_gb:.1f} GB",
    ]
    if ram_gb < 12:
        status = "warn"
        notes.append("16 GB+ recommended")
    if swap_gb < 1:
        status = "warn"
        notes.append("pagefile disabled; RAG models may hit native out-of-memory")
    if free_gb < 10:
        status = "warn"
        notes.append("need ~8 GB for the English demo")
    return Check("resources", status, "; ".join(notes))


OPTIONAL: tuple[tuple[str, str], ...] = (
    ("PySide6", "B2 renderer"),
    ("OpenGL", "B2 renderer"),
    ("matplotlib", "B3 math paths"),
    ("kokoro", "B4 TTS"),
    ("sounddevice", "B4 audio"),
    ("docling", "B5 ingestion"),
    ("pptx", "B5 pptx"),
    ("pdfplumber", "B5 pdf"),
    ("chromadb", "B6 retrieval"),
    ("onnxruntime", "B6 retrieval"),
    ("transformers", "B7 image descriptions"),
)


def check_optional_deps() -> Check:
    present = [name for name, _ in OPTIONAL if _module_present(name)]
    missing = [f"{name} ({batch})" for name, batch in OPTIONAL if name not in present]
    if len(present) == 0:
        return Check(
            "deps",
            "skip",
            "layer packages not installed yet; first missing: " + ", ".join(missing[:3]),
        )
    if missing:
        return Check("deps", "skip", f"{len(present)}/{len(OPTIONAL)} present; next: {missing[0]}")
    return Check("deps", "ok", f"all {len(OPTIONAL)} optional modules present")


def check_ingest_artifacts() -> Check:
    if not _module_present("docling"):
        return Check("docling_artifacts", "skip", "Docling not installed yet (B5)")
    from medha.ingest.docling_parser import missing_artifacts

    problems = missing_artifacts()
    if problems:
        return Check(
            "docling_artifacts",
            "fail",
            "; ".join(problems) + ". Run: python tools/fetch_docling.py",
        )
    return Check("docling_artifacts", "ok", str(config.DOCLING_ARTIFACTS_DIR))


def check_rag_artifacts() -> Check:
    if not _module_present("chromadb") or not _module_present("onnxruntime"):
        return Check("rag_artifacts", "skip", "retrieval dependencies not installed (B6)")
    required = (
        config.EMBED_ONNX_PATH,
        config.EMBED_ONNX_PATH.with_name("model.onnx_data"),
        config.EMBED_TOKENIZER_PATH,
        config.RERANKER_DIR / "config.json",
        config.RERANKER_DIR / "model.safetensors",
        config.RERANKER_DIR / "tokenizer.json",
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        return Check(
            "rag_artifacts",
            "fail",
            "missing: " + ", ".join(missing[:3]) + ". Run: python tools/fetch_models.py",
        )
    return Check("rag_artifacts", "ok", f"{config.EMBED_MODEL_ID} + {config.RERANKER_MODEL_ID}")


def check_image_artifacts() -> Check:
    if not _module_present("transformers") or not _module_present("torch"):
        return Check("image_artifacts", "skip", "VLM dependencies not installed (B7)")
    required = (
        config.VLM_MODEL_DIR / "config.json",
        config.VLM_MODEL_DIR / "model.safetensors",
        config.VLM_MODEL_DIR / "processor_config.json",
        config.VLM_MODEL_DIR / "preprocessor_config.json",
        config.VLM_MODEL_DIR / "tokenizer.json",
        config.VLM_MODEL_DIR / "tokenizer_config.json",
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        return Check(
            "image_artifacts",
            "fail",
            "missing: "
            + ", ".join(missing[:3])
            + ". Run: python tools/fetch_models.py --profile core",
        )
    return Check("image_artifacts", "ok", config.VLM_MODEL_ID)


def check_cuda_torch() -> Check:
    if not _module_present("torch"):
        return Check("torch", "skip", "not installed yet (B4/B5)")
    try:
        from importlib.metadata import version

        meta = version("torch")
    except Exception:
        return Check("torch", "warn", "torch installed but version unknown")
    if "+cu" in meta.lower():
        return Check(
            "torch",
            "warn",
            f"CUDA torch {meta}; install requirements/cpu.txt to protect VRAM",
        )
    return Check("torch", "ok", meta)


def run_all() -> list[Check]:
    checks = [
        check_python(),
        check_venv(),
        check_paths(),
        check_config(),
        check_lockfile(),
        check_licenses(),
        check_ollama(),
        check_gpu(),
        check_compute_apps(),
        check_resources(),
        check_optional_deps(),
        check_ingest_artifacts(),
        check_rag_artifacts(),
        check_image_artifacts(),
        check_cuda_torch(),
    ]
    return checks


def _print_table(checks: list[Check]) -> None:
    from rich.console import Console
    from rich.table import Table

    colors = {"ok": "green", "warn": "yellow", "skip": "dim", "fail": "red"}
    table = Table(title=f"{config.APP_NAME} health", show_lines=False)
    table.add_column("check", style="bold")
    table.add_column("status")
    table.add_column("detail", overflow="fold")
    for check in checks:
        color = colors.get(check.status, "white")
        table.add_row(check.name, f"[{color}]{check.status}[/{color}]", check.detail)
    Console().print(table)

    fails = sum(1 for c in checks if c.status == "fail")
    warns = sum(1 for c in checks if c.status == "warn")
    skips = sum(1 for c in checks if c.status == "skip")
    print(
        f"\n{len(checks)} checks: "
        f"{len(checks) - fails - warns - skips} ok, {warns} warn, {skips} skip, {fails} fail"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="medha-health", description=__doc__)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--strict", action="store_true", help="warnings are failures")
    args = parser.parse_args(argv)

    checks = run_all()
    if args.json:
        print(json.dumps([c.to_dict() for c in checks], indent=2))
    else:
        _print_table(checks)

    failures = [c for c in checks if c.status == "fail" and c.required]
    if args.strict:
        failures += [c for c in checks if c.status == "warn"]
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
