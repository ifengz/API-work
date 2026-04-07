from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from site_gateway.config import ConfigError, load_gateway_config
from site_gateway.policy import GatewayPolicy, PolicyError
from site_gateway.upstream import build_upstream_request


CONFIG_TEMPLATE = {
    "listen_host": "127.0.0.1",
    "listen_port": 8080,
    "upstreams": {
        "one_api": {
            "base_url": "http://one-api:3000",
            "api_key_env": "ONE_API_MASTER_TOKEN"
        },
        "litellm": {
            "base_url": "http://litellm:4000",
            "api_key_env": "LITELLM_MASTER_KEY"
        }
    },
    "model_routes": {
        "gemini-3-flash-preview": {
            "upstream": "litellm",
            "upstream_model": "gemini-3-flash-preview"
        },
        "gemini-3.1-pro-preview": {
            "upstream": "litellm",
            "upstream_model": "gemini-3.1-pro-preview"
        },
        "gemini-3.1-flash-lite-preview": {
            "upstream": "litellm",
            "upstream_model": "gemini-3.1-flash-lite-preview"
        },
        "gemini-2.5-pro": {
            "upstream": "litellm",
            "upstream_model": "gemini-2.5-pro"
        },
        "gemini-2.5-flash": {
            "upstream": "litellm",
            "upstream_model": "gemini-2.5-flash"
        },
        "gemini-3-pro-image-preview": {
            "upstream": "litellm",
            "upstream_model": "gemini-3-pro-image-preview"
        },
        "gemini-3.1-flash-image-preview": {
            "upstream": "litellm",
            "upstream_model": "gemini-3.1-flash-image-preview"
        },
        "gemini-2.5-flash-image": {
            "upstream": "litellm",
            "upstream_model": "gemini-2.5-flash-image"
        },
        "gpt-4o-mini": {
            "upstream": "one_api",
            "upstream_model": "gpt-4o-mini"
        },
        "qwen-max": {
            "upstream": "one_api",
            "upstream_model": "qwen-max"
        }
    },
    "sites": [
        {
            "site_token": "site-demo-a",
            "name": "demo-a",
            "allowed_origins": [
                "https://image.usfan.net",
                "http://127.0.0.1:5173"
            ],
            "allowed_models": [
                "gemini-3-flash-preview",
                "gemini-3.1-pro-preview",
                "gemini-3.1-flash-lite-preview",
                "gemini-2.5-pro",
                "gemini-2.5-flash",
                "gemini-3-pro-image-preview",
                "gemini-3.1-flash-image-preview",
                "gpt-4o-mini",
                "gemini-2.5-flash-image"
            ],
            "default_chat_model": "gemini-3-flash-preview",
            "default_image_model": "gemini-3-pro-image-preview",
            "chat_model_candidates": [
                "gemini-3-flash-preview",
                "gemini-3.1-pro-preview",
                "gemini-3.1-flash-lite-preview",
                "gemini-2.5-pro",
                "gemini-2.5-flash"
            ],
            "image_model_candidates": [
                "gemini-3-pro-image-preview",
                "gemini-3.1-flash-image-preview",
                "gemini-2.5-flash-image"
            ],
            "extra_headers": {
                "X-Forwarded-Site": "demo-a"
            }
        },
        {
            "site_token": "site-demo-b",
            "name": "demo-b",
            "allowed_origins": [
                "https://image.usfan.net",
                "http://127.0.0.1:5173"
            ],
            "allowed_models": [
                "gemini-3-flash-preview",
                "gemini-3.1-pro-preview",
                "gemini-3.1-flash-lite-preview",
                "gemini-2.5-pro",
                "gemini-2.5-flash",
                "gemini-3-pro-image-preview",
                "gemini-3.1-flash-image-preview",
                "gemini-2.5-flash-image",
                "qwen-max"
            ],
            "default_chat_model": "gemini-3-flash-preview",
            "default_image_model": "gemini-3-pro-image-preview",
            "chat_model_candidates": [
                "gemini-3-flash-preview",
                "gemini-3.1-pro-preview",
                "gemini-3.1-flash-lite-preview",
                "gemini-2.5-pro",
                "gemini-2.5-flash"
            ],
            "image_model_candidates": [
                "gemini-3-pro-image-preview",
                "gemini-3.1-flash-image-preview",
                "gemini-2.5-flash-image"
            ],
            "extra_headers": {
                "X-Forwarded-Site": "demo-b"
            }
        }
    ]
}


class SiteGatewayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "gateway.json"
        self.config_path.write_text(
            json.dumps(CONFIG_TEMPLATE, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.config = load_gateway_config(self.config_path)
        self.policy = GatewayPolicy(self.config)
        os.environ["ONE_API_MASTER_TOKEN"] = "one-api-secret"
        os.environ["LITELLM_MASTER_KEY"] = "litellm-secret"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_explicit_route_is_used_for_litellm_model(self) -> None:
        decision = self.policy.resolve("site-demo-a", "gemini-2.5-flash", "chat")
        self.assertEqual(decision.upstream_name, "litellm")

    def test_default_model_used_when_request_model_missing(self) -> None:
        decision = self.policy.resolve("site-demo-a", None, "chat")
        self.assertEqual(decision.request_model, "gemini-3-flash-preview")
        self.assertEqual(decision.upstream_name, "litellm")

    def test_default_chat_candidates_follow_order(self) -> None:
        decisions = self.policy.resolve_candidates("site-demo-a", None, "chat")
        self.assertEqual(
            [decision.request_model for decision in decisions],
            [
                "gemini-3-flash-preview",
                "gemini-3.1-pro-preview",
                "gemini-3.1-flash-lite-preview",
                "gemini-2.5-pro",
                "gemini-2.5-flash",
            ],
        )

    def test_disallowed_model_is_rejected(self) -> None:
        with self.assertRaises(PolicyError):
            self.policy.resolve("site-demo-a", "claude-3-7-sonnet", "chat")

    def test_image_requests_use_default_image_model(self) -> None:
        decision = self.policy.resolve("site-demo-a", None, "images")
        self.assertEqual(decision.request_model, "gemini-3-pro-image-preview")
        self.assertEqual(decision.upstream_name, "litellm")

    def test_demo_b_default_image_model_is_allowed(self) -> None:
        decision = self.policy.resolve("site-demo-b", None, "images")
        self.assertEqual(decision.request_model, "gemini-3-pro-image-preview")
        self.assertEqual(decision.upstream_name, "litellm")

    def test_explicit_model_skips_default_candidates(self) -> None:
        decisions = self.policy.resolve_candidates("site-demo-a", "gemini-2.5-pro", "chat")
        self.assertEqual([decision.request_model for decision in decisions], ["gemini-2.5-pro"])

    def test_multimodal_chat_keeps_primary_upstream_when_no_override_is_configured(self) -> None:
        decision = self.policy.resolve("site-demo-a", "gemini-2.5-flash", "chat")

        overridden = self.policy.resolve_multimodal_chat_decision(
            decision,
            input_image_count=1,
        )

        self.assertEqual(overridden.upstream_name, "litellm")
        self.assertEqual(overridden.upstream_url, "http://litellm:4000/v1/chat/completions")
        self.assertEqual(overridden.upstream_model, "gemini-2.5-flash")

    def test_text_only_chat_keeps_primary_upstream(self) -> None:
        decision = self.policy.resolve("site-demo-a", "gemini-2.5-flash", "chat")

        kept = self.policy.resolve_multimodal_chat_decision(
            decision,
            input_image_count=0,
        )

        self.assertEqual(kept.upstream_name, "litellm")

    def test_upstream_request_overrides_model_and_preserves_headers(self) -> None:
        decision = self.policy.resolve("site-demo-a", "gpt-4o-mini", "chat")
        url, headers, body = build_upstream_request(
            decision,
            {
                "model": "ignored-by-gateway",
                "messages": [{"role": "user", "content": "hi"}],
            },
            trace_id="018f2f4e-5d1d-7c6a-b4fa-9d6c44f3a7ad",
        )
        payload = json.loads(body.decode("utf-8"))

        self.assertEqual(url, "http://one-api:3000/v1/chat/completions")
        self.assertEqual(payload["model"], "gpt-4o-mini")
        self.assertEqual(headers["Authorization"], "Bearer one-api-secret")
        self.assertEqual(headers["X-Forwarded-Site"], "demo-a")
        self.assertEqual(
            headers["X-Client-Trace-Id"],
            "018f2f4e-5d1d-7c6a-b4fa-9d6c44f3a7ad",
        )

    def test_gemini_multimodal_chat_strips_image_url_detail_before_forward(self) -> None:
        decision = self.policy.resolve("site-demo-a", "gemini-2.5-flash", "chat")
        url, headers, body = build_upstream_request(
            decision,
            {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "analyze this image"},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": "data:image/jpeg;base64,AAA",
                                    "detail": "high",
                                },
                            },
                        ],
                    }
                ]
            },
            trace_id="018f2f4e-5d1d-7c6a-b4fa-9d6c44f3a7ad",
        )
        payload = json.loads(body.decode("utf-8"))

        self.assertEqual(url, "http://litellm:4000/v1/chat/completions")
        self.assertEqual(headers["Authorization"], "Bearer litellm-secret")
        image_part = payload["messages"][0]["content"][1]
        self.assertEqual(image_part["image_url"]["url"], "data:image/jpeg;base64,AAA")
        self.assertNotIn("detail", image_part["image_url"])

    def test_missing_model_route_is_rejected(self) -> None:
        invalid = json.loads(json.dumps(CONFIG_TEMPLATE))
        del invalid["model_routes"]["qwen-max"]
        self.config_path.write_text(json.dumps(invalid), encoding="utf-8")

        with self.assertRaises(ConfigError):
            load_gateway_config(self.config_path)


if __name__ == "__main__":
    unittest.main()
