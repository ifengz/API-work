from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.check_project import check_real_gateway_config


VALID_CONFIG = {
    "listen_host": "127.0.0.1",
    "listen_port": 8080,
    "upstreams": {
        "one_api": {
            "base_url": "http://one-api:3000",
            "api_key_env": "ONE_API_MASTER_TOKEN",
        }
    },
    "model_routes": {
        "gpt-4o-mini": {
            "upstream": "one_api",
            "upstream_model": "gpt-4o-mini",
        }
    },
    "sites": [
        {
            "site_token": "site-demo-a",
            "name": "demo-a",
            "allowed_origins": ["https://image.usfan.net"],
            "allowed_models": ["gpt-4o-mini"],
            "default_chat_model": "gpt-4o-mini",
            "default_image_model": "gpt-4o-mini",
        }
    ],
}


class CheckProjectTests(unittest.TestCase):
    def test_check_real_gateway_config_reads_real_gateway_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_dir = root / "config"
            config_dir.mkdir(parents=True)
            (config_dir / "gateway.json").write_text(
                json.dumps(VALID_CONFIG),
                encoding="utf-8",
            )

            errors = check_real_gateway_config(root)

        self.assertEqual(errors, [])

    def test_check_real_gateway_config_reports_invalid_gateway_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_dir = root / "config"
            config_dir.mkdir(parents=True)
            invalid = json.loads(json.dumps(VALID_CONFIG))
            invalid["sites"][0]["default_chat_model"] = "missing-route"
            (config_dir / "gateway.json").write_text(
                json.dumps(invalid),
                encoding="utf-8",
            )

            errors = check_real_gateway_config(root)

        self.assertEqual(len(errors), 1)
        self.assertIn("config/gateway.json", errors[0])


if __name__ == "__main__":
    unittest.main()
