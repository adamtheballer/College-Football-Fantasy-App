"""Retired direct live-score synchronizer.

Historically this script fetched a provider, overwrote ``PlayerStat`` rows, and
recalculated league totals in one process.  It is retained only so an old run
command fails safely and explains the supported pipeline.  It must never
perform network requests or mutate any database records.
"""

from __future__ import annotations

import argparse


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Retired direct live-score synchronizer.")
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--league-id", type=int, default=None)
    parser.add_argument("--provider", default="sportsdata")
    parser.add_argument("--watch", action="store_true")
    return parser.parse_args()


def run_once(_args: argparse.Namespace) -> None:
    raise RuntimeError(
        "Direct live-score synchronization is retired. Use an approved provider adapter to persist immutable "
        "events/revisions, then enqueue durable score_revision work; no direct provider-to-score path is allowed."
    )


def main() -> None:
    run_once(parse_args())


if __name__ == "__main__":
    main()
