"""Ollama Cloud chat model adapter."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Protocol

from shellloop.core import Message
from shellloop.models.text_actions import parse_text_actions


class OllamaCloudError(RuntimeError):
    """Raised when an Ollama Cloud request or response is malformed."""


class Transport(Protocol):
    """Post one JSON payload and return the parsed JSON response."""

    def post_json(self, url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]: ...


class UrllibJsonTransport:
    """Default transport built on the standard library."""

    def post_json(self, url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raise OllamaCloudError(f"Ollama chat request failed: HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise OllamaCloudError("Ollama chat request failed") from exc
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise OllamaCloudError("Ollama chat response is not valid JSON") from exc


class OllamaCloudModel:
    """Query Ollama Cloud's native chat API without a local Ollama service."""

    def __init__(
        self,
        api_base: str,
        model_name: str,
        api_key: str,
        transport: Transport | None = None,
    ) -> None:
        self._api_base = api_base.rstrip("/")
        self._model_name = model_name
        self._api_key = api_key
        self._transport = transport if transport is not None else UrllibJsonTransport()

    def query(self, messages: list[Message]) -> Message:
        text = self.complete(messages)
        return {"role": "assistant", "content": text, "extra": {"actions": parse_text_actions(text)}}

    def complete(self, messages: list[Message]) -> str:
        """Return raw assistant text for a constrained Studio proposal."""
        data = self._transport.post_json(
            f"{self._api_base}/chat",
            {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
            {
                "model": self._model_name,
                "messages": [_ollama_message(message) for message in messages],
                "stream": False,
            },
        )
        return _extract_assistant_text(data)


def _ollama_message(message: Message) -> dict[str, str]:
    content = message.get("content")
    return {"role": str(message.get("role", "user")), "content": "" if content is None else str(content)}


def _extract_assistant_text(data: dict[str, Any]) -> str:
    try:
        text = data["message"]["content"]
    except (KeyError, TypeError) as exc:
        raise OllamaCloudError("Ollama chat response is missing assistant content") from exc
    if not isinstance(text, str) or not text:
        raise OllamaCloudError("Ollama chat response has empty assistant content")
    return text
