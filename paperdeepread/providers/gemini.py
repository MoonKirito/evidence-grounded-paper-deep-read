from __future__ import annotations

from urllib.parse import quote

from paperdeepread.providers.base import ChatMessage, HttpClient, checked_text, content_parts, data_image, sse_events


class GeminiClient(HttpClient):
    def complete(self, messages: list[ChatMessage]) -> str:
        system, contents = [], []
        for message in messages:
            parts = []
            for part in content_parts(message.content):
                if part["type"] == "text":
                    parts.append({"text": part["text"]})
                elif part["type"] == "image_url":
                    mime, data = data_image(part["image_url"]["url"])
                    parts.append({"inlineData": {"mimeType": mime, "data": data}})
                else:
                    raise ValueError(f"Unsupported Gemini content type: {part['type']}")
            if message.role in {"system", "developer"}:
                if any("text" not in part for part in parts):
                    raise ValueError("Gemini system messages must contain only text")
                system.extend(parts)
            elif message.role in {"user", "assistant"}:
                contents.append({"role": "model" if message.role == "assistant" else "user", "parts": parts})
            else:
                raise ValueError(f"Unsupported Gemini role: {message.role}")
        generation = {"maxOutputTokens": self.config.max_tokens}
        if self.config.temperature is not None:
            generation["temperature"] = self.config.temperature
        # Native settings such as thinkingConfig can be configured in extra_body.
        extra = dict(self.config.extra_body)
        custom_generation = extra.pop("generationConfig", {})
        if not isinstance(custom_generation, dict) or "maxOutputTokens" in custom_generation:
            raise ValueError("extra_body.generationConfig must be a table and cannot override maxOutputTokens")
        generation.update(custom_generation)
        if {"contents", "systemInstruction"}.intersection(extra):
            raise ValueError("extra_body cannot override contents or systemInstruction")
        payload = {"contents": contents, "generationConfig": generation, **extra}
        if system:
            payload["systemInstruction"] = {"parts": system}
        model = self.config.model.removeprefix("models/")
        action = "streamGenerateContent?alt=sse" if self.config.stream else "generateContent"
        url = self.config.base_url.rstrip("/") + f"/models/{quote(model, safe='')}:{action}"
        return self.post(url, payload, {"x-goog-api-key": self.config.api_key})

    @staticmethod
    def candidate(data: dict) -> tuple[str, str | None]:
        candidates = data.get("candidates") or []
        if not candidates:
            if (data.get("promptFeedback") or {}).get("blockReason"):
                raise RuntimeError(f"Gemini blocked the prompt: {data['promptFeedback']['blockReason']}")
            return "", None
        candidate = candidates[0]
        # Thinking parts are not final text and must never enter the report.
        text = "".join(p.get("text", "") for p in (candidate.get("content") or {}).get("parts", []) if not p.get("thought"))
        return text, candidate.get("finishReason")

    def _read_response(self, data: dict) -> str:
        text, reason = self.candidate(data)
        return checked_text(text, reason, self.config.provider, allowed={"STOP"})

    def _read_stream(self, response) -> str:
        chunks, reason = [], None
        for event in sse_events(response):
            if event.get("error"):
                raise RuntimeError(f"Gemini stream error: {event['error']}")
            text, new_reason = self.candidate(event)
            chunks.append(text)
            reason = new_reason or reason
        return checked_text("".join(chunks), reason, self.config.provider, allowed={"STOP"})
