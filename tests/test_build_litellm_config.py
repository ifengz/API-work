from __future__ import annotations

import unittest

from scripts.build_litellm_config import render_litellm_yaml


class BuildLiteLLMConfigTests(unittest.TestCase):
    def test_render_supports_literal_project_and_location(self) -> None:
        config = {
            "master_key_env": "LITELLM_MASTER_KEY",
            "salt_key_env": "LITELLM_SALT_KEY",
            "router": {
                "routing_strategy": "simple-shuffle",
                "num_retries": 2,
                "timeout": 120,
                "fallbacks": {
                    "gemini-2.5-pro": ["gemini-2.5-flash"],
                },
            },
            "deployments": [
                {
                    "alias": "gemini-2.5-flash",
                    "provider_model": "vertex_ai/gemini-2.5-flash",
                    "project_id": "proj-a",
                    "location": "global",
                    "credentials_file": "/app/credentials/imported/proj-a-01.json",
                    "rpm": 120,
                }
            ],
        }

        rendered = render_litellm_yaml(config)

        self.assertIn("vertex_project: proj-a", rendered)
        self.assertIn("vertex_location: global", rendered)
        self.assertIn("model_name: gemini-2.5-flash", rendered)

    def test_render_supports_empty_fallbacks(self) -> None:
        config = {
            "master_key_env": "LITELLM_MASTER_KEY",
            "salt_key_env": "LITELLM_SALT_KEY",
            "router": {
                "routing_strategy": "simple-shuffle",
                "num_retries": 2,
                "timeout": 120,
                "fallbacks": {},
            },
            "deployments": [
                {
                    "alias": "gemini-3-flash-preview",
                    "provider_model": "vertex_ai/gemini-3-flash-preview",
                    "project_id": "proj-a",
                    "location": "global",
                    "credentials_file": "/app/credentials/imported/proj-a-01.json",
                    "rpm": 120,
                }
            ],
        }

        rendered = render_litellm_yaml(config)

        self.assertIn("fallbacks: []", rendered)


if __name__ == "__main__":
    unittest.main()
