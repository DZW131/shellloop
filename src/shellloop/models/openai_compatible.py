"""OpenAI-compatible chat completions model adapter.

A real model answers with free text, so this adapter turns the assistant text
into Shellloop's standard message: the text is preserved verbatim in
``content`` while ``extra.actions`` holds the single parsed shell action.

The HTTP client is behind a small ``Transport`` protocol so tests inject a
fake transport and never touch the network.  The default transport uses only
the standard library.  API keys are sent exclusively in the Authorization
header and never appear in returned messages, exceptions, or trajectories.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Protocol

from shellloop.core import Message
from shellloop.models.text_actions import parse_text_actions


class OpenAIModelError(RuntimeError):
    """Raised when the OpenAI-compatible request or response is malformed."""


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
            # Never include the response body: it could echo the API key.
            raise OpenAIModelError(f"chat completions request failed: HTTP {exc.code} {exc.reason}") from exc
        except urllib.error.URLError as exc:
            raise OpenAIModelError(f"chat completions request failed: {exc.reason}") from exc
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise OpenAIModelError("chat completions response is not valid JSON") from exc


class OpenAICompatibleModel:
    """Query one OpenAI-compatible chat completions endpoint.

    Args:
        api_base: Endpoint root, e.g. ``https://api.openai.com/v1``.
        model_name: Model identifier sent in the request body.
        api_key: Bearer credential used only in the Authorization header.
        transport: Injectable HTTP client; defaults to ``UrllibJsonTransport``.
    """

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
        url = f"{self._api_base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": self._model_name, "messages": [_openai_message(message) for message in messages]}
        data = self._transport.post_json(url, headers, payload)
        return _extract_assistant_text(data)


def _openai_message(message: Message) -> dict[str, str]:
    """Reduce a Shellloop message to the OpenAI wire format (role + content)."""
    role = str(message.get("role", "user"))
    content = message.get("content")
    if content is None:
        content = ""
    return {"role": role, "content": str(content)}


def _extract_assistant_text(data: dict[str, Any]) -> str:
    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise OpenAIModelError("chat completions response is missing assistant content") from exc
    if not isinstance(text, str) or not text:
        raise OpenAIModelError("chat completions response has empty assistant content")
    return text
