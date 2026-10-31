# Medha — Project Context

## What it does

Medha is an **offline AI blackboard teacher** for Windows. Given a topic (and optionally a PDF or PPTX), it:

- Writes a structured lesson script,
- Draws it on a simulated chalkboard,
- Narrates it with local speech,
- Pauses at checkpoints/questions.

Everything runs locally: no cloud API, no account, and no network access at demo time. The lesson JSON in `content/lessons/` is the source of truth; SQLite (`data/medha.db`) is only an index and history store, so deleting it does not delete lessons.

Core design idea: **the LLM never draws pixels.** It emits semantic actions (`write_text`, `write_math`, `draw`, `highlight`, `pause`, etc.) in normalized `(0,0)`–`(1,1)` coordinates. The renderer owns all geometry.

---

## How it works

```text
Topic / PDF
   │
   ├─ RETRIEVE    Docling parses PDF/PPT → chunks → BGE-M3 embeddings → Chroma
   │              → BGE reranker → top 5 excerpts
   │
   ├─ GENERATE    Ollama + Qwen3-4B → JSON outline → JSON steps
   │              → schema-constrained → sanitize → repair → validate → layout fix
   │
   ├─ TRANSLATE   English → Hindi/Kannada (optional, IndicTrans2; math protected)
   │
   ├─ SPEAK       Kokoro-82M per sentence, cached WAVs
   │
   ├─ TIME        Sentence/audio durations → timeline; audio is the master clock
   │
   ├─ DRAW        Semantic actions → Hershey vector strokes → chalk jitter → OpenGL
   │
   └─ PLAY        PySide6 desktop Studio; progressive playback as steps finish
```

### Pipeline detail

1. **Ingestion (optional).** Docling parses PDF/PPTX into normalized blocks. Text is chunked to ~450 tokens with 64-token overlap.
2. **Retrieval.** BGE-M3 embeds chunks into 1024-dim vectors stored in ChromaDB. A query retrieves 20 candidates, and the BGE reranker selects the best 5. Excerpt text is capped at 3200 chars.
3. **Generation.** Ollama runs the active LLM with a compact JSON schema. The response is sanitized (Unicode fixes), repaired (clamped rects, dropped bad anchors/targets, renamed duplicate IDs), validated with Pydantic, and layout-repaired.
4. **Translation (optional).** IndicTrans2 translates prose while masking equations/units/LaTeX. Action IDs, coordinates, timings, and checkpoint anchors are preserved.
5. **Speech.** Kokoro synthesizes each narration sentence independently and caches WAVs in `data/cache/tts/`.
6. **Timing.** The timeline resolves anchors and distributes unanchored actions. The audio clock is authoritative.
7. **Rendering.** Hershey vector font, procedural chalk wobble, matplotlib mathtext for equations, OpenGL 3.3 at 1280×720.
8. **Storage.** Lesson JSON is canonical; SQLite indexes lessons, checkpoints, materials, and settings.

---

## Models used

Model inventory is pinned in `models.lock.json` and summarized in `MODELS.md`. Weights are downloaded, never committed; licenses are recorded in `MODEL_LICENSES/`.

### Brain — LLM (lesson writer)

| Model | Type | Why | Profile |
|---|---|---|---|
| **Qwen3-4B-Instruct-2507** (`qwen3:4b-instruct-2507-q4_K_M`) | Transformer LLM, 4B params, 4-bit | Default; good JSON following, Apache-2.0, ~3 GB VRAM | `demo_gpu` |
| **Phi-4-mini-3.8B** | Transformer LLM, 3.8B params | VRAM-safe fallback, MIT | `safe_gpu` |
| **Llama-3.2-3B** | Transformer LLM, 3B params | CPU-only fallback | `cpu` |

Key settings: context 3072/4096/2048, temperature 0.3, top-p 0.9, repeat penalty 1.05, seed 42, max 1200 output tokens. Ollama uses flash attention, q8 KV cache, one loaded model, and a 15-minute keep-alive.

### Librarian — Retrieval / RAG

| Model | Type | Why |
|---|---|---|
| **BGE-M3** | Bi-encoder embedding model, ONNX, 1024-dim, multilingual | Semantic search over uploaded material, CPU, MIT |
| **BGE reranker v2-m3** | Cross-encoder, torch CPU | Re-ranks top 20 vector hits → best 5, Apache-2.0 |

Reranking only runs when the index has at least 50 chunks. Out-of-memory falls back to vector-only search with a warning.

### Eyes — Image understanding

| Model | Type | Why |
|---|---|---|
| **SmolVLM-500M-Instruct** | Vision-language model | Captions diagrams/figures, CPU, Apache-2.0. Currently infrastructure only; generated lessons do not use image actions yet. |

