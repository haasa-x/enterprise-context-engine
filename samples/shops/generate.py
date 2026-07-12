"""Generate and load realistic seed data for the SAP, Salesforce, and Oracle shops.

Usage:
    python -m samples.shops.generate generate [--shop all|sap|salesforce|oracle]
    python -m samples.shops.generate load --shop sap [--base-url URL]

``generate`` writes one ``data/<shop>_events.json`` file per shop, each a JSON
list of universal-schema events with thick, module-aware temporal patterns and
cross-application workflows. ``load`` POSTs a shop's events to a running engine
in batches, using the shop's own tenant id.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

import httpx

from samples.shops import oracle, salesforce, sap
from samples.shops.framework import Shop, generate_shop_events

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_SEED = 42
BATCH_SIZE = 100
DEFAULT_START = date(2026, 1, 12)
DEFAULT_END = date(2026, 7, 11)
_DATA_DIR = Path(__file__).resolve().parent / "data"

SHOPS: dict[str, Shop] = {
    sap.SHOP.key: sap.SHOP,
    salesforce.SHOP.key: salesforce.SHOP,
    oracle.SHOP.key: oracle.SHOP,
}


def _output_path(shop: Shop) -> Path:
    return _DATA_DIR / f"{shop.key}_events.json"


def _selected_shops(name: str) -> list[Shop]:
    if name == "all":
        return list(SHOPS.values())
    if name not in SHOPS:
        raise SystemExit(f"unknown shop {name!r}; choose from all, {', '.join(SHOPS)}")
    return [SHOPS[name]]


def _run_generate(args: argparse.Namespace) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    for shop in _selected_shops(args.shop):
        events = generate_shop_events(shop, DEFAULT_START, DEFAULT_END, args.seed)
        path = _output_path(shop)
        path.write_text(json.dumps(events, indent=2), encoding="utf-8")
        print(f"[{shop.key}] wrote {len(events)} events to {path} (tenant {shop.tenant_id})")


def _run_load(args: argparse.Namespace) -> None:
    for shop in _selected_shops(args.shop):
        events = _read_events(_output_path(shop))
        succeeded, failed = _post_batches(events, args.base_url, shop.tenant_id)
        print(f"[{shop.key}] loaded {succeeded} events ({failed} failed) into {args.base_url}")


def _read_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise SystemExit(f"{path} not found; run 'generate' first")
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
    if not isinstance(body, dict):
        return chunk_size, 0
    # The batch endpoint reports totals directly; prefer them.
    accepted = body.get("acceptedCount")
    rejected = body.get("rejectedCount")
    if isinstance(accepted, int) and isinstance(rejected, int):
        return accepted, rejected
    results = body.get("results")
    if not isinstance(results, list):
        return chunk_size, 0
    ok = sum(1 for item in results if item.get("status") == "accepted")
    return ok, len(results) - ok


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate or load enterprise shop seed data.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="Write shop events to JSON files.")
    generate.add_argument("--shop", default="all", help="all, sap, salesforce, or oracle.")
    generate.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Deterministic RNG seed.")
    generate.set_defaults(func=_run_generate)

    load = subparsers.add_parser("load", help="POST shop events to a running engine.")
    load.add_argument("--shop", default="all", help="all, sap, salesforce, or oracle.")
    load.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Engine base URL.")
    load.set_defaults(func=_run_load)
    return parser


def main() -> None:
    """Parse CLI arguments and dispatch to the selected subcommand."""
    parser = _build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
