#!/usr/bin/env python3
"""Fail a release candidate when runtime source differs from its Git commit.

Docker build contexts include both untracked files and modifications to tracked
files by default. Without this check a local image can migrate successfully
while the Git commit used for a public deployment is missing code, migrations,
or configuration that were present locally. This command is intended for CI
and pre-release verification, before the artifact is built.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


RELEASE_CRITICAL_DIRECTORIES = (
    Path("api/alembic"),
    Path("api/app"),
    Path("collegefootballfantasy_api"),
    Path("scripts"),
    Path("reports/source-imports"),
    Path("web/client"),
    Path("web/public"),
)
RELEASE_CRITICAL_FILES = {
    Path("docker-compose.yml"),
    Path("deployments.yaml"),
    Path("Dockerfile.api"),
    Path("Dockerfile.web"),
    Path("pyproject.toml"),
    Path("uv.lock"),
    Path("web/package.json"),
    Path("web/package-lock.json"),
    Path("web/vite.config.ts"),
    Path("web/nginx.conf"),
}


def is_release_critical(path: Path) -> bool:
    """Return whether a path can change the built production application."""

    if path in RELEASE_CRITICAL_FILES:
        return True
    return any(path.is_relative_to(directory) for directory in RELEASE_CRITICAL_DIRECTORIES)


def dirty_release_critical_paths(repo_root: Path) -> list[tuple[str, Path]]:
    """Return all release-critical paths that differ from ``HEAD``.

    Untracked paths are enumerated with ``git ls-files --others``. Tracked
    paths are enumerated from the index and then compared directly to ``HEAD``.
    This avoids relying on a broad ``git status`` scan, which can return an
    incomplete answer in a damaged or stale filesystem-monitor worktree.
    A release artifact must represent one immutable Git commit; every one of
    those states would break that guarantee.
    """

    untracked_result = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    tracked_result = subprocess.run(
        ["git", "ls-files"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )

    untracked = {
        Path(line)
        for line in untracked_result.stdout.splitlines()
        if line.strip() and is_release_critical(Path(line))
    }
    # This is already a release-artifact mismatch. Short-circuiting keeps the
    # gate fast and deterministic in a badly dirty worktree while still
    # failing closed. A clean candidate proceeds to the tracked-file diff
    # below, which catches modifications that would otherwise be baked in.
    if untracked:
        return [("UNTRACKED", path) for path in sorted(untracked)]

    tracked = [
        Path(line)
        for line in tracked_result.stdout.splitlines()
        if line.strip() and is_release_critical(Path(line))
    ]
    modified: set[Path] = set()
    # A direct HEAD comparison detects staged, unstaged, deleted, and renamed
    # tracked files. Chunking avoids command-length limits on a larger app.
    for start in range(0, len(tracked), 200):
        chunk = [path.as_posix() for path in tracked[start : start + 200]]
        result = subprocess.run(
            ["git", "--no-pager", "diff", "--name-only", "HEAD", "--", *chunk],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
        modified.update(Path(line) for line in result.stdout.splitlines() if line.strip())

    findings = [("MODIFIED", path) for path in modified if is_release_critical(path)]
    return sorted(set(findings), key=lambda item: (item[1].as_posix(), item[0]))


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify release-critical runtime source is tracked by Git.")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    dirty = dirty_release_critical_paths(repo_root)
    if dirty:
        print("Release source integrity FAILED: release-critical source differs from the Git release artifact.")
        for status, path in dirty:
            print(f" - {status} {path}")
        raise SystemExit(1)
    print("Release source integrity PASS: release-critical source exactly matches the Git release artifact.")


if __name__ == "__main__":
    main()



