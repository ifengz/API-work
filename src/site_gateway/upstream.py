from __future__ import annotations

import json
import os
from copy import deepcopy
from dataclasses import dataclass
from typing import Mapping
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
) -> tuple[str, dict[str, str], bytes]:
    forwarded_payload = deepcopy(dict(payload))
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
        "X-Site-Token": decision.site_token,
        "X-Site-Name": decision.site_name,
    }
    headers.update(decision.extra_headers)
    body = json.dumps(forwarded_payload).encode("utf-8")
    return decision.upstream_url, headers, body


def forward_request(
    decision: RoutingDecision,
    payload: Mapping[str, object],
) -> UpstreamResponse:
    url, headers, body = build_upstream_request(decision, payload)
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
