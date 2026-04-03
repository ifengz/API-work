from __future__ import annotations

import argparse
import json
from pathlib import Path


def yaml_quote(value: str) -> str:
    return value.replace(":", "\\:")


def resolve_scalar(deployment: dict[str, object], literal_key: str, env_key: str) -> str:
    literal_value = str(deployment.get(literal_key, "")).strip()
    if literal_value:
        return literal_value
    env_value = str(deployment.get(env_key, "")).strip()
    if env_value:
        return f"os.environ/{env_value}"
    raise KeyError(f"missing {literal_key} or {env_key}")


def render_litellm_yaml(config: dict[str, object]) -> str:
    lines: list[str] = ["model_list:"]
    deployments = config.get("deployments", [])
    for deployment in deployments:
        lines.extend(
            [
                f"  - model_name: {deployment['alias']}",
                "    litellm_params:",
                f"      model: {deployment['provider_model']}",
                f"      vertex_project: {resolve_scalar(deployment, 'project_id', 'project_env')}",
                f"      vertex_location: {resolve_scalar(deployment, 'location', 'location_env')}",
                f"      vertex_credentials: {deployment['credentials_file']}",
                f"      rpm: {int(deployment.get('rpm', 60))}",
            ]
        )

    lines.extend(
        [
            "",
            "litellm_settings:",
            f"  master_key: os.environ/{config.get('master_key_env', 'LITELLM_MASTER_KEY')}",
            f"  salt_key: os.environ/{config.get('salt_key_env', 'LITELLM_SALT_KEY')}",
            "  json_logs: true",
            "",
            "router_settings:",
        ]
    )

    router = dict(config.get("router", {}))
    lines.append(f"  routing_strategy: {router.get('routing_strategy', 'simple-shuffle')}")
    lines.append(f"  num_retries: {int(router.get('num_retries', 2))}")
    lines.append(f"  timeout: {int(router.get('timeout', 120))}")

    fallbacks = router.get("fallbacks", {})
    lines.append("  fallbacks:")
    for model_name, fallback_models in fallbacks.items():
        lines.append(f"    - {model_name}:")
        for fallback_model in fallback_models:
            lines.append(f"        - {fallback_model}")

    lines.extend(
        [
            "",
            "general_settings:",
            "  disable_spend_logs: false",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build LiteLLM YAML from Vertex pool JSON.")
    parser.add_argument("--input", required=True, help="vertex pool json path")
    parser.add_argument("--output", required=True, help="target yaml path")
    args = parser.parse_args()

    config = json.loads(Path(args.input).read_text(encoding="utf-8"))
    rendered = render_litellm_yaml(config)
    Path(args.output).write_text(rendered, encoding="utf-8")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
