"""Generate and load six months of realistic seed events for the Context Engine.

Usage:
    python -m samples.data.seed_events generate [--out FILE] [--tenant ID] [--seed N]
    python -m samples.data.seed_events load [--in FILE] [--base-url URL] [--tenant ID]

The ``generate`` subcommand writes a JSON list of universal-schema events with
thick temporal patterns (daily sprint checks, weekly leave approvals, monthly
expense submissions, and a cross-app leave-to-capacity sequence). The ``load``
subcommand POSTs those events to a running engine in batches of 100.
"""

from __future__ import annotations

import argparse
import json
import random
from datetime import date
from pathlib import Path
from typing import Any

import httpx

from samples.data.event_builder import EventBuilder
from samples.data.patterns import ALL_PATTERNS

DEFAULT_TENANT_ID = "acme-corp"
DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_SEED = 42
BATCH_SIZE = 100
DEFAULT_START = date(2026, 1, 12)
DEFAULT_END = date(2026, 7, 11)
_DATA_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT = _DATA_DIR / "seed_events.json"


def generate_events(tenant_id: str, start: date, end: date, seed: int) -> list[dict[str, Any]]:
    """Generate all patterned events in chronological order for one tenant."""
    rng = random.Random(seed)
    builder = EventBuilder(tenant_id=tenant_id)
    events: list[dict[str, Any]] = []
    for pattern in ALL_PATTERNS:
        events.extend(pattern(builder, start, end, rng))
    events.sort(key=lambda event: str(event["eventTimestamp"]))
    return events


def _run_generate(args: argparse.Namespace) -> None:
    events = generate_events(args.tenant, DEFAULT_START, DEFAULT_END, args.seed)
    output_path = Path(args.out)
    output_path.write_text(json.dumps(events, indent=2), encoding="utf-8")
    print(f"Wrote {len(events)} events to {output_path}")


def _run_load(args: argparse.Namespace) -> None:
    events = _read_events(Path(args.infile))
    for event in events:
        event["tenantId"] = args.tenant
    succeeded, failed = _post_batches(events, args.base_url, args.tenant)
    print(f"Loaded {succeeded} events ({failed} failed) into {args.base_url}")


def _read_events(path: Path) -> list[dict[str, Any]]:
    parsed: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, list):
        raise ValueError(f"expected a JSON list of events in {path}")
    return [dict(event) for event in parsed]


def _post_batches(events: list[dict[str, Any]], base_url: str, tenant_id: str) -> tuple[int, int]:
    succeeded = 0
    failed = 0
    headers = {"X-Tenant-Id": tenant_id}
    with httpx.Client(base_url=base_url, timeout=30.0) as client:
        for start in range(0, len(events), BATCH_SIZE):
            chunk = events[start : start + BATCH_SIZE]
            response = client.post("/v1/events/batch", json={"events": chunk}, headers=headers)
            response.raise_for_status()
            accepted, rejected = _count_batch_result(response.json(), len(chunk))
            succeeded += accepted
            failed += rejected
    return succeeded, failed


def _count_batch_result(body: Any, chunk_size: int) -> tuple[int, int]:
    results = body.get("results") if isinstance(body, dict) else None
    if not isinstance(results, list):
        return chunk_size, 0
    accepted = sum(1 for item in results if str(item.get("status", "")).startswith("2"))
    return accepted, len(results) - accepted


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate or load Context Engine seed events.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="Write seed events to a JSON file.")
    generate.add_argument("--out", default=str(DEFAULT_OUTPUT), help="Output JSON path.")
    generate.add_argument("--tenant", default=DEFAULT_TENANT_ID, help="Tenant identifier.")
    generate.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Deterministic RNG seed.")
    generate.set_defaults(func=_run_generate)

    load = subparsers.add_parser("load", help="POST seed events to a running engine.")
    load.add_argument("--in", dest="infile", default=str(DEFAULT_OUTPUT), help="Input JSON path.")
    load.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Engine base URL.")
    load.add_argument("--tenant", default=DEFAULT_TENANT_ID, help="Tenant identifier.")
    load.set_defaults(func=_run_load)
    return parser


def main() -> None:
    """Parse CLI arguments and dispatch to the selected subcommand."""
    parser = _build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
