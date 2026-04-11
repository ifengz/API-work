from __future__ import annotations

import json
import os
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping
from urllib import error, request

from .policy import RoutingDecision


class ProxyError(RuntimeError):
    """Raised when the upstream proxy request fails locally."""


@dataclass(frozen=True)
class UpstreamResponse:
    status_code: int
    headers: dict[str, str]
    body: bytes


def build_upstream_request(
    decision: RoutingDecision,
    payload: Mapping[str, object],
    trace_id: str,
) -> tuple[str, dict[str, str], bytes]:
    forwarded_payload = _normalize_payload(decision, payload)
    forwarded_payload["model"] = decision.upstream_model

    try:
        upstream_token = os.environ[decision.upstream_api_key_env]
    except KeyError as exc:
        raise ProxyError(
            f"missing upstream token env: {decision.upstream_api_key_env}"
        ) from exc

    headers = {
        "Authorization": f"Bearer {upstream_token}",
        "Content-Type": "application/json",
        "X-Client-Trace-Id": trace_id,
        "X-Site-Id": decision.site_name,
    }
    headers.update(decision.extra_headers)
    body = json.dumps(forwarded_payload).encode("utf-8")
    return decision.upstream_url, headers, body


def _normalize_payload(
    decision: RoutingDecision,
    payload: Mapping[str, object],
) -> dict[str, Any]:
    forwarded_payload = deepcopy(dict(payload))
    if _should_default_ai_studio_image_response_format(decision, forwarded_payload):
        forwarded_payload["response_format"] = "b64_json"
    if _should_strip_image_detail(decision, forwarded_payload):
        forwarded_payload["messages"] = _strip_image_url_detail(
            forwarded_payload.get("messages")
        )
    return forwarded_payload


def _should_strip_image_detail(
    decision: RoutingDecision,
    payload: Mapping[str, object],
) -> bool:
    return (
        decision.upstream_name == "litellm"
        and decision.request_kind == "chat"
        and decision.upstream_model.startswith("gemini")
        and _count_chat_image_parts(payload.get("messages")) > 0
    )


def _should_default_ai_studio_image_response_format(
    decision: RoutingDecision,
    payload: Mapping[str, object],
) -> bool:
    return (
        decision.upstream_name == "ai_studio"
        and decision.request_kind == "images"
        and "response_format" not in payload
    )


def _strip_image_url_detail(messages: object) -> object:
    if not isinstance(messages, list):
        return messages

    sanitized_messages: list[object] = []
    for message in messages:
        if not isinstance(message, dict):
            sanitized_messages.append(message)
            continue
        content = message.get("content")
        if not isinstance(content, list):
            sanitized_messages.append(message)
            continue

        sanitized_content: list[object] = []
        for part in content:
            if not isinstance(part, dict) or part.get("type") != "image_url":
                sanitized_content.append(part)
                continue
            image_url = part.get("image_url")
            if not isinstance(image_url, dict) or "detail" not in image_url:
                sanitized_content.append(part)
                continue
            sanitized_image_url = {
                key: value for key, value in image_url.items() if key != "detail"
            }
            sanitized_part = dict(part)
            sanitized_part["image_url"] = sanitized_image_url
            sanitized_content.append(sanitized_part)

        sanitized_message = dict(message)
        sanitized_message["content"] = sanitized_content
        sanitized_messages.append(sanitized_message)

    return sanitized_messages


def count_input_images(payload: Mapping[str, object]) -> int:
    return _count_chat_image_parts(payload.get("messages")) + _count_reference_images(
        payload.get("referenceImages")
    )


def _count_chat_image_parts(messages: object) -> int:
    if not isinstance(messages, list):
        return 0

    image_part_count = 0
    for message in messages:
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict) or part.get("type") != "image_url":
                continue
            image_url = part.get("image_url")
            if isinstance(image_url, dict) and _as_non_empty_str(image_url.get("url")):
                image_part_count += 1
                continue
            if _as_non_empty_str(image_url):
                image_part_count += 1
    return image_part_count


def _count_reference_images(reference_images: object) -> int:
    if not isinstance(reference_images, list):
        return 0
    return sum(1 for image in reference_images if _as_non_empty_str(image))


def _as_non_empty_str(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def forward_request(
    decision: RoutingDecision,
    payload: Mapping[str, object],
    trace_id: str,
) -> UpstreamResponse:
    url, headers, body = build_upstream_request(decision, payload, trace_id)
    req = request.Request(url=url, data=body, headers=headers, method="POST")

    try:
        with request.urlopen(req, timeout=decision.timeout_seconds) as response:
            return UpstreamResponse(
                status_code=response.status,
                headers=dict(response.headers.items()),
                body=response.read(),
            )
    except error.HTTPError as exc:
        return UpstreamResponse(
            status_code=exc.code,
            headers=dict(exc.headers.items()),
            body=exc.read(),
        )
    except error.URLError as exc:
        raise ProxyError(f"failed to reach upstream: {exc.reason}") from exc
