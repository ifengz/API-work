from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.import_vertex_channels import (
    DEFAULT_VERTEX_MODELS,
    build_channel_name,
    build_channel_payload,
    load_vertex_credentials,
    select_credentials,
)


def write_json(path: Path, project_id: str, client_email: str) -> None:
    payload = {
        "type": "service_account",
        "project_id": project_id,
        "client_email": client_email,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


class VertexImportTests(unittest.TestCase):
    def test_load_vertex_credentials_deduplicates_same_service_account(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_json(root / "a.json", "proj-a", "svc-a@proj-a.iam.gserviceaccount.com")
            write_json(root / "b.json", "proj-a", "svc-a@proj-a.iam.gserviceaccount.com")
            write_json(root / "c.json", "proj-a", "svc-b@proj-a.iam.gserviceaccount.com")

            credentials = load_vertex_credentials(root)

        self.assertEqual(2, len(credentials))
        self.assertEqual("svc-a@proj-a.iam.gserviceaccount.com", credentials[0].client_email)
        self.assertEqual("svc-b@proj-a.iam.gserviceaccount.com", credentials[1].client_email)

    def test_select_credentials_limits_per_project(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_json(root / "a.json", "proj-a", "svc-a@proj-a.iam.gserviceaccount.com")
            write_json(root / "b.json", "proj-a", "svc-b@proj-a.iam.gserviceaccount.com")
            write_json(root / "c.json", "proj-b", "svc-a@proj-b.iam.gserviceaccount.com")

            credentials = load_vertex_credentials(root)
            selected = select_credentials(credentials, None, 1)

        self.assertEqual(2, len(selected))
        self.assertEqual(["proj-a", "proj-b"], [item.project_id for item in selected])

    def test_build_channel_payload_uses_requested_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / "a.json"
            write_json(path, "proj-a", "svc-a@proj-a.iam.gserviceaccount.com")
            credential = load_vertex_credentials(root)[0]

        name = build_channel_name("vertex", credential.project_id, 1)
        payload = build_channel_payload(name, credential, DEFAULT_VERTEX_MODELS, "vertex", "global")

        self.assertEqual("vertex-proj-a-01", name)
        self.assertEqual(42, payload["type"])
        self.assertEqual("vertex", payload["group"])
        self.assertIn("gemini-2.5-flash", payload["models"])
        self.assertIn("gemini-3.1-pro-preview", payload["models"])
        self.assertIn("\"region\":\"global\"", payload["config"])
        self.assertIn("\"vertex_ai_project_id\":\"proj-a\"", payload["config"])
        self.assertTrue(str(payload["key"]).startswith("global|proj-a|"))


if __name__ == "__main__":
    unittest.main()
