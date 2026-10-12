from __future__ import annotations

from paperdeepread.providers.base import ChatMessage, HttpClient, checked_text, sse_events


class OpenAICompatibleClient(HttpClient):
    def complete(self, messages: list[ChatMessage]) -> str:
        payload = {"model": self.config.model,
                   "messages": [{"role": m.role, "content": m.content} for m in messages],
                   self.config.token_parameter: self.config.max_tokens, "stream": self.config.stream}
        if self.config.temperature is not None:
            payload["temperature"] = self.config.temperature
        payload = self.extra_payload(payload, {"model", "messages", "stream", "max_tokens", "max_completion_tokens"})
        if self.config.provider == "minimax":
            payload.setdefault("reasoning_split", True)
        headers = {"Authorization": f"Bearer {self.config.api_key}"} if self.config.api_key else {}
        return self.post(self.config.base_url.rstrip("/") + "/chat/completions", payload, headers)

    def _read_response(self, data: dict) -> str:
        choice = data["choices"][0]
        return checked_text(choice["message"].get("content") or "", choice.get("finish_reason"),
                            self.config.provider, allowed={"stop"})

    def _read_stream(self, response) -> str:
        chunks = []
        reason = None
        for event in sse_events(response):
            if event.get("error"):
                raise RuntimeError(f"{self.config.provider} stream error: {event['error']}")
            if event.get("_done"):
                break
            choices = event.get("choices") or []
            if not choices:
                continue
            choice = choices[0]
            reason = choice.get("finish_reason") or reason
            content = (choice.get("delta") or {}).get("content")
            if isinstance(content, str):
                chunks.append(content)
        return checked_text("".join(chunks), reason, self.config.provider, allowed={"stop"})
