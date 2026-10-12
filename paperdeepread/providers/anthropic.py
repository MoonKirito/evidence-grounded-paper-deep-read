from __future__ import annotations

from paperdeepread.providers.base import ChatMessage, HttpClient, checked_text, content_parts, data_image, sse_events


class AnthropicClient(HttpClient):
    def complete(self, messages: list[ChatMessage]) -> str:
        system, turns = [], []
        for message in messages:
            blocks = []
            for part in content_parts(message.content):
                if part["type"] == "text":
                    blocks.append({"type": "text", "text": part["text"]})
                elif part["type"] == "image_url":
                    mime, data = data_image(part["image_url"]["url"])
                    blocks.append({"type": "image", "source": {"type": "base64", "media_type": mime, "data": data}})
                else:
                    raise ValueError(f"Unsupported Anthropic content type: {part['type']}")
            if message.role in {"system", "developer"}:
                if any(b["type"] != "text" for b in blocks):
                    raise ValueError("Anthropic system messages must contain only text")
                system.extend(blocks)
            elif message.role in {"user", "assistant"}:
                turns.append({"role": message.role, "content": blocks})
            else:
                raise ValueError(f"Unsupported Anthropic role: {message.role}")
        payload = {"model": self.config.model, "messages": turns,
                   "max_tokens": self.config.max_tokens, "stream": self.config.stream}
        if system:
            payload["system"] = system
        if self.config.temperature is not None:
            payload["temperature"] = self.config.temperature
        payload = self.extra_payload(payload, {"model", "messages", "system", "max_tokens", "stream"})
        return self.post(self.config.base_url.rstrip("/") + "/messages", payload,
                         {"x-api-key": self.config.api_key, "anthropic-version": "2023-06-01"})

    def _read_response(self, data: dict) -> str:
        text = "".join(b.get("text", "") for b in data["content"] if b.get("type") == "text")
        return checked_text(text, data.get("stop_reason"), self.config.provider, allowed={"end_turn", "stop_sequence"})

    def _read_stream(self, response) -> str:
        chunks, reason, stopped = [], None, False
        for event in sse_events(response):
            kind = event.get("type")
            if kind == "error":
                raise RuntimeError(f"Anthropic stream error: {event.get('error')}")
            if kind == "content_block_start":
                block = event.get("content_block") or {}
                if block.get("type") == "text":
                    chunks.append(block.get("text", ""))
            if kind == "content_block_delta":
                delta = event.get("delta") or {}
                if delta.get("type") == "text_delta":
                    chunks.append(delta.get("text", ""))
            if kind == "message_delta":
                reason = (event.get("delta") or {}).get("stop_reason") or reason
            if kind == "message_stop":
                stopped = True
                break
        if not stopped:
            raise RuntimeError("Anthropic stream ended before message_stop; partial content was rejected.")
        return checked_text("".join(chunks), reason, self.config.provider, allowed={"end_turn", "stop_sequence"})
