"""Tail a legacy audit log, transform each line into a universal-schema event,
and POST it to a running Context Engine (Path 3 — log listener).

Usage:
    python log_listener.py                       # follow audit.log from the end
    python log_listener.py --from-start          # replay the whole file, then follow
    python log_listener.py --base-url URL --tenant ID

Parses lines of the form:
    2026-01-05T09:03:00Z user=emp001 action=view_report object=report:Q1 app=legacy-erp
"""

from __future__ import annotations

import argparse
import time
import uuid
from pathlib import Path
from typing import Any

import httpx

DEFAULT_LOG_PATH = Path(__file__).resolve().parent / "audit.log"
DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_TENANT_ID = "acme-corp"
APPLICATION_INSTANCE_ID = "legacy-erp-prod"
CONNECTOR_NAME = "log-listener"
CONNECTOR_VERSION = "0.1.0"
POLL_INTERVAL_SECONDS = 1.0

# Maps an action-verb prefix in the log to a universal-schema action category.
_CATEGORY_BY_VERB = {
    "view": "read",
    "export": "read",
    "search": "search",
    "approve": "approve",
    "reject": "reject",
    "update": "update",
    "create": "create",
    "delete": "delete",
}


def parse_log_line(line: str) -> dict[str, str] | None:
    """Parse a ``key=value`` audit line into a flat dict, or None if malformed."""
    parts = line.strip().split()
    if len(parts) < 5:
        return None
    fields: dict[str, str] = {"timestamp": parts[0]}
    for token in parts[1:]:
        if "=" not in token:
            return None
        key, value = token.split("=", 1)
        fields[key] = value
    required = ("user", "action", "object", "app")
    if any(key not in fields for key in required):
        return None
    return fields


def _category_for(action: str) -> str:
    verb = action.split("_", 1)[0]
    return _CATEGORY_BY_VERB.get(verb, "read")


def _iso_timestamp(raw: str) -> str:
    return raw.replace("Z", "+00:00")


def to_event(fields: dict[str, str], tenant_id: str) -> dict[str, Any]:
    """Transform a parsed log line into a universal-schema event dict."""
    object_type, _, object_id = fields["object"].partition(":")
    return {
        "schemaVersion": "1.0.0",
        "eventId": str(uuid.uuid4()),
        "tenantId": tenant_id,
        "applicationId": fields["app"],
        "applicationInstanceId": APPLICATION_INSTANCE_ID,
        "environment": "production",
        "eventTimestamp": _iso_timestamp(fields["timestamp"]),
        "actor": {"nativeUserId": fields["user"], "userIdType": "app_native_id"},
        "action": {"type": fields["action"], "category": _category_for(fields["action"])},
        "object": {
            "objectType": object_type or "record",
            "objectId": object_id or fields["object"],
        },
        "source": {"connector": CONNECTOR_NAME, "connectorVersion": CONNECTOR_VERSION},
    }


def _post_event(client: httpx.Client, event: dict[str, Any], tenant_id: str) -> bool:
    response = client.post("/v1/events", json=event, headers={"X-Tenant-Id": tenant_id})
    if response.status_code in (201, 409):
        return True
    print(f"rejected ({response.status_code}): {response.text[:120]}")
    return False


def _handle_line(line: str, client: httpx.Client, tenant_id: str) -> None:
    fields = parse_log_line(line)
    if fields is None:
        return
    if _post_event(client, to_event(fields, tenant_id), tenant_id):
        print(f"forwarded {fields['user']} {fields['action']} {fields['object']}")


def tail_and_forward(path: Path, base_url: str, tenant_id: str, from_start: bool) -> None:
    """Follow the log file and forward each new line as an event, until interrupted."""
    print(f"Listening to {path}, posting to {base_url} (Ctrl-C to stop)")
    with (
        httpx.Client(base_url=base_url, timeout=10.0) as client,
        path.open("r", encoding="utf-8") as log_file,
    ):
        if not from_start:
            log_file.seek(0, 2)
        while True:
            line = log_file.readline()
            if line:
                _handle_line(line, client, tenant_id)
            else:
                time.sleep(POLL_INTERVAL_SECONDS)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Forward audit log lines as events.")
    parser.add_argument("--path", default=str(DEFAULT_LOG_PATH), help="Log file path.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Engine base URL.")
    parser.add_argument("--tenant", default=DEFAULT_TENANT_ID, help="Tenant identifier.")
    parser.add_argument("--from-start", action="store_true", help="Replay existing lines first.")
    return parser.parse_args()


def main() -> None:
    """Parse arguments and start tailing the audit log."""
    args = _parse_args()
    path = Path(args.path)
    if not path.exists():
        path.touch()
    tail_and_forward(path, args.base_url, args.tenant, args.from_start)


if __name__ == "__main__":
    main()
