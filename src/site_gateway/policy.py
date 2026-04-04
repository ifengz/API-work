from __future__ import annotations

from dataclasses import asdict, dataclass

from .config import ConfigError, GatewayConfig, SiteConfig


class PolicyError(ValueError):
    """Raised when a request violates site policy."""


@dataclass(frozen=True)
class RoutingDecision:
    site_token: str
    site_name: str
    request_kind: str
    request_model: str
    upstream_name: str
    upstream_model: str
    upstream_url: str
    upstream_api_key_env: str
    timeout_seconds: int
    extra_headers: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class GatewayPolicy:
    def __init__(self, config: GatewayConfig) -> None:
        self.config = config

    def resolve(
        self,
        site_token: str,
        requested_model: str | None,
        request_kind: str,
    ) -> RoutingDecision:
        if request_kind not in {"chat", "images"}:
            raise PolicyError(f"unsupported request kind: {request_kind}")

        try:
            site = self.config.get_site(site_token)
        except ConfigError as exc:
            raise PolicyError(str(exc)) from exc

        model_name = self._resolve_model_name(site, requested_model, request_kind)
        if model_name not in site.allowed_models:
            raise PolicyError(
                f"model '{model_name}' is not allowed for site '{site.name}'"
            )

        route = self.config.model_routes.get(model_name)
        if route is None:
            raise PolicyError(f"model '{model_name}' has no configured route")

        try:
            upstream = self.config.get_upstream(route.upstream)
        except ConfigError as exc:
            raise PolicyError(str(exc)) from exc

        return RoutingDecision(
            site_token=site.site_token,
            site_name=site.name,
            request_kind=request_kind,
            request_model=model_name,
            upstream_name=upstream.name,
            upstream_model=route.upstream_model,
            upstream_url=upstream.url_for(request_kind),
            upstream_api_key_env=upstream.api_key_env,
            timeout_seconds=upstream.timeout_seconds,
            extra_headers=site.extra_headers,
        )

    @staticmethod
    def _resolve_model_name(
        site: SiteConfig,
        requested_model: str | None,
        request_kind: str,
    ) -> str:
        if requested_model:
            return requested_model
        if request_kind == "images":
            return site.default_image_model
        return site.default_chat_model
