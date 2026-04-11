from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse


class ConfigError(ValueError):
    """Raised when the gateway configuration is invalid."""


@dataclass(frozen=True)
class UpstreamConfig:
    name: str
    base_url: str
    api_key_env: str
    timeout_seconds: int = 120
    chat_path: str = "/v1/chat/completions"
    image_path: str = "/v1/images/generations"

    def url_for(self, request_kind: str) -> str:
        path = self.image_path if request_kind == "images" else self.chat_path
        return f"{self.base_url.rstrip('/')}{path}"


@dataclass(frozen=True)
class ModelRoute:
    upstream: str
    upstream_model: str
    multimodal_chat_upstream: str | None = None
    multimodal_chat_upstream_model: str | None = None


@dataclass(frozen=True)
class SiteConfig:
    site_token: str
    name: str
    allowed_origins: tuple[str, ...]
    allowed_models: tuple[str, ...]
    default_chat_model: str
    default_image_model: str
    chat_model_candidates: tuple[str, ...]
    image_model_candidates: tuple[str, ...]
    model_route_overrides: dict[str, ModelRoute] = field(default_factory=dict)
    extra_headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class GatewayConfig:
    listen_host: str
    listen_port: int
    upstreams: dict[str, UpstreamConfig]
    model_routes: dict[str, ModelRoute]
    sites: dict[str, SiteConfig]

    def get_site(self, site_token: str) -> SiteConfig:
        try:
            return self.sites[site_token]
        except KeyError as exc:
            raise ConfigError(f"unknown site token: {site_token}") from exc

    def get_upstream(self, upstream_name: str) -> UpstreamConfig:
        try:
            return self.upstreams[upstream_name]
        except KeyError as exc:
            raise ConfigError(f"unknown upstream: {upstream_name}") from exc

    def is_allowed_origin(self, origin: str) -> bool:
        return any(_site_allows_origin(site, origin) for site in self.sites.values())

    def site_allows_origin(self, site_token: str, origin: str) -> bool:
        return _site_allows_origin(self.get_site(site_token), origin)


def load_gateway_config(path: str | Path) -> GatewayConfig:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))

    upstreams_raw = raw.get("upstreams", {})
    sites_raw = raw.get("sites", [])
    if not upstreams_raw:
        raise ConfigError("missing upstreams")
    if not sites_raw:
        raise ConfigError("missing sites")

    upstreams = {
        name: UpstreamConfig(
            name=name,
            base_url=value["base_url"],
            api_key_env=value["api_key_env"],
            timeout_seconds=int(value.get("timeout_seconds", 120)),
            chat_path=value.get("chat_path", "/v1/chat/completions"),
            image_path=value.get("image_path", "/v1/images/generations"),
        )
        for name, value in upstreams_raw.items()
    }

    model_routes = {
        model_name: _parse_model_route(
            model_name,
            value,
            upstreams=upstreams,
            field_name=f"model route '{model_name}'",
        )
        for model_name, value in raw.get("model_routes", {}).items()
    }

    sites: dict[str, SiteConfig] = {}
    for site in sites_raw:
        site_token = _require_string(site.get("site_token"), "site_token")
        if site_token in sites:
            raise ConfigError(f"duplicate site token: {site_token}")

        site_name = _require_string(site.get("name"), f"site '{site_token}' name")
        allowed_origins = _require_origin_list(
            site.get("allowed_origins"),
            f"site '{site_name}' allowed_origins",
        )
        allowed_models = _require_string_list(
            site.get("allowed_models"),
            f"site '{site_name}' allowed_models",
        )
        default_chat_model = _require_string(
            site.get("default_chat_model"),
            f"site '{site_name}' default_chat_model",
        )
        default_image_model = _require_string(
            site.get("default_image_model"),
            f"site '{site_name}' default_image_model",
        )
        chat_model_candidates = _optional_string_list(
            site.get("chat_model_candidates"),
            f"site '{site_name}' chat_model_candidates",
        ) or (default_chat_model,)
        image_model_candidates = _optional_string_list(
            site.get("image_model_candidates"),
            f"site '{site_name}' image_model_candidates",
        ) or (default_image_model,)
        model_route_overrides = _parse_site_model_route_overrides(
            site.get("model_route_overrides"),
            f"site '{site_name}' model_route_overrides",
            upstreams=upstreams,
        )

        if default_chat_model not in allowed_models:
            raise ConfigError(
                f"site '{site_name}' default_chat_model must be listed in allowed_models"
            )
        if default_image_model not in allowed_models:
            raise ConfigError(
                f"site '{site_name}' default_image_model must be listed in allowed_models"
            )
        effective_model_routes = {**model_routes, **model_route_overrides}
        for model_name in allowed_models:
            if model_name not in effective_model_routes:
                raise ConfigError(
                    f"site '{site_name}' allowed model '{model_name}' must exist in model_routes or model_route_overrides"
                )
        if default_chat_model not in effective_model_routes:
            raise ConfigError(
                f"site '{site_name}' default_chat_model must exist in model_routes or model_route_overrides"
            )
        if default_image_model not in effective_model_routes:
            raise ConfigError(
                f"site '{site_name}' default_image_model must exist in model_routes or model_route_overrides"
            )
        if chat_model_candidates[0] != default_chat_model:
            raise ConfigError(
                f"site '{site_name}' chat_model_candidates must start with default_chat_model"
            )
        if image_model_candidates[0] != default_image_model:
            raise ConfigError(
                f"site '{site_name}' image_model_candidates must start with default_image_model"
            )
        for model_name in (*chat_model_candidates, *image_model_candidates):
            if model_name not in allowed_models:
                raise ConfigError(
                    f"site '{site_name}' candidate model '{model_name}' must be listed in allowed_models"
                )
            if model_name not in effective_model_routes:
                raise ConfigError(
                    f"site '{site_name}' candidate model '{model_name}' must exist in model_routes or model_route_overrides"
                )

        sites[site_token] = SiteConfig(
            site_token=site_token,
            name=site_name,
            allowed_origins=allowed_origins,
            allowed_models=allowed_models,
            default_chat_model=default_chat_model,
            default_image_model=default_image_model,
            chat_model_candidates=chat_model_candidates,
            image_model_candidates=image_model_candidates,
            model_route_overrides=model_route_overrides,
            extra_headers=dict(site.get("extra_headers", {})),
        )

    return GatewayConfig(
        listen_host=raw.get("listen_host", "0.0.0.0"),
        listen_port=int(raw.get("listen_port", 8080)),
        upstreams=upstreams,
        model_routes=model_routes,
        sites=sites,
    )


