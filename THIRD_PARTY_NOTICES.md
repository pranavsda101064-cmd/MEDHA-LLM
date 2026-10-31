# Third-party notices

Medha code and specification are Apache-2.0. This file summarizes third-party
components. Full license texts are in `LICENSES/`; model weight license
snapshots are in `MODEL_LICENSES/`. Model weights are not distributed with the
repository; `tools/fetch_models.py` fetches them under their original terms.

## Frontend

- **Landing page** (`frontend/`): React + Vite landing adapted from
  [dishaaaaaaa14/dishaui](https://github.com/dishaaaaaaa14/dishaui), licensed
  under the Apache License 2.0 (the same license as this repository). Its npm
  dependencies listed in `frontend/package-lock.json` keep their own licenses
  and are not redistributed (`node_modules/` is ignored); `frontend/dist/`
  holds the built, minified bundle used at runtime.

## Font data

- **Hershey Futural** (`assets/fonts/futural.jhf`, converted to
  `assets/fonts/hershey.json`): Hershey font data is usable for any purpose,
  commercial or otherwise, with the acknowledgements in
  `LICENSES/LicenseRef-Hershey.txt`. The data may not be converted to the U.S.
  NTIS format. The GPLv2+ `libhersheyfont` code is not used.
- **Gochi Hand** (`assets/fonts/GochiHand-Regular.ttf`): handwritten labels for
  the Studio notice-board menu items. Copyright 2011 Huerta Tipografica, with
  Reserved Font Names "Gochi" and "Gochi Hand"; licensed under the SIL Open
  Font License 1.1 (`LICENSES/OFL-1.1.txt`).

## Models

| Component | License | Notes |
|---|---|---|
| Qwen3-4B-Instruct-2507 | Apache-2.0 | Default lesson/action model |
| Phi-4-mini | MIT | VRAM-safe fallback |
| Llama 3.2 3B | Llama 3.2 Community | CPU fallback; review before commercial release |
| BAAI/bge-m3 | MIT | Embeddings, ONNX CPU |
| BAAI/bge-reranker-v2-m3 | Apache-2.0 | Reranker, CPU torch |
| SmolVLM-500M-Instruct | Apache-2.0 | Image captions and diagram descriptions, CPU torch |
| Kokoro-82M | Apache-2.0 | English speech |
| Docling Heron layout | Apache-2.0 | PDF layout analysis |
| Docling TableFormer | CDLA-Permissive-2.0 OR Apache-2.0 | PDF table structure |
| Docling Heron ONNX | Apache-2.0 | Optional CPU ONNX layout variant |
| faster-whisper-small | MIT | Optional voice input/alignment |
| Indic Parler-TTS | Apache-2.0 | Gated; Indic v1.1 |
| IndicTrans2 distilled 200M | MIT | Gated; Indic v1.1 |

Deliberately excluded: Qwen2.5-VL-3B (Qwen Research/non-commercial), Piper
(GPL-3.0-or-later) with lessac (research-only), and Meta MMS (CC-BY-NC-4.0).

## Runtime libraries

- PySide6 / Qt 6: LGPL-3.0-only. Dynamic linking is used; Qt is not statically
  linked or modified. See `LICENSES/LGPL-3.0-only.txt`.
- PyOpenGL: BSD-style.
- NumPy, SciPy: BSD-3-Clause.
- Matplotlib: PSF-based/BSD-compatible.
- Pydantic: MIT.
- httpx, psutil, filelock, platformdirs: BSD/MIT-style.
- PyTorch / TorchAudio / torchvision: BSD-3-Clause.
- ONNX Runtime: MIT.
- ChromaDB: Apache-2.0.
- Hugging Face Transformers: Apache-2.0.
- Kokoro, misaki: Apache-2.0.
- spaCy / en_core_web_sm: MIT; en_core_web_sm is installed separately.
- soundfile: BSD-3-Clause; sounddevice: MIT.
- Docling, python-pptx, pypdf, pdfplumber: MIT/BSD/Apache-2.0 components; see
  their installed package metadata.
- pytesseract: Apache-2.0. Optional OCR requires a separately installed
  Tesseract binary (Apache-2.0) and Leptonica (BSD-2-Clause); neither is bundled.

Run `python tools/license_audit.py` and `pip-licenses` before a public release.
