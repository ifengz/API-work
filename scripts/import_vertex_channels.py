from __future__ import annotations

import argparse
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from http.cookiejar import CookieJar
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


class ImportError(Exception):
    pass


@dataclass(frozen=True)
class VertexCredential:
    project_id: str
    client_email: str
    path: Path
    raw_json: str


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def load_vertex_credentials(root: Path) -> list[VertexCredential]:
    unique: dict[tuple[str, str], VertexCredential] = {}
    for path in sorted(root.rglob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("type") != "service_account":
            continue
        project_id = str(data.get("project_id", "")).strip()
        client_email = str(data.get("client_email", "")).strip()
        if not project_id or not client_email:
            continue
        key = (project_id, client_email)
        if key in unique:
            continue
        unique[key] = VertexCredential(
            project_id=project_id,
            client_email=client_email,
            path=path,
            raw_json=json.dumps(data, ensure_ascii=False, separators=(",", ":")),
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


def build_channel_name(prefix: str, project_id: str, ordinal: int) -> str:
    return f"{prefix}-{slugify(project_id)}-{ordinal:02d}"


def build_channel_payload(
    name: str,
    credential: VertexCredential,
    models: list[str],
    group: str,
    region: str,
) -> dict[str, object]:
    config = {
        "region": region,
        "vertex_ai_project_id": credential.project_id,
        "vertex_ai_adc": credential.raw_json,
    }
    return {
        "name": name,
        "type": 42,
        "group": group,
        "models": ",".join(models),
        "key": f"{region}|{credential.project_id}|{credential.raw_json}",
        "status": 1,
        "model_mapping": "",
        "system_prompt": "",
        "base_url": "",
        "other": "",
        "config": json.dumps(config, ensure_ascii=False, separators=(",", ":")),
    }


class OneAPIClient:
    def __init__(self, server: str, access_token: str | None = None) -> None:
        self.server = server.rstrip("/")
        self.cookie_jar = CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookie_jar))
        self.access_token = access_token

    def _request(self, method: str, path: str, payload: dict[str, object] | None = None) -> dict[str, object]:
        data = None
        headers = {"Content-Type": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(f"{self.server}{path}", data=data, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise ImportError(f"{method} {path} failed: {exc.code} {body}") from exc
        except urllib.error.URLError as exc:
            raise ImportError(f"{method} {path} failed: {exc.reason}") from exc

    def login(self, username: str, password: str) -> None:
        response = self._request(
            "POST",
            "/api/user/login",
            {"username": username, "password": password},
        )
        if not response.get("success"):
            raise ImportError(str(response.get("message", "login failed")))

    def search_channels(self, keyword: str) -> list[dict[str, object]]:
        query = urllib.parse.quote(keyword, safe="")
        response = self._request("GET", f"/api/channel/search?keyword={query}")
        if not response.get("success"):
            raise ImportError(str(response.get("message", "search failed")))
        return list(response.get("data") or [])

    def create_channel(self, payload: dict[str, object]) -> None:
        response = self._request("POST", "/api/channel/", payload)
        if not response.get("success"):
            raise ImportError(str(response.get("message", "create channel failed")))

    def test_channel(self, channel_id: int, model: str) -> dict[str, object]:
        query = urllib.parse.quote(model, safe="")
        response = self._request("GET", f"/api/channel/test/{channel_id}?model={query}")
        if not response.get("success"):
            raise ImportError(str(response.get("message", "test failed")))
        return response


def find_exact_channel(channels: list[dict[str, object]], name: str) -> dict[str, object] | None:
    for channel in channels:
        if channel.get("name") == name:
            return channel
    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bulk import VertexAI channels into One-API.")
    parser.add_argument("--server", required=True, help="One-API base URL, e.g. http://api-work.usfan.net:5000")
    parser.add_argument("--vertex-dir", default="vertex", help="directory containing service-account JSON files")
    parser.add_argument("--group", default="default", help="One-API group name")
    parser.add_argument("--region", default="global", help="Vertex region, default global")
    parser.add_argument("--name-prefix", default="vertex", help="channel name prefix")
    parser.add_argument("--projects", default="", help="comma-separated project ids to import")
    parser.add_argument("--max-per-project", type=int, default=None, help="limit imported credentials per project")
    parser.add_argument("--models", default=",".join(DEFAULT_VERTEX_MODELS), help="comma-separated model list")
    parser.add_argument("--test-model", default="gemini-2.5-flash", help="model used for channel test")
    parser.add_argument("--access-token", default="", help="One-API admin access token")
    parser.add_argument("--username", default="", help="One-API admin username if not using access token")
    parser.add_argument("--password", default="", help="One-API admin password if not using access token")
    parser.add_argument("--dry-run", action="store_true", help="print planned channels without creating them")
    parser.add_argument("--skip-test", action="store_true", help="skip channel test after creation")
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

    per_project_index: dict[str, int] = defaultdict(int)
    planned: list[tuple[str, VertexCredential, dict[str, object]]] = []
    for credential in selected:
        per_project_index[credential.project_id] += 1
        name = build_channel_name(args.name_prefix, credential.project_id, per_project_index[credential.project_id])
        payload = build_channel_payload(name, credential, models, args.group, args.region)
        planned.append((name, credential, payload))

    if args.dry_run:
        for name, credential, _payload in planned:
            print(f"PLAN {name} | {credential.project_id} | {credential.client_email} | {credential.path}")
        return 0

    client = OneAPIClient(args.server, access_token=args.access_token or None)
    if not args.access_token:
        if not args.username or not args.password:
            raise SystemExit("provide --access-token or --username/--password")
        client.login(args.username, args.password)

    created_count = 0
    tested_count = 0
    for name, credential, payload in planned:
        existing = find_exact_channel(client.search_channels(name), name)
        if existing is None:
            client.create_channel(payload)
            created_count += 1
            existing = find_exact_channel(client.search_channels(name), name)
        if existing is None:
            raise SystemExit(f"channel created but not found by name: {name}")
        channel_id = int(existing["id"])
        print(f"READY {name} | id={channel_id} | {credential.project_id} | {credential.client_email}")
        if args.skip_test:
            continue
        result = client.test_channel(channel_id, args.test_model)
        tested_count += 1
        print(
            f"TEST OK {name} | model={args.test_model} | time={result.get('time')} | message={result.get('message', '')}"
        )

    print(f"DONE created={created_count} tested={tested_count} total={len(planned)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
