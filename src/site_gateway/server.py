from __future__ import annotations

import json
import os
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .config import GatewayConfig, load_gateway_config
from .policy import GatewayPolicy, PolicyError
from .upstream import ProxyError, forward_request


class SiteGatewayServer(ThreadingHTTPServer):
    def __init__(self, config: GatewayConfig) -> None:
        super().__init__((config.listen_host, config.listen_port), SiteGatewayHandler)
        self.config = config
        self.policy = GatewayPolicy(config)


class SiteGatewayHandler(BaseHTTPRequestHandler):
    server: SiteGatewayServer
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:
        if self.path == "/healthz":
            self._send_json(HTTPStatus.OK, {"status": "ok"})
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path == "/v1/resolve":
            self._handle_resolve()
            return
        if self.path == "/v1/chat/completions":
            self._handle_proxy("chat")
            return
        if self.path == "/v1/images/generations":
            self._handle_proxy("images")
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def log_message(self, format: str, *args: object) -> None:
        return

    def _handle_resolve(self) -> None:
        payload = self._read_json()
        site_token = self._extract_site_token(payload)
        model_name = payload.get("model")
        request_kind = payload.get("request_kind", "chat")
        try:
            decision = self.server.policy.resolve(site_token, _as_str(model_name), _as_str(request_kind))
        except PolicyError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        self._send_json(HTTPStatus.OK, decision.to_dict())

    def _handle_proxy(self, request_kind: str) -> None:
        payload = self._read_json()
        site_token = self._extract_site_token(payload)
        try:
            decision = self.server.policy.resolve(
                site_token,
                _as_str(payload.get("model")),
                request_kind,
            )
            response = forward_request(decision, payload)
        except PolicyError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        except ProxyError as exc:
            self._send_json(HTTPStatus.BAD_GATEWAY, {"error": str(exc)})
            return

        content_type = response.headers.get("Content-Type", "application/json")
        self.send_response(response.status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(response.body)))
        self.end_headers()
        self.wfile.write(response.body)

    def _read_json(self) -> dict[str, object]:
        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length)
        if not body:
            return {}
        return json.loads(body.decode("utf-8"))

    def _extract_site_token(self, payload: dict[str, object]) -> str:
        auth_header = self.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header.removeprefix("Bearer ").strip()
        header_token = self.headers.get("X-Site-Token")
        if header_token:
            return header_token.strip()
        payload_token = payload.get("site_token")
        if isinstance(payload_token, str) and payload_token.strip():
            return payload_token.strip()
        raise PolicyError("missing site token")

    def _send_json(self, status: HTTPStatus, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _as_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    config_path = argv[0] if argv else os.environ.get("SITE_GATEWAY_CONFIG", "config/gateway.json")
    config = load_gateway_config(Path(config_path))
    server = SiteGatewayServer(config)
    print(f"site-gateway listening on {config.listen_host}:{config.listen_port}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
