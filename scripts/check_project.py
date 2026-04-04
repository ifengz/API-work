from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from site_gateway.config import ConfigError, load_gateway_config


REQUIRED_FILES = [
    "README.md",
    "Dockerfile",
    "docker-compose.yml",
    "scripts/deploy-production.sh",
    "scripts/deploy-production.env.example",
    "scripts/build_vertex_pool_from_dir.py",
    "scripts/import_vertex_channels.py",
    "src/site_gateway/server.py",
    "src/site_gateway/policy.py",
    "config/gateway.example.json",
    "config/litellm.example.yaml",
    "config/vertex-pool.example.json",
    "scripts/build_litellm_config.py",
    "tests/test_build_litellm_config.py",
    "tests/test_site_gateway.py",
    "tests/test_vertex_import.py",
    "tests/test_vertex_pool_builder.py",
]


def check_files() -> list[str]:
    errors: list[str] = []
    for relative_path in REQUIRED_FILES:
        if not (ROOT / relative_path).exists():
            errors.append(f"missing file: {relative_path}")
    return errors


def check_json_files() -> list[str]:
    errors: list[str] = []
    for relative_path in ["config/gateway.example.json", "config/vertex-pool.example.json"]:
        try:
            json.loads((ROOT / relative_path).read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"invalid json: {relative_path}: {exc}")
    return errors


def check_litellm_template() -> list[str]:
    errors: list[str] = []
    content = (ROOT / "config/litellm.example.yaml").read_text(encoding="utf-8")
    for marker in ["model_list:", "litellm_settings:", "router_settings:", "fallbacks:"]:
        if marker not in content:
            errors.append(f"litellm template missing marker: {marker}")
    return errors


def check_real_gateway_config(root: Path = ROOT) -> list[str]:
    gateway_path = root / "config/gateway.json"
    try:
        load_gateway_config(gateway_path)
    except FileNotFoundError:
        return ["missing file: config/gateway.json"]
    except (ConfigError, json.JSONDecodeError) as exc:
        return [f"invalid config/gateway.json: {exc}"]
    return []


def main() -> int:
    errors = (
        check_files()
        + check_json_files()
        + check_litellm_template()
        + check_real_gateway_config()
    )
    if errors:
        for error in errors:
            print(error)
        return 1

    print("project skeleton looks consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
