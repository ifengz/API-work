from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


DEFAULT_AUDIT_DB = Path("data/site-gateway/audit.db")
SUMMARY_DIMENSIONS = {
    "site_name": ("site_name", "site_name"),
    "site_token": ("site_token_fingerprint", "site_token_fingerprint"),
    "request_model": ("request_model", "request_model"),
}


@dataclass(frozen=True)
class AuditEvent:
    created_at: datetime
    trace_id: str
    site_name: str | None
    site_token_preview: str | None
    site_token_fingerprint: str | None
    request_kind: str | None
    request_model: str | None
    upstream_name: str | None
    upstream_model: str | None
    attempted_models_json: str | None
    status_code: int
    error_code: str | None
    duration_ms: int
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    image_count: int | None


@dataclass(frozen=True)
class ResponseUsage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    image_count: int | None = None


class AuditStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def record_event(self, event: AuditEvent) -> None:
        payload = asdict(event)
        payload["created_at"] = format_timestamp(event.created_at)
        payload["created_minute"] = format_minute_bucket(event.created_at)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO request_audit (
                    created_at,
                    created_minute,
                    trace_id,
                    site_name,
                    site_token_preview,
                    site_token_fingerprint,
                    request_kind,
                    request_model,
                    upstream_name,
                    upstream_model,
                    attempted_models_json,
                    status_code,
                    error_code,
                    duration_ms,
                    prompt_tokens,
                    completion_tokens,
                    total_tokens,
                    image_count
                ) VALUES (
                    :created_at,
                    :created_minute,
                    :trace_id,
                    :site_name,
                    :site_token_preview,
                    :site_token_fingerprint,
                    :request_kind,
                    :request_model,
                    :upstream_name,
                    :upstream_model,
                    :attempted_models_json,
                    :status_code,
                    :error_code,
                    :duration_ms,
                    :prompt_tokens,
                    :completion_tokens,
                    :total_tokens,
                    :image_count
                )
                """,
                payload,
            )

    def list_recent_events(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    created_at,
                    trace_id,
                    site_name,
                    site_token_preview,
                    site_token_fingerprint,
                    request_kind,
                    request_model,
                    upstream_name,
                    upstream_model,
                    attempted_models_json,
                    status_code,
                    error_code,
                    duration_ms,
                    prompt_tokens,
                    completion_tokens,
                    total_tokens,
                    image_count
                FROM request_audit
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (max(limit, 1),),
            ).fetchall()
        return [_row_to_event_dict(row) for row in rows]

    def summarize_by_minute(
        self,
        window_minutes: int,
        *,
        now: datetime | None = None,
    ) -> list[dict[str, Any]]:
        params = (format_timestamp(resolve_cutoff(window_minutes, now)),)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    created_minute AS minute,
                    COUNT(*) AS request_count,
                    SUM(CASE WHEN status_code < 400 THEN 1 ELSE 0 END) AS success_count,
                    SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) AS failure_count,
                    COALESCE(SUM(total_tokens), 0) AS total_tokens,
                    COALESCE(SUM(image_count), 0) AS image_count
                FROM request_audit
                WHERE created_at >= ?
                GROUP BY created_minute
                ORDER BY created_minute ASC
                """,
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def summarize_by_dimension(
        self,
        dimension: str,
        *,
        window_minutes: int | None = None,
        now: datetime | None = None,
    ) -> list[dict[str, Any]]:
        try:
            group_column, select_column = SUMMARY_DIMENSIONS[dimension]
        except KeyError as exc:
            raise ValueError(f"unsupported summary dimension: {dimension}") from exc

        alias_name = "site_token_fingerprint" if dimension == "site_token" else dimension
        select_fields = [
            f"{select_column} AS {alias_name}",
            "COUNT(*) AS request_count",
            "SUM(CASE WHEN status_code < 400 THEN 1 ELSE 0 END) AS success_count",
            "SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) AS failure_count",
            "COALESCE(SUM(total_tokens), 0) AS total_tokens",
            "COALESCE(SUM(image_count), 0) AS image_count",
        ]
        if dimension == "site_token":
            select_fields.insert(1, "site_token_preview")

        where_clause = ""
        params: tuple[Any, ...] = ()
        if window_minutes is not None:
            where_clause = "WHERE created_at >= ?"
            params = (format_timestamp(resolve_cutoff(window_minutes, now)),)

        query = f"""
            SELECT
                {", ".join(select_fields)}
            FROM request_audit
            {where_clause}
            GROUP BY {group_column}
            ORDER BY request_count DESC, {group_column} ASC
        """
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS request_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    created_minute TEXT NOT NULL,
                    trace_id TEXT NOT NULL,
                    site_name TEXT,
                    site_token_preview TEXT,
                    site_token_fingerprint TEXT,
                    request_kind TEXT,
                    request_model TEXT,
                    upstream_name TEXT,
                    upstream_model TEXT,
                    attempted_models_json TEXT,
                    status_code INTEGER NOT NULL,
                    error_code TEXT,
                    duration_ms INTEGER NOT NULL,
                    prompt_tokens INTEGER,
                    completion_tokens INTEGER,
                    total_tokens INTEGER,
                    image_count INTEGER
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_request_audit_created_at
                ON request_audit (created_at)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_request_audit_site_name
                ON request_audit (site_name)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_request_audit_site_token
                ON request_audit (site_token_fingerprint)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_request_audit_request_model
                ON request_audit (request_model)
                """
            )
            self._ensure_columns(connection)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_columns(self, connection: sqlite3.Connection) -> None:
        existing_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(request_audit)").fetchall()
        }
        if "attempted_models_json" not in existing_columns:
            connection.execute(
                "ALTER TABLE request_audit ADD COLUMN attempted_models_json TEXT"
            )


def get_audit_db_path(raw_path: str | None = None) -> Path:
    if raw_path:
        return Path(raw_path)
    return DEFAULT_AUDIT_DB


def build_token_identity(site_token: str) -> tuple[str, str]:
    digest = hashlib.sha256(site_token.encode("utf-8")).hexdigest()
    return mask_token(site_token), digest[:16]


def extract_response_usage(body: bytes, content_type: str | None) -> ResponseUsage:
    if not content_type or "json" not in content_type.lower():
        return ResponseUsage()
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return ResponseUsage()

    if not isinstance(payload, dict):
        return ResponseUsage()

    usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
    data = payload.get("data")
    image_count = len(data) if isinstance(data, list) else None
    return ResponseUsage(
        prompt_tokens=coerce_int(usage.get("prompt_tokens")),
        completion_tokens=coerce_int(usage.get("completion_tokens")),
        total_tokens=coerce_int(usage.get("total_tokens")),
        image_count=image_count,
    )


def coerce_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def resolve_cutoff(window_minutes: int, now: datetime | None = None) -> datetime:
    reference = now or datetime.now(UTC)
    return reference - timedelta(minutes=max(window_minutes, 0))


def format_timestamp(value: datetime) -> str:
    utc_value = value.astimezone(UTC).replace(microsecond=0)
    return utc_value.isoformat().replace("+00:00", "Z")


def format_minute_bucket(value: datetime) -> str:
    utc_value = value.astimezone(UTC).replace(second=0, microsecond=0)
    return utc_value.isoformat().replace("+00:00", "Z")


def mask_token(value: str) -> str:
    if len(value) <= 10:
        return f"{value[:3]}...{value[-3:]}"
    return f"{value[:7]}...{value[-4:]}"


def encode_attempted_models(models: list[str] | tuple[str, ...]) -> str:
    return json.dumps(list(models), ensure_ascii=False)


def decode_attempted_models(raw_value: object) -> list[str]:
    if not isinstance(raw_value, str) or not raw_value:
        return []
    try:
        payload = json.loads(raw_value)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, str)]


def _row_to_event_dict(row: sqlite3.Row) -> dict[str, Any]:
    payload = dict(row)
    payload["attempted_models"] = decode_attempted_models(
        payload.pop("attempted_models_json", None)
    )
    return payload
