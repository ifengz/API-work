from __future__ import annotations

import json
import os
import re
import secrets
import sys
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .config import ConfigError, GatewayConfig, load_gateway_config
from .policy import GatewayPolicy, PolicyError
from .upstream import ProxyError, forward_request


PUBLIC_PROXY_PATHS = {
    "/v1/chat/completions": "chat",
    "/v1/images/generations": "images",
}
CORS_ALLOWED_METHODS = "POST, OPTIONS"
CORS_ALLOWED_HEADERS = "Authorization, Content-Type, X-Client-Trace-Id"
TRACE_ID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


class RequestError(RuntimeError):
    def __init__(
        self,
        status: HTTPStatus,
        code: str,
        message: str,
        *,
        cors_origin: str | None = None,
        trace_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.cors_origin = cors_origin
        self.trace_id = trace_id


class SiteGatewayServer(ThreadingHTTPServer):
    def __init__(self, config: GatewayConfig) -> None:
        super().__init__((config.listen_host, config.listen_port), SiteGatewayHandler)
        self.config = config
        self.policy = GatewayPolicy(config)


class SiteGatewayHandler(BaseHTTPRequestHandler):
    server: SiteGatewayServer
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:
        self._trace_id = _new_trace_id()
        if self.path == "/healthz":
            self._send_json(
                HTTPStatus.OK,
                {"status": "ok"},
                cors_origin=self._current_allowed_origin(),
                trace_id=self._trace_id,
            )
            return
        self._send_error(
            HTTPStatus.NOT_FOUND,
            "NOT_FOUND",
            "not found",
            cors_origin=self._current_allowed_origin(),
            trace_id=self._trace_id,
        )

    def do_OPTIONS(self) -> None:
        self._trace_id = _new_trace_id()
        cors_origin = self._current_allowed_origin()
        try:
            request_kind = PUBLIC_PROXY_PATHS.get(self.path)
            if request_kind is None:
                raise RequestError(
                    HTTPStatus.NOT_FOUND,
                    "NOT_FOUND",
                    "not found",
                    cors_origin=cors_origin,
                    trace_id=self._trace_id,
                )

            cors_origin = self._require_allowed_origin()
            requested_method = self.headers.get("Access-Control-Request-Method", "")
            if requested_method.upper() != "POST":
                raise RequestError(
                    HTTPStatus.METHOD_NOT_ALLOWED,
                    "BAD_REQUEST",
                    "preflight method must be POST",
                    cors_origin=cors_origin,
                    trace_id=self._trace_id,
                )

            self.send_response(HTTPStatus.NO_CONTENT)
            self._send_cors_headers(cors_origin)
            self.send_header("Access-Control-Allow-Methods", CORS_ALLOWED_METHODS)
            self.send_header("Access-Control-Allow-Headers", CORS_ALLOWED_HEADERS)
            self.send_header("Access-Control-Max-Age", "600")
            self.send_header("Content-Length", "0")
            self.end_headers()
        except RequestError as exc:
            self._send_error(
                exc.status,
                exc.code,
                exc.message,
                cors_origin=exc.cors_origin,
                trace_id=exc.trace_id or self._trace_id,
            )

    def do_POST(self) -> None:
        self._trace_id = _new_trace_id()
        cors_origin = self._current_allowed_origin()
        try:
            request_kind = PUBLIC_PROXY_PATHS.get(self.path)
            if request_kind is None:
                raise RequestError(
                    HTTPStatus.NOT_FOUND,
                    "NOT_FOUND",
                    "not found",
                    cors_origin=cors_origin,
                    trace_id=self._trace_id,
                )

            site_token = self._extract_site_token()
            self._trace_id = self._require_trace_id()
            payload = self._read_json()
            self._reject_payload_site_token(payload)
            cors_origin = self._require_site_origin(site_token)
            self._handle_proxy(request_kind, payload, site_token, cors_origin)
        except RequestError as exc:
            self._send_error(
                exc.status,
                exc.code,
                exc.message,
                cors_origin=exc.cors_origin,
                trace_id=exc.trace_id or self._trace_id,
            )

    def log_message(self, format: str, *args: object) -> None:
        return

    def _handle_proxy(
        self,
        request_kind: str,
        payload: dict[str, object],
        site_token: str,
        cors_origin: str | None,
    ) -> None:
        try:
            decision = self.server.policy.resolve(
                site_token,
                _as_str(payload.get("model")),
                request_kind,
            )
            response = forward_request(decision, payload, self._trace_id)
        except PolicyError as exc:
            raise _map_policy_error(exc, cors_origin, self._trace_id) from exc
        except ProxyError as exc:
            raise RequestError(
                HTTPStatus.SERVICE_UNAVAILABLE,
                "UPSTREAM_UNAVAILABLE",
                "upstream request failed",
                cors_origin=cors_origin,
                trace_id=self._trace_id,
            ) from exc

        if response.status_code >= 400:
            raise RequestError(
                _map_upstream_status(response.status_code),
                "UPSTREAM_UNAVAILABLE",
                "upstream request failed",
                cors_origin=cors_origin,
                trace_id=self._trace_id,
            )

        content_type = response.headers.get("Content-Type", "application/json")
        self._send_body(
            HTTPStatus(response.status_code),
            response.body,
            content_type=content_type,
            cors_origin=cors_origin,
            trace_id=self._trace_id,
        )

    def _read_json(self) -> dict[str, object]:
        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length)
        if not body:
            return {}
        content_type = self.headers.get("Content-Type", "")
        if content_type and "application/json" not in content_type.lower():
            raise RequestError(
                HTTPStatus.BAD_REQUEST,
                "BAD_REQUEST",
                "content type must be application/json",
                cors_origin=self._current_allowed_origin(),
                trace_id=self._trace_id,
            )
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RequestError(
                HTTPStatus.BAD_REQUEST,
                "BAD_REQUEST",
                "request body must be valid json",
                cors_origin=self._current_allowed_origin(),
                trace_id=self._trace_id,
            ) from exc

    def _extract_site_token(self) -> str:
        if self.headers.get("X-Site-Token"):
            raise RequestError(
                HTTPStatus.UNAUTHORIZED,
                "TOKEN_INVALID",
                "authorization bearer token is required",
                cors_origin=self._current_allowed_origin(),
                trace_id=self._trace_id,
            )
        auth_header = self.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise RequestError(
                HTTPStatus.UNAUTHORIZED,
                "TOKEN_INVALID",
                "authorization bearer token is required",
                cors_origin=self._current_allowed_origin(),
                trace_id=self._trace_id,
            )

        site_token = auth_header.removeprefix("Bearer ").strip()
        if not site_token:
            raise RequestError(
                HTTPStatus.UNAUTHORIZED,
                "TOKEN_INVALID",
                "authorization bearer token is required",
                cors_origin=self._current_allowed_origin(),
                trace_id=self._trace_id,
            )
        return site_token

    def _reject_payload_site_token(self, payload: dict[str, object]) -> None:
        if "site_token" not in payload:
            return
        raise RequestError(
            HTTPStatus.UNAUTHORIZED,
            "TOKEN_INVALID",
            "authorization bearer token is required",
            cors_origin=self._current_allowed_origin(),
            trace_id=self._trace_id,
        )

    def _require_trace_id(self) -> str:
        trace_id = self.headers.get("X-Client-Trace-Id", "").strip()
        if TRACE_ID_PATTERN.fullmatch(trace_id):
            return trace_id
        raise RequestError(
            HTTPStatus.BAD_REQUEST,
            "BAD_REQUEST",
            "request trace id is invalid",
            cors_origin=self._current_allowed_origin(),
            trace_id=self._trace_id,
        )

    def _require_site_origin(self, site_token: str) -> str | None:
        origin = self.headers.get("Origin")
        if not origin:
            return None
        try:
            if self.server.config.site_allows_origin(site_token, origin):
                return origin
        except ConfigError as exc:
            raise RequestError(
                HTTPStatus.UNAUTHORIZED,
                "TOKEN_INVALID",
                "site token is invalid",
                cors_origin=self._current_allowed_origin(),
                trace_id=self._trace_id,
            ) from exc
        raise RequestError(
            HTTPStatus.FORBIDDEN,
            "ORIGIN_NOT_ALLOWED",
            "origin not allowed",
            trace_id=self._trace_id,
        )

    def _send_json(
        self,
        status: HTTPStatus,
        payload: dict[str, object],
        *,
        cors_origin: str | None = None,
        trace_id: str | None = None,
    ) -> None:
        body = json.dumps(payload).encode("utf-8")
        self._send_body(
            status,
            body,
            content_type="application/json",
            cors_origin=cors_origin,
            trace_id=trace_id,
        )

    def _send_error(
        self,
        status: HTTPStatus,
        code: str,
        message: str,
        *,
        cors_origin: str | None = None,
        trace_id: str | None = None,
    ) -> None:
        self._send_json(
            status,
            {
                "error": {
                    "code": code,
                    "message": message,
                    "trace_id": trace_id or self._trace_id,
                }
            },
            cors_origin=cors_origin,
            trace_id=trace_id,
        )

    def _send_body(
        self,
        status: HTTPStatus,
        body: bytes,
        *,
        content_type: str,
        cors_origin: str | None = None,
        trace_id: str | None = None,
    ) -> None:
        self.send_response(status)
        if cors_origin:
            self._send_cors_headers(cors_origin)
        if trace_id:
            self.send_header("X-Client-Trace-Id", trace_id)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_cors_headers(self, cors_origin: str) -> None:
        self.send_header("Access-Control-Allow-Origin", cors_origin)
        self.send_header("Vary", "Origin")

    def _current_allowed_origin(self) -> str | None:
        origin = self.headers.get("Origin")
        if not origin or not self.server.config.is_allowed_origin(origin):
            return None
        return origin

    def _require_allowed_origin(self) -> str | None:
        origin = self.headers.get("Origin")
        if not origin:
            return None
        if self.server.config.is_allowed_origin(origin):
            return origin
        raise RequestError(
            HTTPStatus.FORBIDDEN,
            "ORIGIN_NOT_ALLOWED",
            "origin not allowed",
            trace_id=self._trace_id,
        )


