# Medha

Medha is an offline AI blackboard teacher. It generates a structured lesson, draws it on a
chalkboard, narrates it, and pauses for checkpoints. Everything runs on the local machine:
no cloud API, no account, and no network access at demo time.

The source of truth for a lesson is a JSON file that conforms to
`spec/board-action/v1/lesson.schema.json`. SQLite (`data/medha.db`) is only an index and
history store; deleting it does not delete lessons.

## Requirements

- Windows 10/11
- Python 3.12
- [Ollama](https://ollama.com/download) for lesson generation
- A GPU is optional. The default profile uses Ollama on the GPU and CPU-only helpers.
- About 15 GB free disk for the full demo model set.

Medha is currently tested with Python 3.12.15 on Windows.

## First-time setup

Run PowerShell from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

This creates `.venv`, installs the requirements, starts Ollama, downloads the models
for the `demo_gpu` profile, fetches the Docling artifacts, and runs health checks.

Choose a different model profile or skip downloads:

```powershell
.\scripts\setup.ps1 -Profile cpu
.\scripts\setup.ps1 -SkipModels
.\scripts\setup.ps1 -WithIndic
```

`-WithIndic` is optional and installs the Hindi/Kannada translation stack. The Indic models
are gated: accept their terms on Hugging Face, set `HF_TOKEN`, then run
`python tools/fetch_models.py --profile indic`. Audio remains English for now. Without them,
English lessons still work and translation falls back to English with a visible warning.

Models are fetched, never committed. `models.lock.json` pins revisions and licenses;
`MODEL_LICENSES/` contains the generated sidecars. See `MODELS.md`.

## Launch

```powershell
.\scripts\launch.ps1
```

The Studio opens on the Create tab. Enter a topic, choose a language, and generate a lesson.
Library and Settings tabs provide saved lessons, favorites, checkpoint history, and saved
preferences.

Useful variants:

```powershell
.\scripts\launch.ps1 -NoTTS
.\scripts\launch.ps1 -Health
.\scripts\launch.ps1 -Lesson .\content\lessons\newton.json
```

The same entry points work without PowerShell wrappers:

```powershell
.\.venv\Scripts\python.exe -m medha
.\.venv\Scripts\python.exe -m medha --health
.\.venv\Scripts\python.exe -m medha --version
```

## Demo

```powershell
.\scripts\demo.ps1
```

This opens the retained Newton's Second Law lesson. It is useful when generation is slow or
when showing the board, narration, and checkpoints before generating a new topic.

## Offline verification

```powershell
.\scripts\offline.ps1 -AuditOnly
.\scripts\offline.ps1
```

The audit checks the application layout, the model lock, and every model required by the
selected profile. The launcher sets `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, and related
telemetry-off variables. Once models are present, a demo can run with the network disabled.

## Full verification

```powershell
.\scripts\verify.ps1
```

Runs `ruff`, `mypy`, `pytest`, `pip check`, the license audit, environment health checks, and
the offline audit. Use `-SkipTests`, `-SkipHealth`, or `-Strict` to adjust the run.

Tests can also be run directly:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy medha tests tools
```

## Languages

The Studio supports English, Hindi, and Kannada labels. English generation uses the local
Qwen model and Kokoro speech. Hindi and Kannada translation is available when the optional
IndicTrans2 models are installed, but narration intentionally stays on English Kokoro audio
for now; Indic speech is deferred. Without the translation models, Medha keeps the English
lesson and reports why translation was unavailable.

Translated lessons keep the original step/action IDs, coordinates, timings, and checkpoint
anchors. The translated `lesson_id` gets a `-hi` or `-kn` suffix so both versions can coexist
in the library. Voice input/ASR is not enabled in this version.

## Project layout

```text
medha/            application and CLI modules
spec/             board-action and lesson JSON schemas
content/lessons/  retained and generated lesson files
assets/           fonts, symbols, and voices
models/           fetched model weights (not committed)
MODEL_LICENSES/   license sidecars for fetched models
tools/            model fetcher, audits, ingest fixtures
scripts/          PowerShell setup, launch, demo, verify, offline wrappers
data/             SQLite index, caches, uploads, generated images
```

## Troubleshooting

**Ollama is unreachable.** Run `ollama serve`, then `.\scripts\launch.ps1`. Health checks
report the current endpoint.

**Generation works but speech is silent.** Check the Settings tab and the TTS cache. A
missing Kokoro model or audio device falls back to silent playback with a warning.

**Hindi or Kannada translation is unavailable.** Install `requirements\indic.txt`, accept the
gated model terms, set `HF_TOKEN`, and fetch the `indic` profile. Narration stays in English
for now.

**Reranker loading fails.** The BGE reranker loads with a low-memory path, but a very tight
Windows commit limit can still reject it. Medha then keeps vector-only retrieval as a
fallback; disable reranking in Settings if needed.

**A board action was dropped.** Invalid actions from the LLM are rejected by schema repair
and reported as warnings rather than breaking playback.

## Packaging

Medha is portable as a folder containing the source, `.venv`, `models/`, and `data/`. Copy
the folder, run `scripts\setup.ps1` once on the target machine if Python or models are
missing, then use `scripts\launch.ps1`. PyInstaller is intentionally not used because the
model runtimes and OpenGL renderer are large and easier to diagnose in a normal environment.

## Licenses

Code and specification are Apache-2.0. Lesson content is CC-BY-4.0. Fetched model licenses
are recorded in `MODEL_LICENSES/` and summarized in `MODELS.md`; third-party notices are in
`THIRD_PARTY_NOTICES.md`.