def _require_string(value: object, field_name: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise ConfigError(f"missing {field_name}")


def _require_string_list(value: object, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ConfigError(f"missing {field_name}")

    items: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ConfigError(f"invalid {field_name}")
        items.append(item.strip())
    return tuple(items)


def _require_origin_list(value: object, field_name: str) -> tuple[str, ...]:
    origins = _require_string_list(value, field_name)
    for origin in origins:
        _normalize_origin(origin, field_name=field_name, allow_wildcard=True)
    return origins


def _site_allows_origin(site: SiteConfig, origin: str) -> bool:
    return any(
        _origin_matches(allowed_origin, origin) for allowed_origin in site.allowed_origins
    )


def _origin_matches(allowed_origin: str, request_origin: str) -> bool:
    try:
        allowed_scheme, allowed_host, allowed_port = _normalize_origin(
            allowed_origin,
            allow_wildcard=True,
        )
        request_scheme, request_host, request_port = _normalize_origin(request_origin)
    except ValueError:
        return False

    if allowed_scheme != request_scheme or allowed_port != request_port:
        return False
    if allowed_host.startswith("*."):
        suffix = allowed_host[1:]
        return request_host.endswith(suffix) and request_host != allowed_host[2:]
    return allowed_host == request_host


def _normalize_origin(
    origin: str,
    *,
    field_name: str | None = None,
    allow_wildcard: bool = False,
) -> tuple[str, str, int | None]:
    parsed = urlparse(origin)
    hostname = (parsed.hostname or "").lower()
    has_wildcard = "*" in origin
    invalid = (
        origin == "null"
        or parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or not hostname
        or parsed.path not in {"", "/"}
        or parsed.params
        or parsed.query
        or parsed.fragment
        or origin.endswith("/")
        or (has_wildcard and not _is_supported_wildcard_host(hostname))
        or (has_wildcard and not allow_wildcard)
        or ("*" in hostname and not has_wildcard)
    )
    if invalid:
        if field_name:
            raise ConfigError(f"invalid {field_name}")
        raise ValueError("invalid origin")
    return parsed.scheme, hostname, parsed.port


def _is_supported_wildcard_host(hostname: str) -> bool:
    return hostname.startswith("*.") and hostname.count("*") == 1 and "." in hostname[2:]


def _parse_model_route(
    model_name: str,
    value: object,
    *,
    upstreams: dict[str, UpstreamConfig],
    field_name: str,
) -> ModelRoute:
    if not isinstance(value, dict):
        raise ConfigError(f"invalid {field_name}")

    route = ModelRoute(
        upstream=_require_string(value.get("upstream"), f"{field_name} upstream"),
        upstream_model=_require_string(
            value.get("upstream_model", model_name),
            f"{field_name} upstream_model",
        ),
        multimodal_chat_upstream=_optional_string(
            value.get("multimodal_chat_upstream"),
            f"{field_name} multimodal_chat_upstream",
        ),
        multimodal_chat_upstream_model=_optional_string(
            value.get("multimodal_chat_upstream_model"),
            f"{field_name} multimodal_chat_upstream_model",
        ),
    )
    if route.upstream not in upstreams:
        raise ConfigError(
            f"{field_name} points to unknown upstream '{route.upstream}'"
        )
    if (
        route.multimodal_chat_upstream is not None
        and route.multimodal_chat_upstream not in upstreams
    ):
        raise ConfigError(
            f"{field_name} points to unknown multimodal_chat_upstream "
            f"'{route.multimodal_chat_upstream}'"
        )
    return route


def _parse_site_model_route_overrides(
    value: object,
    field_name: str,
    *,
    upstreams: dict[str, UpstreamConfig],
) -> dict[str, ModelRoute]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigError(f"invalid {field_name}")

    overrides: dict[str, ModelRoute] = {}
    for model_name, route_value in value.items():
        parsed_model_name = _require_string(model_name, field_name)
        overrides[parsed_model_name] = _parse_model_route(
            parsed_model_name,
            route_value,
            upstreams=upstreams,
            field_name=f"{field_name} '{parsed_model_name}'",
        )
    return overrides


def _optional_string(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise ConfigError(f"invalid {field_name}")


def _optional_string_list(value: object, field_name: str) -> tuple[str, ...] | None:
    if value is None:
        return None
    return _require_string_list(value, field_name)