def _as_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _map_policy_error(
    exc: PolicyError,
    cors_origin: str | None,
    trace_id: str,
) -> RequestError:
    message = str(exc)
    if "unknown site token" in message:
        return RequestError(
            HTTPStatus.UNAUTHORIZED,
            "TOKEN_INVALID",
            "site token is invalid",
            cors_origin=cors_origin,
            trace_id=trace_id,
        )
    if "is not allowed for site" in message:
        return RequestError(
            HTTPStatus.FORBIDDEN,
            "MODEL_NOT_ALLOWED",
            "requested model is not allowed",
            cors_origin=cors_origin,
            trace_id=trace_id,
        )
    return RequestError(
        HTTPStatus.BAD_REQUEST,
        "BAD_REQUEST",
        "request is invalid",
        cors_origin=cors_origin,
        trace_id=trace_id,
    )


def _map_upstream_status(status_code: int) -> HTTPStatus:
    if status_code in {
        HTTPStatus.BAD_REQUEST,
        HTTPStatus.UNAUTHORIZED,
        HTTPStatus.FORBIDDEN,
        HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
        HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
        HTTPStatus.TOO_MANY_REQUESTS,
    }:
        return HTTPStatus(status_code)
    return HTTPStatus.SERVICE_UNAVAILABLE


def _new_trace_id() -> str:
    timestamp_ms = int(time.time_ns() // 1_000_000) & ((1 << 48) - 1)
    rand_a = secrets.randbits(12)
    rand_b = secrets.randbits(62)
    return (
        f"{timestamp_ms >> 16:08x}-"
        f"{timestamp_ms & 0xffff:04x}-"
        f"{(0x7 << 12) | rand_a:04x}-"
        f"{0x80 | ((rand_b >> 56) & 0x3f):02x}{(rand_b >> 48) & 0xff:02x}-"
        f"{rand_b & ((1 << 48) - 1):012x}"
    )


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
