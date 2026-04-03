from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_vertex_pool_from_dir import (
    DEFAULT_VERTEX_MODELS,
    build_vertex_pool_config,
    copy_credentials,
    load_vertex_credentials,
    select_credentials,
)


def write_json(path: Path, project_id: str, client_email: str) -> None:
    payload = {
        "type": "service_account",
        "project_id": project_id,
        "client_email": client_email,
        "private_key": "dummy",
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


class VertexPoolBuilderTests(unittest.TestCase):
    def test_build_vertex_pool_config_creates_one_deployment_per_model_and_credential(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_json(root / "a.json", "proj-a", "svc-a@proj-a.iam.gserviceaccount.com")
            write_json(root / "b.json", "proj-b", "svc-b@proj-b.iam.gserviceaccount.com")

            credentials = load_vertex_credentials(root)
            selected = select_credentials(credentials, None, None)
            config = build_vertex_pool_config(selected, DEFAULT_VERTEX_MODELS[:2], "global")

        self.assertEqual(4, len(config["deployments"]))
        aliases = {deployment["alias"] for deployment in config["deployments"]}
        self.assertEqual(set(DEFAULT_VERTEX_MODELS[:2]), aliases)
        self.assertEqual({"proj-a", "proj-b"}, {deployment["project_id"] for deployment in config["deployments"]})

    def test_copy_credentials_writes_deduplicated_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_json(root / "a.json", "proj-a", "svc-a@proj-a.iam.gserviceaccount.com")
            write_json(root / "b.json", "proj-a", "svc-a@proj-a.iam.gserviceaccount.com")
            write_json(root / "c.json", "proj-a", "svc-b@proj-a.iam.gserviceaccount.com")

            credentials = load_vertex_credentials(root)
            output_dir = root / "out"
            copied = copy_credentials(credentials, output_dir)
            self.assertEqual(2, len(copied))
            self.assertTrue(all(path.exists() for path in copied.values()))


if __name__ == "__main__":
    unittest.main()
