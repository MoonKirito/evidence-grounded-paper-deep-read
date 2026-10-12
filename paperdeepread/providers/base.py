from __future__ import annotations

import base64
import binascii
import json
import re
import socket
import http.client
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol, Iterator

from paperdeepread.config import LlmConfig


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str | list[dict]


class ModelClient(Protocol):
    config: LlmConfig
    def complete(self, messages: list[ChatMessage]) -> str: ...


def content_parts(content: str | list[dict]) -> list[dict]:
    return [{"type": "text", "text": content}] if isinstance(content, str) else content


def data_image(url: str) -> tuple[str, str]:
    match = re.fullmatch(r"data:(image/(?:png|jpeg|webp|gif));base64,([A-Za-z0-9+/=\r\n]+)", url)
    if not match:
        raise ValueError("Native vision adapters require a base64 data image, as produced by pdffigures2 pre-reading.")
    mime, encoded = match.groups()
    encoded = encoded.replace("\n", "").replace("\r", "")
    try:
        base64.b64decode(encoded, validate=True)
    except binascii.Error as exc:
        raise ValueError("Invalid base64 image content") from exc
    return mime, encoded


def sse_events(response) -> Iterator[dict]:
    """Parse SSE records, including multiple data lines and heartbeat comments."""
    lines: list[str] = []
    def parse():
        raw = "\n".join(lines)
        if raw == "[DONE]":
            return {"_done": True}
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Malformed JSON in model streaming response") from exc
        if not isinstance(value, dict):
            raise RuntimeError("Model stream event must be a JSON object")
        return value
    for raw_line in response:
        line = raw_line.decode("utf-8").rstrip("\r\n")
        if not line:
            if lines:
                yield parse()
                lines.clear()
            continue
        if line.startswith("data:"):
            lines.append(line[5:].lstrip(" "))
    if lines:
        yield parse()


def checked_text(text: str, reason: str | None, provider: str, *, allowed: set[str]) -> str:
    if reason in {"length", "max_tokens", "MAX_TOKENS"}:
        raise RuntimeError(f"{provider} response was truncated; increase max_tokens before resuming.")
    if reason not in allowed:
        raise RuntimeError(f"{provider} response did not finish normally (reason={reason!r}); partial content was rejected.")
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError(f"{provider} returned no final text; check the model, output budget and content restrictions.")
    return text.strip() + "\n"


class HttpClient:
    def __init__(self, config: LlmConfig):
        self.config = config

    def post(self, url: str, payload: dict, headers: dict) -> str:
        if self.config.require_api_key and not self.config.api_key:
            raise RuntimeError(f"Missing {self.config.provider} API key. Set {self.config.api_key_env} or llm.api_key.")
        request = urllib.request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                                         headers={"Content-Type": "application/json", **headers}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                if self.config.stream:
                    return self._read_stream(response)
                data = json.loads(response.read().decode("utf-8"))
                if not isinstance(data, dict):
                    raise RuntimeError("Model response must be a JSON object")
                if data.get("error"):
                    raise RuntimeError(f"Model API error: {data['error']}")
                return self._read_response(data)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:2000]
            if self.config.api_key:
                body = body.replace(self.config.api_key, "[REDACTED]")
            raise RuntimeError(f"{self.config.provider} API HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"{self.config.provider} request failed: {exc.reason}") from exc
        except (TimeoutError, socket.timeout) as exc:
            raise RuntimeError(f"{self.config.provider} request timed out after {self.config.timeout_seconds}s; try streaming or a larger timeout.") from exc
        except (OSError, http.client.IncompleteRead) as exc:
            raise RuntimeError(f"{self.config.provider} connection was interrupted; partial content was rejected.") from exc
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected {self.config.provider} response format: {type(exc).__name__}") from exc

    def extra_payload(self, payload: dict, protected: set[str]) -> dict:
        overlap = protected.intersection(self.config.extra_body)
        if overlap:
            raise ValueError(f"extra_body cannot override core fields: {', '.join(sorted(overlap))}")
        return {**payload, **self.config.extra_body}
