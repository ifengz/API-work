from __future__ import annotations

import json
import os
import re
import secrets
import sys
import time
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .audit import AuditEvent, AuditStore, build_token_identity, extract_response_usage, get_audit_db_path
from .config import ConfigError, GatewayConfig, load_gateway_config
from .policy import GatewayPolicy, PolicyError
from .upstream import ProxyError, UpstreamResponse, forward_request


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
        self.audit_store = AuditStore(get_audit_db_path(os.environ.get("SITE_GATEWAY_AUDIT_DB")))


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
        started_at = time.monotonic_ns()
        created_at = _utc_now()
        self._trace_id = _new_trace_id()
        cors_origin = self._current_allowed_origin()
        request_kind = PUBLIC_PROXY_PATHS.get(self.path)
        audit_fields = {
            "site_name": None,
            "site_token_preview": None,
            "site_token_fingerprint": None,
            "request_kind": request_kind,
            "request_model": None,
            "upstream_name": None,
            "upstream_model": None,
            "status_code": HTTPStatus.NOT_FOUND,
            "error_code": None,
            "prompt_tokens": None,
            "completion_tokens": None,
            "total_tokens": None,
            "image_count": None,
        }
        try:
            if request_kind is None:
                raise RequestError(
                    HTTPStatus.NOT_FOUND,
                    "NOT_FOUND",
                    "not found",
                    cors_origin=cors_origin,
                    trace_id=self._trace_id,
                )

            site_token = self._extract_site_token()
            token_preview, token_fingerprint = build_token_identity(site_token)
            audit_fields["site_token_preview"] = token_preview
            audit_fields["site_token_fingerprint"] = token_fingerprint
            self._trace_id = self._require_trace_id()
            payload = self._read_json()
            audit_fields["request_model"] = _as_str(payload.get("model"))
            self._reject_payload_site_token(payload)
            cors_origin = self._require_site_origin(site_token)
            decision, response = self._handle_proxy(request_kind, payload, site_token)
            usage = extract_response_usage(
                response.body,
                response.headers.get("Content-Type", "application/json"),
            )
            audit_fields.update(
                {
                    "site_name": decision.site_name,
                    "request_model": decision.request_model,
                    "upstream_name": decision.upstream_name,
                    "upstream_model": decision.upstream_model,
                    "status_code": response.status_code,
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens,
                    "image_count": usage.image_count,
                }
            )
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
        except RequestError as exc:
            audit_fields["status_code"] = int(exc.status)
            audit_fields["error_code"] = exc.code
            self._send_error(
                exc.status,
                exc.code,
                exc.message,
                cors_origin=exc.cors_origin,
                trace_id=exc.trace_id or self._trace_id,
            )
        finally:
            self._record_audit_event(
                AuditEvent(
                    created_at=created_at,
                    trace_id=self._trace_id,
                    site_name=audit_fields["site_name"],
                    site_token_preview=audit_fields["site_token_preview"],
                    site_token_fingerprint=audit_fields["site_token_fingerprint"],
                    request_kind=audit_fields["request_kind"],
                    request_model=audit_fields["request_model"],
                    upstream_name=audit_fields["upstream_name"],
                    upstream_model=audit_fields["upstream_model"],
                    status_code=int(audit_fields["status_code"]),
                    error_code=audit_fields["error_code"],
                    duration_ms=_elapsed_milliseconds(started_at),
                    prompt_tokens=audit_fields["prompt_tokens"],
                    completion_tokens=audit_fields["completion_tokens"],
                    total_tokens=audit_fields["total_tokens"],
                    image_count=audit_fields["image_count"],
                )
            )

    def log_message(self, format: str, *args: object) -> None:
        return

    def _record_audit_event(self, event: AuditEvent) -> None:
        try:
            self.server.audit_store.record_event(event)
        except Exception as exc:
            print(
                f"audit write failed trace_id={event.trace_id}: {exc}",
                file=sys.stderr,
            )

    def _handle_proxy(
        self,
        request_kind: str,
        payload: dict[str, object],
        site_token: str,
    ) -> tuple[object, UpstreamResponse]:
        cors_origin = self._current_allowed_origin()
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
        return decision, response

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


def _elapsed_milliseconds(started_at: int) -> int:
    elapsed_ns = time.monotonic_ns() - started_at
    return max(0, elapsed_ns // 1_000_000)


def _utc_now() -> datetime:
    return datetime.now(UTC)


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
