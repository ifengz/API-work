from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from site_gateway.config import load_gateway_config
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
        "vertex-gemini-flash": {
            "upstream": "litellm",
            "upstream_model": "vertex-gemini-flash"
        },
        "gpt-4o-mini": {
            "upstream": "one_api",
            "upstream_model": "gpt-4o-mini"
        }
    },
    "sites": [
        {
            "site_token": "site-demo-a",
            "name": "demo-a",
            "allowed_models": [
                "vertex-gemini-flash",
                "gpt-4o-mini",
                "vertex-imagen-3"
            ],
            "default_chat_model": "gpt-4o-mini",
            "default_image_model": "vertex-imagen-3",
            "extra_headers": {
                "X-Forwarded-Site": "demo-a"
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

    def test_vertex_models_default_to_litellm(self) -> None:
        decision = self.policy.resolve("site-demo-a", "vertex-gemini-flash", "chat")
        self.assertEqual(decision.upstream_name, "litellm")

    def test_default_model_used_when_request_model_missing(self) -> None:
        decision = self.policy.resolve("site-demo-a", None, "chat")
        self.assertEqual(decision.request_model, "gpt-4o-mini")
        self.assertEqual(decision.upstream_name, "one_api")

    def test_disallowed_model_is_rejected(self) -> None:
        with self.assertRaises(PolicyError):
            self.policy.resolve("site-demo-a", "claude-3-7-sonnet", "chat")

    def test_image_requests_use_default_image_model(self) -> None:
        decision = self.policy.resolve("site-demo-a", None, "images")
        self.assertEqual(decision.request_model, "vertex-imagen-3")
        self.assertEqual(decision.upstream_name, "litellm")

    def test_upstream_request_overrides_model_and_preserves_headers(self) -> None:
        decision = self.policy.resolve("site-demo-a", "gpt-4o-mini", "chat")
        url, headers, body = build_upstream_request(
            decision,
            {
                "model": "ignored-by-gateway",
                "messages": [{"role": "user", "content": "hi"}]
            },
        )
        payload = json.loads(body.decode("utf-8"))

        self.assertEqual(url, "http://one-api:3000/v1/chat/completions")
        self.assertEqual(payload["model"], "gpt-4o-mini")
        self.assertEqual(headers["Authorization"], "Bearer one-api-secret")
        self.assertEqual(headers["X-Forwarded-Site"], "demo-a")


if __name__ == "__main__":
    unittest.main()
