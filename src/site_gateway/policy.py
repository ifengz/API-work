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
        return self.resolve_candidates(site_token, requested_model, request_kind)[0]

    def resolve_candidates(
        self,
        site_token: str,
        requested_model: str | None,
        request_kind: str,
    ) -> tuple[RoutingDecision, ...]:
        if request_kind not in {"chat", "images"}:
            raise PolicyError(f"unsupported request kind: {request_kind}")

        try:
            site = self.config.get_site(site_token)
        except ConfigError as exc:
            raise PolicyError(str(exc)) from exc

        model_names = self._resolve_model_names(site, requested_model, request_kind)
        return tuple(
            self._build_decision(site, request_kind, model_name)
            for model_name in model_names
        )

    def _build_decision(
        self,
        site: SiteConfig,
        request_kind: str,
        model_name: str,
    ) -> RoutingDecision:
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

    def resolve_multimodal_chat_decision(
        self,
        decision: RoutingDecision,
        *,
        input_image_count: int,
    ) -> RoutingDecision:
        if decision.request_kind != "chat" or input_image_count < 1:
            return decision

        route = self.config.model_routes.get(decision.request_model)
        if route is None or route.multimodal_chat_upstream is None:
            return decision

        try:
            upstream = self.config.get_upstream(route.multimodal_chat_upstream)
        except ConfigError as exc:
            raise PolicyError(str(exc)) from exc

        return RoutingDecision(
            site_token=decision.site_token,
            site_name=decision.site_name,
            request_kind=decision.request_kind,
            request_model=decision.request_model,
            upstream_name=upstream.name,
            upstream_model=route.multimodal_chat_upstream_model
            or decision.request_model,
            upstream_url=upstream.url_for("chat"),
            upstream_api_key_env=upstream.api_key_env,
            timeout_seconds=upstream.timeout_seconds,
            extra_headers=decision.extra_headers,
        )

    @staticmethod
    def _resolve_model_names(
        site: SiteConfig,
        requested_model: str | None,
        request_kind: str,
    ) -> tuple[str, ...]:
        if requested_model:
            return (requested_model,)
        if request_kind == "images":
            return site.image_model_candidates
        return site.chat_model_candidates
