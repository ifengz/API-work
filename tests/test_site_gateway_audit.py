from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from site_gateway.audit import AuditEvent, AuditStore


class AuditStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "audit.db"
        self.store = AuditStore(self.db_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_minute_and_dimension_summaries_are_derived_from_same_events(self) -> None:
        now = datetime(2026, 4, 5, 3, 40, tzinfo=UTC)
        self.store.record_event(
            AuditEvent(
                created_at=now - timedelta(minutes=2, seconds=10),
                trace_id="trace-1",
                site_name="image-usfan",
                site_token_preview="sk-abcd...wxyz",
                site_token_fingerprint="token-a",
                request_kind="chat",
                request_model="gemini-2.5-flash",
                upstream_name="litellm",
                upstream_model="gemini-2.5-flash",
                status_code=200,
                error_code=None,
                duration_ms=1200,
                prompt_tokens=11,
                completion_tokens=7,
                total_tokens=18,
                image_count=None,
            )
        )
        self.store.record_event(
            AuditEvent(
                created_at=now - timedelta(minutes=2, seconds=2),
                trace_id="trace-2",
                site_name="image-usfan",
                site_token_preview="sk-abcd...wxyz",
                site_token_fingerprint="token-a",
                request_kind="images",
                request_model="gemini-2.5-flash-image",
                upstream_name="litellm",
                upstream_model="gemini-2.5-flash-image",
                status_code=200,
                error_code=None,
                duration_ms=3200,
                prompt_tokens=None,
                completion_tokens=None,
                total_tokens=None,
                image_count=2,
            )
        )
        self.store.record_event(
            AuditEvent(
                created_at=now - timedelta(minutes=1, seconds=5),
                trace_id="trace-3",
                site_name="studio-b",
                site_token_preview="sk-ffff...9999",
                site_token_fingerprint="token-b",
                request_kind="chat",
                request_model="gpt-4o-mini",
                upstream_name="one_api",
                upstream_model="gpt-4o-mini",
                status_code=403,
                error_code="MODEL_NOT_ALLOWED",
                duration_ms=90,
                prompt_tokens=None,
                completion_tokens=None,
                total_tokens=None,
                image_count=None,
            )
        )

        minute_rows = self.store.summarize_by_minute(window_minutes=5, now=now)
        site_rows = self.store.summarize_by_dimension("site_name", window_minutes=5, now=now)
        token_rows = self.store.summarize_by_dimension("site_token", window_minutes=5, now=now)
        model_rows = self.store.summarize_by_dimension("request_model", window_minutes=5, now=now)

        self.assertEqual(sum(row["request_count"] for row in minute_rows), 3)
        self.assertEqual(minute_rows[0]["minute"], "2026-04-05T03:37:00Z")
        self.assertEqual(minute_rows[0]["request_count"], 2)
        self.assertEqual(minute_rows[1]["minute"], "2026-04-05T03:38:00Z")
        self.assertEqual(minute_rows[1]["failure_count"], 1)

        self.assertEqual(site_rows[0]["site_name"], "image-usfan")
        self.assertEqual(site_rows[0]["request_count"], 2)
        self.assertEqual(site_rows[0]["total_tokens"], 18)
        self.assertEqual(site_rows[0]["image_count"], 2)

        self.assertEqual(token_rows[0]["site_token_fingerprint"], "token-a")
        self.assertEqual(token_rows[0]["site_token_preview"], "sk-abcd...wxyz")
        self.assertEqual(token_rows[0]["request_count"], 2)

        image_model_row = next(
            row for row in model_rows if row["request_model"] == "gemini-2.5-flash-image"
        )
        self.assertEqual(image_model_row["image_count"], 2)

    def test_recent_events_keep_newest_first(self) -> None:
        now = datetime(2026, 4, 5, 3, 40, tzinfo=UTC)
        self.store.record_event(
            AuditEvent(
                created_at=now - timedelta(seconds=30),
                trace_id="trace-new",
                site_name="image-usfan",
                site_token_preview="sk-abcd...wxyz",
                site_token_fingerprint="token-a",
                request_kind="chat",
                request_model="gemini-2.5-flash",
                upstream_name="litellm",
                upstream_model="gemini-2.5-flash",
                status_code=200,
                error_code=None,
                duration_ms=100,
                prompt_tokens=1,
                completion_tokens=2,
                total_tokens=3,
                image_count=None,
            )
        )
        self.store.record_event(
            AuditEvent(
                created_at=now - timedelta(minutes=1),
                trace_id="trace-old",
                site_name="studio-b",
                site_token_preview="sk-ffff...9999",
                site_token_fingerprint="token-b",
                request_kind="chat",
                request_model="gpt-4o-mini",
                upstream_name="one_api",
                upstream_model="gpt-4o-mini",
                status_code=200,
                error_code=None,
                duration_ms=200,
                prompt_tokens=2,
                completion_tokens=3,
                total_tokens=5,
                image_count=None,
            )
        )

        recent = self.store.list_recent_events(limit=2)
        self.assertEqual([row["trace_id"] for row in recent], ["trace-new", "trace-old"])


if __name__ == "__main__":
    unittest.main()
