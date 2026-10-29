"""Small stdlib Ollama chat client with structured JSON output."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any, Protocol, TypedDict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import config

from .errors import OllamaError


class ChatMessage(TypedDict):
    role: str
    content: str


class ChatClient(Protocol):
    model: str

    def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        format_schema: dict[str, Any] | None = None,
        options: Mapping[str, Any] | None = None,
    ) -> str: ...


class OllamaClient:
    def __init__(
        self,
        *,
        model: str | None = None,
        base_url: str | None = None,
        timeout_s: float | None = None,
        options: Mapping[str, Any] | None = None,
    ) -> None:
        profile = config.active_llm()
        self.model = model or profile.model
        self.base_url = (base_url or config.OLLAMA_BASE_URL).rstrip("/")
        self.timeout_s = timeout_s or config.OLLAMA_TIMEOUT_S
        self._options = {
            "temperature": config.OLLAMA_TEMPERATURE,
            "top_p": config.OLLAMA_TOP_P,
            "repeat_penalty": config.OLLAMA_REPEAT_PENALTY,
            "num_ctx": profile.num_ctx,
            "num_gpu": profile.num_gpu,
            "num_predict": config.OLLAMA_NUM_PREDICT,
            "seed": config.OLLAMA_SEED,
        }
        if options:
            self._options.update(options)

    def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        format_schema: dict[str, Any] | None = None,
        options: Mapping[str, Any] | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": list(messages),
            "stream": False,
            "format": format_schema or "json",
            "options": {**self._options, **dict(options or {})},
            "keep_alive": config.OLLAMA_KEEP_ALIVE,
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            f"{self.base_url}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_s) as response:
                raw = response.read()
        except HTTPError as exc:
            detail = _http_detail(exc)
            raise OllamaError(
                f"Ollama returned HTTP {exc.code} for model {self.model}: {detail}"
            ) from exc
        except URLError as exc:
            raise OllamaError(
                f"cannot reach Ollama at {self.base_url}; start Ollama and retry ({exc.reason})"
            ) from exc
        except TimeoutError as exc:
            raise OllamaError(
                f"Ollama timed out after {self.timeout_s:.0f}s; try a smaller lesson"
            ) from exc

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise OllamaError("Ollama returned invalid JSON") from exc
        if not isinstance(data, dict):
            raise OllamaError("Ollama returned an unexpected response")
        message = data.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            error = data.get("error")
            detail = str(error) if error else "response contained no message content"
            raise OllamaError(f"Ollama returned no lesson: {detail}")
        return content


def _http_detail(exc: HTTPError) -> str:
    try:
        payload = exc.read().decode("utf-8", errors="replace")
    except Exception:
        return exc.reason or "no error detail"
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return payload[:400] or (exc.reason or "no error detail")
    if isinstance(data, dict):
        detail = data.get("error") or data.get("message")
        if detail:
            return str(detail)[:400]
    return payload[:400]
