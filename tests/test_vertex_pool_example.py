from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class VertexPoolExampleTests(unittest.TestCase):
    def test_example_does_not_require_secondary_credentials_by_default(self) -> None:
        config = json.loads((ROOT / "config/vertex-pool.example.json").read_text(encoding="utf-8"))
        credential_files = {deployment["credentials_file"] for deployment in config["deployments"]}
        self.assertNotIn("/app/credentials/vertex-secondary.json", credential_files)


if __name__ == "__main__":
    unittest.main()
