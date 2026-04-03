from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


REQUIRED_FILES = [
    "README.md",
    "Dockerfile",
    "docker-compose.yml",
    "src/site_gateway/server.py",
    "src/site_gateway/policy.py",
    "config/gateway.example.json",
    "config/litellm.example.yaml",
    "config/vertex-pool.example.json",
    "scripts/build_litellm_config.py",
    "tests/test_site_gateway.py",
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


def main() -> int:
    errors = check_files() + check_json_files() + check_litellm_template()
    if errors:
        for error in errors:
            print(error)
        return 1

    print("project skeleton looks consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
