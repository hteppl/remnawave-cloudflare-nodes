import os
from pathlib import Path
from typing import Any, Optional

from fluent.runtime import FluentBundle, FluentResource

from ..utils import get_logger

logger = get_logger(__name__)

LOCALES_DIR = Path(__file__).parent / "locales"
SUPPORTED_LANGUAGES = ("en", "ru")

_instance: Optional["Translator"] = None


class Translator:
    def __init__(self, language: str = "en"):
        if language not in SUPPORTED_LANGUAGES:
            logger.warning(f"Unsupported language '{language}', falling back to 'en'")
            language = "en"

        self._language = language
        self._bundle = FluentBundle([language], use_isolating=False)

        ftl_path = LOCALES_DIR / language / "messages.ftl"
        resource = FluentResource(ftl_path.read_text(encoding="utf-8"))
        self._bundle.add_resource(resource)

    @property
    def language(self) -> str:
        return self._language

    def get(self, message_id: str, **kwargs: Any) -> str:
        msg = self._bundle.get_message(message_id)
        if msg is None or msg.value is None:
            logger.error(f"Missing translation: {message_id} [{self._language}]")
            return message_id

        val, errors = self._bundle.format_pattern(msg.value, kwargs)
        for err in errors:
            logger.debug(f"Fluent error for '{message_id}': {err}")
        return val


def get_translator(language: Optional[str] = None) -> Translator:
    global _instance
    if language is None:
        language = os.getenv("LANGUAGE", "en")
    if _instance is None or language != _instance.language:
        _instance = Translator(language=language)
    return _instance
