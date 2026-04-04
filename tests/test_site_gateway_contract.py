from __future__ import annotations

import json
import sys
import tempfile
import unittest
from email.message import Message
from io import BytesIO
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from site_gateway.config import ConfigError, load_gateway_config
from site_gateway.policy import GatewayPolicy
from site_gateway.server import SiteGatewayHandler


VALID_TRACE_ID = "018f2f4e-5d1d-7c6a-b4fa-9d6c44f3a7ad"


CONFIG_TEMPLATE = {
    "listen_host": "127.0.0.1",
    "listen_port": 0,
    "upstreams": {
        "one_api": {
            "base_url": "http://one-api:3000",
            "api_key_env": "ONE_API_MASTER_TOKEN",
        },
        "litellm": {
            "base_url": "http://litellm:4000",
            "api_key_env": "LITELLM_MASTER_KEY",
        },
    },
    "model_routes": {
        "gemini-2.5-flash": {
            "upstream": "litellm",
            "upstream_model": "gemini-2.5-flash",
        },
        "gemini-2.5-flash-image": {
            "upstream": "litellm",
            "upstream_model": "gemini-2.5-flash-image",
        },
        "gpt-4o-mini": {
            "upstream": "one_api",
            "upstream_model": "gpt-4o-mini",
        },
    },
    "sites": [
        {
            "site_token": "site-demo-a",
            "name": "demo-a",
            "allowed_origins": [
                "https://image.usfan.net",
            ],
            "allowed_models": [
                "gemini-2.5-flash",
                "gemini-2.5-flash-image",
                "gpt-4o-mini",
            ],
            "default_chat_model": "gemini-2.5-flash",
            "default_image_model": "gemini-2.5-flash-image",
        },
        {
            "site_token": "site-demo-b",
            "name": "demo-b",
            "allowed_origins": [
                "https://studio-b.usfan.net",
            ],
            "allowed_models": [
                "gpt-4o-mini",
            ],
            "default_chat_model": "gpt-4o-mini",
            "default_image_model": "gpt-4o-mini",
        },
    ],
}


class SiteGatewayContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "gateway.json"
        self.config_path.write_text(
            json.dumps(CONFIG_TEMPLATE, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_load_gateway_config_requires_allowed_origins(self) -> None:
        invalid = json.loads(json.dumps(CONFIG_TEMPLATE))
        del invalid["sites"][0]["allowed_origins"]
        self.config_path.write_text(json.dumps(invalid), encoding="utf-8")

        with self.assertRaises(ConfigError):
            load_gateway_config(self.config_path)

    def test_preflight_allows_whitelisted_origin(self) -> None:
        handler = self._build_handler(
            "OPTIONS",
            "/v1/chat/completions",
            headers={
                "Origin": "https://image.usfan.net",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )

        getattr(handler, "do_OPTIONS")()

        self.assertEqual(handler.sent_status, 204)
        self.assertEqual(
            handler.sent_headers["Access-Control-Allow-Origin"],
            "https://image.usfan.net",
        )
        self.assertIn("Origin", handler.sent_headers["Vary"])

    def test_preflight_rejects_unknown_origin(self) -> None:
        handler = self._build_handler(
            "OPTIONS",
            "/v1/chat/completions",
            headers={
                "Origin": "https://evil.example.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )

        getattr(handler, "do_OPTIONS")()

        self.assertEqual(handler.sent_status, 403)
        self.assertNotIn("Access-Control-Allow-Origin", handler.sent_headers)

    def test_public_post_rejects_origin_not_allowed_for_site_token(self) -> None:
        handler = self._build_handler(
            "POST",
            "/v1/chat/completions",
            body=json.dumps({"messages": [{"role": "user", "content": "hi"}]}),
            headers={
                "Origin": "https://image.usfan.net",
                "Content-Type": "application/json",
                "Authorization": "Bearer site-demo-b",
                "X-Client-Trace-Id": VALID_TRACE_ID,
            },
        )

        handler.do_POST()

        payload = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(handler.sent_status, 403)
        self.assertEqual(payload["error"]["code"], "ORIGIN_NOT_ALLOWED")
        self.assertEqual(payload["error"]["trace_id"], VALID_TRACE_ID)

    def test_public_post_rejects_x_site_token_header(self) -> None:
        handler = self._build_handler(
            "POST",
            "/v1/chat/completions",
            body=json.dumps({"messages": [{"role": "user", "content": "hi"}]}),
            headers={
                "Origin": "https://image.usfan.net",
                "Content-Type": "application/json",
                "X-Site-Token": "site-demo-a",
            },
        )

        handler.do_POST()

        payload = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(handler.sent_status, 401)
        self.assertEqual(payload["error"]["code"], "TOKEN_INVALID")
        self.assertIn("trace_id", payload["error"])

    def test_invalid_json_uses_error_envelope(self) -> None:
        handler = self._build_handler(
            "POST",
            "/v1/chat/completions",
            body="{not-json",
            headers={
                "Origin": "https://image.usfan.net",
                "Content-Type": "application/json",
                "Authorization": "Bearer site-demo-a",
                "X-Client-Trace-Id": VALID_TRACE_ID,
            },
        )

        handler.do_POST()

        payload = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(handler.sent_status, 400)
        self.assertEqual(payload["error"]["code"], "BAD_REQUEST")
        self.assertEqual(payload["error"]["trace_id"], VALID_TRACE_ID)
        self.assertEqual(
            handler.sent_headers["Access-Control-Allow-Origin"],
            "https://image.usfan.net",
        )

    def test_missing_trace_id_is_rejected(self) -> None:
        handler = self._build_handler(
            "POST",
            "/v1/chat/completions",
            body=json.dumps({"messages": [{"role": "user", "content": "hi"}]}),
            headers={
                "Origin": "https://image.usfan.net",
                "Content-Type": "application/json",
                "Authorization": "Bearer site-demo-a",
            },
        )

        handler.do_POST()

        payload = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(handler.sent_status, 400)
        self.assertEqual(payload["error"]["code"], "BAD_REQUEST")
        self.assertRegex(
            payload["error"]["trace_id"],
            r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
        )

    def test_disallowed_model_returns_model_not_allowed(self) -> None:
        handler = self._build_handler(
            "POST",
            "/v1/chat/completions",
            body=json.dumps(
                {
                    "model": "claude-3-7-sonnet",
                    "messages": [{"role": "user", "content": "hi"}],
                }
            ),
            headers={
                "Origin": "https://image.usfan.net",
                "Content-Type": "application/json",
                "Authorization": "Bearer site-demo-a",
                "X-Client-Trace-Id": VALID_TRACE_ID,
            },
        )

        handler.do_POST()

        payload = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(handler.sent_status, 403)
        self.assertEqual(payload["error"]["code"], "MODEL_NOT_ALLOWED")
        self.assertEqual(payload["error"]["trace_id"], VALID_TRACE_ID)

    def _build_handler(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str],
        body: str | None = None,
    ) -> SiteGatewayHandler:
        config = load_gateway_config(self.config_path)
        handler = SiteGatewayHandler.__new__(SiteGatewayHandler)
        handler.server = type(
            "ServerStub",
            (),
            {
                "config": config,
                "policy": GatewayPolicy(config),
            },
        )()
        handler.command = method
        handler.path = path
        handler.request_version = "HTTP/1.1"
        handler.requestline = f"{method} {path} HTTP/1.1"
        header_message = Message()
        for key, value in headers.items():
            header_message[key] = value
        encoded_body = (body or "").encode("utf-8")
        if encoded_body and "Content-Length" not in header_message:
            header_message["Content-Length"] = str(len(encoded_body))
        handler.headers = header_message
        handler.rfile = BytesIO(encoded_body)
        handler.wfile = BytesIO()
        handler.sent_status = None
        handler.sent_headers = {}

        def send_response(status: int, message: str | None = None) -> None:
            handler.sent_status = status

        def send_header(name: str, value: str) -> None:
            handler.sent_headers[name] = value

        def end_headers() -> None:
            return None

        handler.send_response = send_response
        handler.send_header = send_header
        handler.end_headers = end_headers
        return handler


if __name__ == "__main__":
    unittest.main()
