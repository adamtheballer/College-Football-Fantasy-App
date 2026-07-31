#!/usr/bin/env python3
"""Fail closed when a local runtime port is already owned by another process.

The local UI must never silently attach to an API or Vite process started by a
different worktree.  In particular, Docker/Colima SSH helpers can retain a
host port after the API container has stopped.  Binding the requested host
port before startup produces a clear, actionable failure instead of a browser
that talks to a stale or dead channel.
"""

from __future__ import annotations

import argparse
import socket


def port_is_available(port: int) -> bool:
    """Return whether the loopback TCP port can be reserved right now."""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as candidate:
        candidate.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        try:
            candidate.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify a local runtime port is free before startup.")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--label", required=True, help="Human-readable service name, such as API or UI.")
    parser.add_argument(
        "--port-variable",
        required=True,
        help="Environment variable users can set to choose another port, such as API_PORT.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 1 <= args.port <= 65535:
        raise SystemExit(f"{args.label} port must be between 1 and 65535.")
    if port_is_available(args.port):
        return 0
    raise SystemExit(
        f"{args.label} cannot start because 127.0.0.1:{args.port} is already in use. "
        "Do not reuse that process as this runtime: stop the owner, or choose an isolated port with "
        f"{args.port_variable}=<free-port>."
    )


if __name__ == "__main__":
    raise SystemExit(main())
