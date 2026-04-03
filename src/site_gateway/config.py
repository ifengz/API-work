from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


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


@dataclass(frozen=True)
class SiteConfig:
    site_token: str
    name: str
    allowed_models: tuple[str, ...]
    default_chat_model: str
    default_image_model: str
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
        model_name: ModelRoute(
            upstream=value["upstream"],
            upstream_model=value.get("upstream_model", model_name),
        )
        for model_name, value in raw.get("model_routes", {}).items()
    }

    sites = {
        site["site_token"]: SiteConfig(
            site_token=site["site_token"],
            name=site["name"],
            allowed_models=tuple(site["allowed_models"]),
            default_chat_model=site["default_chat_model"],
            default_image_model=site["default_image_model"],
            extra_headers=dict(site.get("extra_headers", {})),
        )
        for site in sites_raw
    }

    return GatewayConfig(
        listen_host=raw.get("listen_host", "0.0.0.0"),
        listen_port=int(raw.get("listen_port", 8080)),
        upstreams=upstreams,
        model_routes=model_routes,
        sites=sites,
    )