### Voice — TTS

| Model | Type | Why |
|---|---|---|
| **Kokoro-82M** | Neural TTS, CPU, 24 kHz, voice `af_heart` | Fast, high-quality English, Apache-2.0 |

Each sentence is cached as WAV + JSON metadata. Missing model or audio device degrades to silent playback with a warning.

### Documents — PDF/PPTX parsing

| Model | Type | Why |
|---|---|---|
| **Docling layout Heron** | RT-DetRv2 layout detector | Finds text/tables/figures, CPU, Apache-2.0 |
| **Docling TableFormer** | Table-structure model | Reconstructs tables, CDLA-Permissive-2.0 OR Apache-2.0 |
| **Docling Heron ONNX** | Optional ONNX layout variant | Alternative portable pipeline, Apache-2.0 |

Limits: 200 PDF pages, 200 PPTX slides, 50 MB files, 50 images per document. OCR is off by default.

### Optional Indic stack (gated)

| Model | Type | Why |
|---|---|---|
| **IndicTrans2 en-indic-dist-200M** | Seq2seq translator | English → Hindi/Kannada, MIT, gated |
| **Indic Parler-TTS** | Neural TTS | Hindi/Kannada voice, Apache-2.0, gated; pre-generated, not live playback |
| **FLAN-T5-large tokenizer** | Tokenizer only | Encodes the voice-style description for Parler |

Requires accepting model terms on Hugging Face and setting `HF_TOKEN`. Without them, Medha keeps the English lesson and reports why translation was unavailable.

### Declared but not wired

- **faster-whisper-small** — optional ASR/word alignment; no application code uses it yet.

### Deliberately excluded

- **Qwen2.5-VL-3B** — non-commercial Qwen Research license.
- **Piper** — GPL-3.0+ and research-only Blizzard data.
- **Meta MMS** — CC-BY-NC 4.0.

---

## Key implementation facts

- **Config:** `config.py` is the single source of truth for paths, profiles, model IDs, timing, and limits. It is dependency-free.
- **Lesson contract:** `medha/core/schema.py` and `spec/board-action/v1/SPEC.md`. Coordinates are normalized; durations are milliseconds; anchors are `{sentence, char}`.
- **Generation robustness:** compact JSON schema for Ollama grammar, lenient JSON extraction, Unicode sanitization, conservative repair that drops invalid actions instead of inventing content, two attempts per request.
- **RAG limits:** 450-token chunks, 64 overlap, 20 candidates, top 5, 3200-char material cap; rerank only when ≥50 chunks.
- **Timing:** audio is the master clock; checkpoints fire at the end of their step.
- **Rendering:** Hershey vector font (`assets/fonts/hershey.json`), procedural chalk wobble, matplotlib mathtext for equations, OpenGL 3.3, 1280×720, 60 FPS target.
- **Storage:** `content/lessons/*.json` canonical; `data/medha.db` index; caches for TTS, ingest, images, and Chroma vectors.
- **UI:** PySide6 desktop Studio with Create, Library, and Settings tabs; generation runs in a Qt worker thread; progressive playback starts before all steps are ready.
- **Frontend:** `frontend/` is a default Vite/React scaffold, not wired to any backend server — effectively unused.
- **Licensing:** code/spec Apache-2.0, lesson content CC-BY-4.0, model licenses tracked in `MODEL_LICENSES/`.
- **Verification:** `scripts/verify.ps1` runs ruff, mypy, pytest, pip check, license audit, health checks, and the offline audit.

---

## Main limitations

- Hindi/Kannada text translates, but narration stays English Kokoro audio.
- Image extraction/description exists, but image actions are not used in generated lessons.
- Voice input (faster-whisper) is not enabled.
- The small 3K context means source material is aggressively truncated.
- OCR is off by default, so scanned PDFs may not ingest well.
- The reranker can fail under very tight Windows commit limits; vector-only retrieval is the fallback.

---

## Files to open first

1. `README.md` — user-facing overview
2. `MODELS.md` + `models.lock.json` — model inventory and licenses
3. `config.py` — tuning knobs
4. `spec/board-action/v1/SPEC.md` + `medha/core/schema.py` — lesson/action contract
5. `medha/lesson/generator.py` — generation, repair, caching
6. `medha/rag/service.py` — retrieval pipeline
7. `medha/render/timeline.py` + `medha/render/playback.py` — sync and playback
8. `medha/tts/speech.py` + `medha/tts/kokoro.py` — speech and caching
9. `medha/studio/service.py` + `medha/studio/app.py` — end-to-end app flow
10. `medha/eval/checks.py` — quality scoring
