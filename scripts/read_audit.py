from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from site_gateway.audit import AuditStore, get_audit_db_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Read site-gateway audit data.")
    parser.add_argument(
        "--db",
        default=str(get_audit_db_path()),
        help="sqlite database path",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    recent_parser = subparsers.add_parser("recent", help="show recent events")
    recent_parser.add_argument("--limit", type=int, default=20)

    minute_parser = subparsers.add_parser("minutes", help="show per-minute summary")
    minute_parser.add_argument("--window", type=int, default=60)

    summary_parser = subparsers.add_parser("summary", help="show grouped summary")
    summary_parser.add_argument(
        "--group-by",
        choices=("site_name", "site_token", "request_model"),
        required=True,
    )
    summary_parser.add_argument("--window", type=int, default=None)

    args = parser.parse_args()
    store = AuditStore(args.db)

    if args.command == "recent":
        payload = store.list_recent_events(limit=args.limit)
    elif args.command == "minutes":
        payload = store.summarize_by_minute(window_minutes=args.window)
    else:
        payload = store.summarize_by_dimension(
            args.group_by,
            window_minutes=args.window,
        )

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
