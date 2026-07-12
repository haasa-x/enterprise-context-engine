"""Simulate a legacy enterprise app by appending audit log lines to a file.

Each line uses a simple, parseable ``key=value`` format, for example:

    2026-01-05T09:03:00Z user=emp001 action=view_report object=report:Q1 app=legacy-erp

Usage:
    python log_generator.py --count 50            # write 50 lines and exit
    python log_generator.py --follow --interval 2 # append a line every 2 seconds
"""

from __future__ import annotations

import argparse
import random
import time
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_LOG_PATH = Path(__file__).resolve().parent / "audit.log"
APP_NAME = "legacy-erp"

_USERS = ("emp001", "emp002", "emp003", "emp004", "emp005")
_ACTIONS = (
    ("view_report", "report"),
    ("approve_invoice", "invoice"),
    ("update_record", "record"),
    ("export_ledger", "ledger"),
    ("search_vendor", "vendor"),
)
_OBJECT_SUFFIXES = ("Q1", "Q2", "Q3", "2026-07", "north", "south", "acct-4471")


def build_log_line(rng: random.Random) -> str:
    """Construct a single audit log line with the current UTC timestamp."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    user = rng.choice(_USERS)
    action, object_type = rng.choice(_ACTIONS)
    object_id = f"{object_type}:{rng.choice(_OBJECT_SUFFIXES)}"
    return f"{timestamp} user={user} action={action} object={object_id} app={APP_NAME}"


def append_lines(path: Path, count: int, rng: random.Random) -> None:
    """Append ``count`` audit log lines to ``path``."""
    with path.open("a", encoding="utf-8") as log_file:
        for _ in range(count):
            log_file.write(build_log_line(rng) + "\n")


def follow(path: Path, interval_seconds: float, rng: random.Random) -> None:
    """Continuously append one log line per ``interval_seconds`` until interrupted."""
    print(f"Appending to {path} every {interval_seconds}s (Ctrl-C to stop)")
    while True:
        append_lines(path, 1, rng)
        time.sleep(interval_seconds)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate legacy audit log lines.")
    parser.add_argument("--path", default=str(DEFAULT_LOG_PATH), help="Log file path.")
    parser.add_argument("--count", type=int, default=50, help="Lines to write when not following.")
    parser.add_argument("--follow", action="store_true", help="Append continuously.")
    parser.add_argument("--interval", type=float, default=2.0, help="Seconds between lines.")
    parser.add_argument("--seed", type=int, default=7, help="Deterministic RNG seed.")
    return parser.parse_args()


def main() -> None:
    """Parse arguments and either write a fixed count or follow indefinitely."""
    args = _parse_args()
    rng = random.Random(args.seed)
    path = Path(args.path)
    if args.follow:
        follow(path, args.interval, rng)
    else:
        append_lines(path, args.count, rng)
        print(f"Wrote {args.count} lines to {path}")


if __name__ == "__main__":
    main()
