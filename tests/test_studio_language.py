"""Studio language options must map display names to schema language codes."""

from __future__ import annotations

import config
from medha.studio.app import LANGUAGES


def test_language_choices_are_name_code_pairs() -> None:
    assert tuple(
        (name, code) for code, name in config.LANGUAGE_NAMES.items()
    ) == LANGUAGES
    assert dict(LANGUAGES) == {"English": "en", "Hindi": "hi", "Kannada": "kn"}
    assert all(code in config.SUPPORTED_LANGUAGES for _, code in LANGUAGES)
