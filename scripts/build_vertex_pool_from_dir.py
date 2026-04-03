from __future__ import annotations

import argparse
import json
import re
import shutil
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


DEFAULT_VERTEX_MODELS = [
    "gemini-3-flash-preview",
    "gemini-3.1-pro-preview",
    "gemini-3.1-flash-image-preview",
    "gemini-3-pro-image-preview",
    "gemini-3.1-flash-lite-preview",
    "gemini-2.5-flash-image",
    "gemini-2.5-pro",
    "gemini-pro-latest",
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
]

MODEL_RPM = {
    "gemini-2.5-pro": 60,
    "gemini-2.5-flash-image": 30,
    "gemini-3.1-flash-image-preview": 30,
    "gemini-3-pro-image-preview": 30,
}

MODEL_FALLBACKS = {
    "gemini-2.5-pro": ["gemini-2.5-flash"],
    "gemini-3.1-pro-preview": ["gemini-3-flash-preview", "gemini-2.5-flash"],
}


@dataclass(frozen=True)
class VertexCredential:
    project_id: str
    client_email: str
    path: Path
    payload: dict[str, object]


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def load_vertex_credentials(root: Path) -> list[VertexCredential]:
    unique: dict[tuple[str, str], VertexCredential] = {}
    for path in sorted(root.rglob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("type") != "service_account":
            continue
        project_id = str(payload.get("project_id", "")).strip()
        client_email = str(payload.get("client_email", "")).strip()
        if not project_id or not client_email:
            continue
        key = (project_id, client_email)
        if key in unique:
            continue
        unique[key] = VertexCredential(
            project_id=project_id,
            client_email=client_email,
            path=path,
            payload=payload,
        )
    return sorted(unique.values(), key=lambda item: (item.project_id, item.client_email))


def select_credentials(
    credentials: list[VertexCredential],
    projects: set[str] | None,
    max_per_project: int | None,
) -> list[VertexCredential]:
    selected: list[VertexCredential] = []
    per_project: dict[str, int] = defaultdict(int)
    for credential in credentials:
        if projects and credential.project_id not in projects:
            continue
        if max_per_project is not None and per_project[credential.project_id] >= max_per_project:
            continue
        selected.append(credential)
        per_project[credential.project_id] += 1
    return selected


def copy_credentials(credentials: list[VertexCredential], output_dir: Path) -> dict[tuple[str, str], Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    copied: dict[tuple[str, str], Path] = {}
    per_project: dict[str, int] = defaultdict(int)
    for credential in credentials:
        per_project[credential.project_id] += 1
        project_slug = slugify(credential.project_id)
        account_slug = slugify(credential.client_email.split("@", 1)[0])
        target = output_dir / f"{project_slug}-{per_project[credential.project_id]:02d}-{account_slug}.json"
        shutil.copyfile(credential.path, target)
        copied[(credential.project_id, credential.client_email)] = target
    return copied


def rpm_for_model(model_name: str) -> int:
    return MODEL_RPM.get(model_name, 120)


def provider_model_name(model_name: str) -> str:
    return f"vertex_ai/{model_name}"


def build_vertex_pool_config(
    credentials: list[VertexCredential],
    models: list[str],
    location: str,
    copied_paths: dict[tuple[str, str], Path] | None = None,
) -> dict[str, object]:
    deployments: list[dict[str, object]] = []
    for credential in credentials:
        key = (credential.project_id, credential.client_email)
        copied_path = copied_paths[key] if copied_paths else credential.path
        credentials_file = f"/app/credentials/imported/{copied_path.name}"
        for model_name in models:
            deployments.append(
                {
                    "alias": model_name,
                    "provider_model": provider_model_name(model_name),
                    "project_id": credential.project_id,
                    "location": location,
                    "credentials_file": credentials_file,
                    "rpm": rpm_for_model(model_name),
                }
            )
    return {
        "master_key_env": "LITELLM_MASTER_KEY",
        "salt_key_env": "LITELLM_SALT_KEY",
        "router": {
            "routing_strategy": "simple-shuffle",
            "num_retries": 2,
            "timeout": 120,
            "fallbacks": MODEL_FALLBACKS,
        },
        "deployments": deployments,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build vertex-pool.json from a directory of service-account JSON files.")
    parser.add_argument("--vertex-dir", default="vertex", help="directory containing source json files")
    parser.add_argument("--output-config", default="config/vertex-pool.json", help="target vertex-pool json file")
    parser.add_argument(
        "--output-credentials-dir",
        default="credentials/imported",
        help="directory where deduplicated credential files will be copied",
    )
    parser.add_argument("--projects", default="", help="comma-separated project ids to include")
    parser.add_argument("--max-per-project", type=int, default=None, help="limit credentials per project")
    parser.add_argument("--location", default="global", help="vertex region, default global")
    parser.add_argument("--models", default=",".join(DEFAULT_VERTEX_MODELS), help="comma-separated model names")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    projects = {item.strip() for item in args.projects.split(",") if item.strip()} or None
    models = [item.strip() for item in args.models.split(",") if item.strip()]
    if not models:
        raise SystemExit("models list cannot be empty")

    credentials = load_vertex_credentials(Path(args.vertex_dir))
    selected = select_credentials(credentials, projects, args.max_per_project)
    if not selected:
        raise SystemExit("no matching vertex credentials found")

    copied = copy_credentials(selected, Path(args.output_credentials_dir))
    config = build_vertex_pool_config(selected, models, args.location, copied)

    output_config = Path(args.output_config)
    output_config.parent.mkdir(parents=True, exist_ok=True)
    output_config.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"wrote {output_config}")
    print(f"credentials {len(copied)}")
    print(f"deployments {len(config['deployments'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
