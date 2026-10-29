"""Medha runtime configuration.

Single source of truth for paths, model profiles and latency budgets.
Keep this module dependency-free: it must import on a bare Python install.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# Keep NumPy's OpenBLAS pool small; Medha uses ONNX/torch thread pools explicitly.
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

# --- Identity ---
APP_NAME = "Medha"
APP_VERSION = "0.1.0"
SCHEMA_VERSION = "1.0.0"

# --- Paths ---
ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
CONTENT_DIR = ROOT / "content"
CACHE_DIR = DATA_DIR / "cache"
LESSON_CACHE_DIR = CACHE_DIR / "lessons"
LESSON_CONTENT_DIR = CONTENT_DIR / "lessons"
TTS_CACHE_DIR = CACHE_DIR / "tts"
INGEST_CACHE_DIR = CACHE_DIR / "ingest"
GRAPH_CACHE_DIR = CACHE_DIR / "graphs"
UPLOAD_DIR = DATA_DIR / "uploads"
CHROMA_DIR = DATA_DIR / "chroma"
IMAGE_DIR = DATA_DIR / "images"
IMAGE_MANIFEST_PATH = IMAGE_DIR / "manifest.json"
DB_PATH = DATA_DIR / "medha.db"
MODEL_DIR = ROOT / "models"
ASSETS_DIR = ROOT / "assets"
IMAGE_LIB_DIR = ASSETS_DIR / "images"
VOICE_DIR = ASSETS_DIR / "voices"
FONT_DIR = ASSETS_DIR / "fonts"
SYMBOLS_DIR = ASSETS_DIR / "symbols"
LOG_DIR = ROOT / "logs"
LICENSES_DIR = ROOT / "LICENSES"
MODEL_LICENSES_DIR = ROOT / "MODEL_LICENSES"
SPEC_DIR = ROOT / "spec"

DIRECTORIES = (
    DATA_DIR,
    CONTENT_DIR,
    CACHE_DIR,
    LESSON_CACHE_DIR,
    LESSON_CONTENT_DIR,
    TTS_CACHE_DIR,
    INGEST_CACHE_DIR,
    GRAPH_CACHE_DIR,
    UPLOAD_DIR,
    CHROMA_DIR,
    IMAGE_DIR,
    MODEL_DIR,
    IMAGE_LIB_DIR,
    VOICE_DIR,
    FONT_DIR,
    SYMBOLS_DIR,
    LOG_DIR,
    LICENSES_DIR,
    MODEL_LICENSES_DIR,
)


def ensure_dirs() -> None:
    """Create runtime directories. Safe to call repeatedly."""
    for directory in DIRECTORIES:
        directory.mkdir(parents=True, exist_ok=True)


# --- Licensing ---
CODE_LICENSE = "Apache-2.0"
SPEC_LICENSE = "Apache-2.0"
CONTENT_LICENSE = "CC-BY-4.0"
MODEL_LOCK_PATH = ROOT / "models.lock.json"
MODELS_DOC_PATH = ROOT / "MODELS.md"


# --- Hardware ---
CPU_ONLY = os.getenv("MEDHA_CPU_ONLY", "0").lower() in {"1", "true", "yes"}
VRAM_TARGET_GB = 3.0
VRAM_MIN_FREE_GB = 1.0
LLM_CTX_SHRINK_STEPS = (3072, 2560, 2048)


# --- LLM profiles ---
@dataclass(frozen=True)
class LlmProfile:
    key: str
    model: str
    num_ctx: int
    num_gpu: int
    license: str
    notes: str


LLM_PROFILES: dict[str, LlmProfile] = {
    "demo_gpu": LlmProfile(
        key="demo_gpu",
        model="qwen3:4b-instruct-2507-q4_K_M",
        num_ctx=3072,
        num_gpu=30,
        license="Apache-2.0",
        notes="Default. Non-thinking Qwen3 4B; partial GPU offload for 4 GB VRAM.",
    ),
    "safe_gpu": LlmProfile(
        key="safe_gpu",
        model="phi4-mini:3.8b",
        num_ctx=4096,
        num_gpu=99,
        license="MIT",
        notes="VRAM-safe fallback; strong math/science for its size.",
    ),
    "cpu": LlmProfile(
        key="cpu",
        model="llama3.2:3b",
        num_ctx=2048,
        num_gpu=0,
        license="Llama-3.2-Community",
        notes="CPU-only fallback. Slow but keeps the demo alive.",
    ),
}

DEFAULT_PROFILE = "cpu" if CPU_ONLY else os.getenv("MEDHA_PROFILE", "demo_gpu")
if DEFAULT_PROFILE not in LLM_PROFILES:
    DEFAULT_PROFILE = "demo_gpu"

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_TIMEOUT_S = float(os.getenv("OLLAMA_TIMEOUT_S", "180"))
OLLAMA_TEMPERATURE = 0.3
OLLAMA_TOP_P = 0.9
OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "15m")
OLLAMA_REPEAT_PENALTY = 1.05
OLLAMA_NUM_PREDICT = 1200
OLLAMA_SEED = int(os.getenv("MEDHA_SEED", "42"))

# Environment the launcher should set for Ollama. These keep the LLM under ~3 GB.
OLLAMA_ENV = {
    "OLLAMA_FLASH_ATTENTION": "1",
    "OLLAMA_KV_CACHE_TYPE": "q8_0",
    "OLLAMA_MAX_LOADED_MODELS": "1",
    "OLLAMA_NUM_PARALLEL": "1",
    "OLLAMA_KEEP_ALIVE": OLLAMA_KEEP_ALIVE,
}


def active_llm() -> LlmProfile:
    return LLM_PROFILES[DEFAULT_PROFILE]


# --- Lesson generation (Ollama on GPU) ---
LESSON_PROMPT_VERSION = "b13-v1"
LESSON_CACHE_VERSION = "b13"
LESSON_DEFAULT_STEPS = 5
LESSON_MAX_STEPS = 8
LESSON_DEFAULT_AUDIENCE = "high-school students"
LESSON_RAG_TOP_K = 5
LESSON_MAX_MATERIAL_CHARS = 3200
LESSON_STEP_MAX_MATERIAL_CHARS = 2200
LESSON_MAX_CHUNK_CHARS = 700
LESSON_MAX_ATTEMPTS = 2
LESSON_SPEECH_WORDS_PER_SECOND = 2.6


# --- Embeddings / RAG (CPU only) ---
RAG_SCHEMA_VERSION = "1.0.0"
EMBED_MODEL_ID = "BAAI/bge-m3"
RERANKER_MODEL_ID = "BAAI/bge-reranker-v2-m3"
EMBED_DEVICE = "cpu"
EMBED_BATCH_SIZE = 8
EMBED_MAX_LENGTH = 512
EMBED_DIM = 1024
EMBED_NORMALIZE = True
EMBED_ONNX_PATH = MODEL_DIR / "bge-m3" / "onnx" / "model.onnx"
EMBED_TOKENIZER_PATH = MODEL_DIR / "bge-m3" / "onnx" / "tokenizer.json"
EMBED_NUM_THREADS = int(os.getenv("MEDHA_EMBED_THREADS", "4"))
RERANKER_DIR = MODEL_DIR / "bge-reranker-v2-m3"
RERANK_ENABLED = os.getenv("MEDHA_RERANK", "1").lower() not in {"0", "false", "no"}
RERANK_BATCH_SIZE = int(os.getenv("MEDHA_RERANK_BATCH", "8"))
RERANK_MAX_LENGTH = 512
RERANK_NUM_THREADS = int(os.getenv("MEDHA_RERANK_THREADS", "8"))
RAG_TOP_K = 5
RERANK_CANDIDATES = 20
RERANK_MIN_CHUNKS = 50
CHROMA_COLLECTION = "medha_material"
CHROMA_TELEMETRY = False

# --- Images / VLM (CPU only) ---
IMAGE_SCHEMA_VERSION = "1.0.0"
IMAGE_CACHE_VERSION = "b7"
IMAGE_RENDER_SCALE = 2.0
IMAGE_MIN_SIDE = 64
IMAGE_MAX_PER_DOC = 50
VLM_MODEL_ID = "HuggingFaceTB/SmolVLM-500M-Instruct"
VLM_MODEL_DIR = MODEL_DIR / "smolvlm-500m-instruct"
VLM_DEVICE = "cpu"
VLM_ENABLED = os.getenv("MEDHA_VLM", "1").lower() not in {"0", "false", "no"}
VLM_NUM_THREADS = int(os.getenv("MEDHA_VLM_THREADS", "8"))
VLM_MAX_NEW_TOKENS = int(os.getenv("MEDHA_VLM_MAX_TOKENS", "96"))
VLM_IMAGE_SPLITTING = os.getenv("MEDHA_VLM_SPLIT", "1").lower() not in {"0", "false", "no"}
VLM_PROMPT_VERSION = "b7-v4"
VLM_PROMPT = (
    "What text and symbols are visible? What shapes, objects, and colors are "
    "visible? Answer briefly and do not guess."
)

# --- TTS (CPU only) ---
KOKORO_REPO_ID = "hexgrad/Kokoro-82M"
KOKORO_REVISION = "f3ff3571791e39611d31c381e3a41a3af07b4987"
KOKORO_MODEL_DIR = MODEL_DIR / "kokoro-82m"
KOKORO_CONFIG_PATH = KOKORO_MODEL_DIR / "config.json"
KOKORO_WEIGHTS_PATH = KOKORO_MODEL_DIR / "kokoro-v1_0.pth"
KOKORO_DEVICE = "cpu"
KOKORO_LANG_CODE = "a"
KOKORO_VOICE = "af_heart"
KOKORO_VOICE_PATH = KOKORO_MODEL_DIR / "voices" / f"{KOKORO_VOICE}.pt"
KOKORO_SPEED = 1.0
TTS_SAMPLE_RATE = 24000
TTS_SENTENCE_END = r"(?<=[.!?])\s+"
TTS_LEAD_MS = 80
TTS_SENTENCE_GAP_MS = 90
TTS_STEP_GAP_MS = 250
TTS_CACHE_VERSION = "b11"

INDIC_PARLER_MODEL_ID = "ai4bharat/indic-parler-tts"
INDIC_PARLER_REVISION = "660bc53c64ae83150613264111708a0465211237"
INDIC_PARLER_MODEL_DIR = MODEL_DIR / "indic-parler-tts"
INDIC_PARLER_DESCRIPTION = (
    "A female teacher speaks clearly and calmly at a moderate pace. "
    "The recording is very high quality and close, with no background noise."
)
INDIC_PARLER_DESCRIPTION_TOKENIZER = "google/flan-t5-large"
INDIC_PARLER_DESCRIPTION_TOKENIZER_DIR = MODEL_DIR / "flan-t5-large"
INDICTRANS2_MODEL_ID = "ai4bharat/indictrans2-en-indic-dist-200M"
INDICTRANS2_REVISION = "2cfd0a20057756d756bf3e53528f492afc52f91a"
INDICTRANS2_MODEL_DIR = MODEL_DIR / "indictrans2-en-indic-dist-200M"
INDIC_LANGS = {
    "kannada": "kan_Knda",
    "hindi": "hin_Deva",
}
LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "kn": "Kannada",
}
INDIC_LANG_CODES = {
    "hi": "hin_Deva",
    "kn": "kan_Knda",
}
SUPPORTED_LANGUAGES = tuple(LANGUAGE_NAMES)

# --- Board / renderer ---
BOARD_WIDTH = 1280
BOARD_HEIGHT = 720
BOARD_FPS = 60
BOARD_BG = (0.055, 0.100, 0.072)
CHALK_COLOR = (0.96, 0.96, 0.90)
MATH_COLOR = (1.0, 1.0, 0.72)
DIAGRAM_COLOR = (0.70, 0.90, 1.00)
HIGHLIGHT_COLOR = (1.0, 0.82, 0.25)
CHALK_SPEED = 0.045
STROKE_JITTER = 0.0015
STROKE_WIDTH_PX = 3.0
BOARD_MARGIN_X = 0.055
BOARD_MARGIN_Y = 0.07
TITLE_BAND_H = 0.14
HERSHEY_PATH = FONT_DIR / "hershey.json"
HERSHEY_SOURCE = "futural.jhf"

# --- Timing / sync ---
LOOKAHEAD_STEPS = 1
AUDIO_LEAD_MS = 80
STEP_PAUSE_S = 0.25
MAX_DRIFT_MS = 150
CLOCK_POLL_MS = 10

# --- Ingestion ---
INGEST_SCHEMA_VERSION = "1.0.0"
INGEST_CACHE_VERSION = "b5"
CHUNK_TOKENS = 450
CHUNK_OVERLAP = 64
MAX_PDF_PAGES = 200
MAX_PPTX_SLIDES = 200
MAX_INGEST_BYTES = 50 * 1024 * 1024
CHUNK_TOKENIZER_PATH = MODEL_DIR / "bge-m3" / "tokenizer.json"
DOCLING_ARTIFACTS_DIR = MODEL_DIR / "docling"
DOCLING_NUM_THREADS = int(os.getenv("DOCLING_NUM_THREADS", "4"))
DOCLING_TIMEOUT_S = float(os.getenv("DOCLING_TIMEOUT_S", "120"))
OCR_ENABLED = os.getenv("MEDHA_OCR", "0").lower() in {"1", "true", "yes"}

# --- Storage / cache ---
CACHE_VERSION = "b0"
PROMPT_VERSION = "p0"


def as_dict() -> dict[str, str]:
    """Small summary used by the health command and diagnostics."""
    llm = active_llm()
    return {
        "app": f"{APP_NAME} {APP_VERSION}",
        "schema": SCHEMA_VERSION,
        "profile": llm.key,
        "llm": llm.model,
        "llm_ctx": str(llm.num_ctx),
        "llm_license": llm.license,
        "embed": EMBED_MODEL_ID,
        "reranker": RERANKER_MODEL_ID,
        "vlm": VLM_MODEL_ID,
        "tts": f"kokoro:{KOKORO_VOICE}",
        "code_license": CODE_LICENSE,
        "content_license": CONTENT_LICENSE,
        "db": str(DB_PATH),
    }
