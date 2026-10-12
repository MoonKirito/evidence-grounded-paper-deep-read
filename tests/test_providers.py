from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from paperdeepread.cli import main
from paperdeepread.config import load_config, parse_llm_config, write_default_config
from paperdeepread.providers import create_client
from paperdeepread.providers.anthropic import AnthropicClient
from paperdeepread.providers.base import ChatMessage, sse_events
from paperdeepread.providers.gemini import GeminiClient
from paperdeepread.providers.openai_compatible import OpenAICompatibleClient
from paperdeepread.providers.presets import PROVIDERS

IMAGE = "data:image/png;base64,aGVsbG8="
MESSAGES = [ChatMessage("system", "system instruction"), ChatMessage("user", [
    {"type": "text", "text": "read this figure"}, {"type": "image_url", "image_url": {"url": IMAGE}}])]


class FakeResponse:
    def __init__(self, body):
        self.body = body.encode("utf-8")
    def __enter__(self): return self
    def __exit__(self, *_): pass
    def read(self): return self.body
    def __iter__(self): return iter(self.body.splitlines(keepends=True))


def stream(*events):
    return "".join("event: ignored\ndata: " + json.dumps(e) + "\n\n" for e in events)


def config(provider, streaming=False, **kwargs):
    return parse_llm_config({"provider": provider, "model": "model-id", "api_key": "test-secret", "stream": streaming, **kwargs})


class ConfigTests(unittest.TestCase):
    def test_all_presets_resolve_defaults_and_select_correct_protocol(self):
        for name, preset in PROVIDERS.items():
            with self.subTest(provider=name):
                settings = {"base_url": "http://localhost:8000/v1"} if name == "openai_compatible" else {}
                cfg = config(name, **settings)
                self.assertEqual(cfg.api_key_env, preset.api_key_env)
                client = create_client(cfg)
                expected = {"openai": OpenAICompatibleClient, "anthropic": AnthropicClient, "gemini": GeminiClient}[preset.protocol]
                self.assertIsInstance(client, expected)

    def test_aliases_and_provider_specific_configuration(self):
        for alias, canonical in [("claude", "anthropic"), ("kimi", "moonshot"), ("glm", "zhipu"), ("google", "gemini")]:
            self.assertEqual(config(alias).provider, canonical)
        self.assertEqual(config("openai").token_parameter, "max_completion_tokens")
        self.assertEqual(config("qwen").token_parameter, "max_tokens")
        self.assertIsNone(config("openai").temperature)
        self.assertIsNone(config("openai", temperature=0.2, omit_temperature=True).temperature)
        self.assertNotIn("test-secret", repr(config("openai")))

    def test_vision_inherits_same_provider_but_not_another_vendors_credentials(self):
        parent = config("deepseek", base_url="https://custom.example/v1", extra_body={"thinking": {"type": "enabled"}})
        same = parse_llm_config({"model": "vision-model"}, parent)
        self.assertEqual(same.base_url, parent.base_url)
        self.assertEqual(same.api_key, parent.api_key)
        changed = parse_llm_config({"provider": "qwen", "model": "vision-model"}, parent)
        self.assertEqual(changed.base_url, PROVIDERS["qwen"].base_url)
        self.assertEqual(changed.api_key_env, "DASHSCOPE_API_KEY")
        self.assertEqual(changed.api_key, "")
        self.assertEqual(changed.extra_body, {})

    def test_init_config_for_every_preset_round_trips(self):
        with tempfile.TemporaryDirectory() as tmp:
            for provider in PROVIDERS:
                with self.subTest(provider=provider):
                    path = Path(tmp) / f"{provider}.toml"
                    url = "https://custom.example/v1" if provider == "openai_compatible" else None
                    write_default_config(path, provider=provider, model="model-id", base_url=url)
                    cfg = load_config(path)
                    self.assertEqual(cfg.llm.provider, provider)
                    self.assertEqual(cfg.llm.model, "model-id")
                    self.assertIsNone(cfg.vision)
            path = Path(tmp) / "legacy.toml"
            write_default_config(path)
            self.assertEqual(load_config(path).llm.provider, "mimo")
            path.write_text('[llm]\nprovider="deepseek"\nmodel="text-model"\n[vision]\nprovider="gemini"\nmodel="vision-model"\n', encoding="utf-8")
            cfg = load_config(path)
            self.assertEqual(cfg.vision.provider, "gemini")

    def test_invalid_configuration_fails_before_network(self):
        for values in [{"provider": "unknown"}, {"provider": "openai"},
                       {"provider": "openai_compatible", "model": "x"},
                       {"max_tokens": 0}, {"timeout_seconds": -1},
                       {"max_tokens_parameter": "wrong"}, {"stream": "false"},
                       {"base_url": "https://api.example/v1/chat/completions"}]:
            with self.subTest(values=values), self.assertRaises(ValueError):
                parse_llm_config(values)

    def test_environment_keys_and_local_no_key_mode(self):
        cfg = parse_llm_config({"provider": "openai", "model": "x"})
        with patch.dict(os.environ, {"OPENAI_API_KEY": "from-env"}):
            self.assertEqual(cfg.api_key, "from-env")
        local = parse_llm_config({"provider": "openai_compatible", "model": "x", "base_url": "http://localhost:8000/v1", "require_api_key": False, "stream": False})
        with patch("urllib.request.urlopen", return_value=FakeResponse('{"choices":[{"message":{"content":"OK"},"finish_reason":"stop"}]}')) as request:
            self.assertEqual(create_client(local).complete([ChatMessage("user", "hello")]), "OK\n")
            self.assertIsNone(request.call_args[0][0].get_header("Authorization"))


