from __future__ import annotations

import json
import socket
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass

from paperdeepread.config import LlmConfig


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


class MimoClient:
    def __init__(self, config: LlmConfig) -> None:
        if config.provider != "mimo":
            raise ValueError(f"Unsupported provider for MimoClient: {config.provider}")
        self.config = config

    def complete(self, messages: list[ChatMessage]) -> str:
        api_key = self.config.api_key
        if not api_key:
            raise RuntimeError(
                f"Missing MiMo API key. Set environment variable {self.config.api_key_env}."
            )

        payload = {
            "model": self.config.model,
            "messages": [{"role": msg.role, "content": msg.content} for msg in messages],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "stream": self.config.stream,
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        url = self.config.base_url.rstrip("/") + "/chat/completions"
        request = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                if self.config.stream:
                    return self._read_stream(response)
                raw = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"MiMo API HTTP {exc.code}: {error_body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"MiMo API request failed: {exc.reason}") from exc
        except (TimeoutError, socket.timeout) as exc:
            raise RuntimeError(
                "MiMo API request timed out while waiting for the model response. "
                "The request reached the API, but the report generation did not finish "
                f"within {self.config.timeout_seconds} seconds. Try stream=true, a larger "
                "timeout_seconds, or a smaller max_input_chars/max_tokens."
            ) from exc

        data = json.loads(raw)
        try:
            choice = data["choices"][0]
            message = choice["message"]
            content = message["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected MiMo API response shape: {raw[:1000]}") from exc

        if not isinstance(content, str) or not content.strip():
            reasoning = message.get("reasoning_content", "")
            finish_reason = choice.get("finish_reason", "")
            usage = data.get("usage", {})
            raise RuntimeError(
                "MiMo API returned empty final content. "
                f"finish_reason={finish_reason!r}, reasoning_chars={len(reasoning)}, usage={usage}. "
                "For mimo-v2.5-pro, completion tokens include hidden reasoning tokens; increase "
                "max_tokens or reduce max_input_chars."
            )
        return content.strip() + "\n"

    def _read_stream(self, response) -> str:
        chunks: list[str] = []
        content_chars = 0
        reasoning_chars = 0
        next_content_notice = 2000
        next_reasoning_notice = 2000
        finish_reason = None
        for raw_line in response:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line or line.startswith(":"):
                continue
            if line.startswith("data:"):
                line = line[len("data:") :].strip()
            if line == "[DONE]":
                break
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            choices = event.get("choices") or []
            if not choices:
                continue
            choice = choices[0]
            finish_reason = choice.get("finish_reason") or finish_reason
            delta = choice.get("delta") or {}
            reasoning = delta.get("reasoning_content")
            if isinstance(reasoning, str):
                reasoning_chars += len(reasoning)
                if reasoning_chars >= next_reasoning_notice:
                    print(
                        f"[llm stream] reasoning {reasoning_chars} chars",
                        file=sys.stderr,
                    )
                    next_reasoning_notice += 2000
            content = delta.get("content")
            if isinstance(content, str):
                chunks.append(content)
                content_chars += len(content)
                if content_chars >= next_content_notice:
                    print(
                        f"[llm stream] content {content_chars} chars",
                        file=sys.stderr,
                    )
                    next_content_notice += 2000

        text = "".join(chunks).strip()
        if not text:
            raise RuntimeError(
                "MiMo API streaming response did not contain final report content. "
                f"finish_reason={finish_reason!r}, reasoning_chars={reasoning_chars}. "
                "For mimo-v2.5-pro, the model may spend the output budget on reasoning before "
                "writing content; increase max_tokens or reduce max_input_chars."
            )
        return text + "\n"