class AdapterTests(unittest.TestCase):
    def call(self, provider, response, streaming=False, **kwargs):
        client = create_client(config(provider, streaming, **kwargs))
        with patch("urllib.request.urlopen", return_value=FakeResponse(response)) as network:
            result = client.complete(MESSAGES)
            request = network.call_args[0][0]
            return result, request, json.loads(request.data)

    def test_openai_preserves_multimodal_messages_and_uses_new_token_field(self):
        response = '{"choices":[{"message":{"content":"report"},"finish_reason":"stop"}]}'
        result, request, payload = self.call("openai", response)
        self.assertEqual(result, "report\n")
        self.assertEqual(request.full_url, "https://api.openai.com/v1/chat/completions")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-secret")
        self.assertEqual(payload["messages"][1]["content"][1]["image_url"]["url"], IMAGE)
        self.assertIn("max_completion_tokens", payload)
        self.assertNotIn("max_tokens", payload)
        self.assertNotIn("temperature", payload)

    def test_compatible_provider_extra_parameters(self):
        response = '{"choices":[{"message":{"content":"report"},"finish_reason":"stop"}]}'
        _, request, payload = self.call("qwen", response, extra_body={"enable_thinking": False})
        self.assertFalse(payload["enable_thinking"])
        self.assertIn("max_tokens", payload)
        self.assertIn("dashscope.aliyuncs.com", request.full_url)

    def test_minimax_keeps_reasoning_out_of_final_content(self):
        response = '{"choices":[{"message":{"content":"report","reasoning_content":"private"},"finish_reason":"stop"}]}'
        result, request, payload = self.call("minimax", response)
        self.assertEqual(result, "report\n")
        self.assertTrue(payload["reasoning_split"])
        self.assertIn("max_completion_tokens", payload)
        self.assertIn("api.minimax.cn/v1", request.full_url)

    def test_anthropic_converts_system_and_base64_image(self):
        response = '{"content":[{"type":"thinking","thinking":"private"},{"type":"text","text":"report"}],"stop_reason":"end_turn"}'
        result, request, payload = self.call("anthropic", response)
        self.assertEqual(result, "report\n")
        self.assertEqual(request.full_url, "https://api.anthropic.com/v1/messages")
        self.assertEqual(request.get_header("X-api-key"), "test-secret")
        self.assertEqual(request.get_header("Anthropic-version"), "2023-06-01")
        self.assertEqual(payload["system"][0]["text"], "system instruction")
        image = payload["messages"][0]["content"][1]
        self.assertEqual(image["source"], {"type": "base64", "media_type": "image/png", "data": "aGVsbG8="})

    def test_gemini_converts_image_and_excludes_thinking_text(self):
        response = '{"candidates":[{"content":{"parts":[{"text":"private","thought":true},{"text":"report"}]},"finishReason":"STOP"}]}'
        result, request, payload = self.call("gemini", response, extra_body={"generationConfig": {"thinkingConfig": {"thinkingBudget": 0}}})
        self.assertEqual(result, "report\n")
        self.assertTrue(request.full_url.endswith("/models/model-id:generateContent"))
        self.assertNotIn("test-secret", request.full_url)
        self.assertEqual(request.get_header("X-goog-api-key"), "test-secret")
        self.assertEqual(payload["systemInstruction"]["parts"][0]["text"], "system instruction")
        self.assertEqual(payload["contents"][0]["parts"][1]["inlineData"]["mimeType"], "image/png")
        self.assertEqual(payload["generationConfig"]["thinkingConfig"]["thinkingBudget"], 0)

    def test_all_three_streaming_protocols(self):
        cases = [
            ("openai", stream({"choices": [{"delta": {"reasoning_content": "private", "content": "rep"}}]}, {"choices": [{"delta": {"content": "ort"}, "finish_reason": "stop"}]}) + "data: [DONE]\n\n"),
            ("anthropic", stream({"type": "content_block_delta", "delta": {"type": "thinking_delta", "thinking": "private"}}, {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "report"}}, {"type": "message_delta", "delta": {"stop_reason": "end_turn"}}, {"type": "message_stop"})),
            ("gemini", stream({"candidates": [{"content": {"parts": [{"text": "private", "thought": True}, {"text": "report"}]}, "finishReason": "STOP"}]})),
        ]
        for provider, response in cases:
            with self.subTest(provider=provider):
                result, request, payload = self.call(provider, response, True)
                self.assertEqual(result, "report\n")
                if provider == "gemini":
                    self.assertIn("streamGenerateContent?alt=sse", request.full_url)
                else:
                    self.assertTrue(payload["stream"])

    def test_truncated_blocked_and_empty_responses_fail(self):
        cases = [("openai", {"choices": [{"message": {"content": "partial"}, "finish_reason": "length"}]}),
                 ("anthropic", {"content": [{"type": "text", "text": "partial"}], "stop_reason": "max_tokens"}),
                 ("gemini", {"candidates": [{"content": {"parts": [{"text": "partial"}]}, "finishReason": "MAX_TOKENS"}]}),
                 ("gemini", {"promptFeedback": {"blockReason": "SAFETY"}}),
                 ("openai", {"choices": [{"message": {"content": ""}, "finish_reason": "stop"}]})]
        for provider, data in cases:
            with self.subTest(provider=provider), self.assertRaises(RuntimeError):
                self.call(provider, json.dumps(data))

    def test_incomplete_streams_and_error_events_fail(self):
        cases = [("openai", {"choices": [{"delta": {"content": "partial"}}]}),
                 ("anthropic", {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "partial"}}),
                 ("gemini", {"candidates": [{"content": {"parts": [{"text": "partial"}]}}]}),
                 ("openai", {"error": {"message": "limit reached"}}),
                 ("anthropic", {"type": "error", "error": {"message": "limit reached"}})]
        for provider, data in cases:
            with self.subTest(provider=provider), self.assertRaises(RuntimeError):
                self.call(provider, stream(data), True)

    def test_extra_body_cannot_replace_core_requests(self):
        for provider, extra in [("openai", {"messages": []}), ("anthropic", {"model": "other"}), ("gemini", {"contents": []})]:
            with self.subTest(provider=provider), patch("urllib.request.urlopen") as network, self.assertRaises(ValueError):
                create_client(config(provider, extra_body=extra)).complete(MESSAGES)
            network.assert_not_called()

    def test_missing_key_and_http_error_are_actionable_and_redacted(self):
        cfg = parse_llm_config({"provider": "openai", "model": "x", "api_key_env": "UNSET_TEST_KEY"})
        with patch.dict(os.environ, {}, clear=True), patch("urllib.request.urlopen") as network, self.assertRaisesRegex(RuntimeError, "UNSET_TEST_KEY"):
            create_client(cfg).complete(MESSAGES)
        network.assert_not_called()
        error = urllib.error.HTTPError("https://api.example", 401, "Unauthorized", {}, io.BytesIO(b"bad test-secret"))
        with patch("urllib.request.urlopen", side_effect=error), self.assertRaises(RuntimeError) as caught:
            create_client(config("anthropic")).complete(MESSAGES)
        self.assertIn("401", str(caught.exception))
        self.assertNotIn("test-secret", str(caught.exception))

    def test_multiline_sse_and_malformed_records(self):
        events = list(sse_events(FakeResponse(': heartbeat\n\ndata: {"a":\ndata: 1}\n\ndata: [DONE]\n\n')))
        self.assertEqual(events, [{"a": 1}, {"_done": True}])
        with self.assertRaises(RuntimeError):
            list(sse_events(FakeResponse("data: not-json\n\n")))


class CliTests(unittest.TestCase):
    def test_provider_list_and_alias_config_generation(self):
        with patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(main(["list-providers"]), 0)
            self.assertIn("anthropic", output.getvalue())
        with tempfile.TemporaryDirectory() as tmp, patch("sys.stdout", new_callable=io.StringIO) as output:
            path = Path(tmp) / "config.toml"
            self.assertEqual(main(["init-config", "--path", str(path), "--provider", "claude", "--model", "test-model"]), 0)
            self.assertEqual(load_config(path).llm.provider, "anthropic")
            self.assertIn("ANTHROPIC_API_KEY", output.getvalue())


if __name__ == "__main__":
    unittest.main()
