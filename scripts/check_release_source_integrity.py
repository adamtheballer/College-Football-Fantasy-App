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
import os
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
    Path(".dockerignore"),
    Path("docker-compose.yml"),
    Path("deployments.yaml"),
    Path("Dockerfile.api"),
    Path("Dockerfile.e2e"),
    Path("Dockerfile.web"),
    Path("pyproject.toml"),
    Path("uv.lock"),
    Path("web/.dockerignore"),
    Path("web/.npmrc"),
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


def _release_scope_arguments() -> list[str]:
    """Return Git pathspecs covering every file that can affect a release."""

    return [
        *(directory.as_posix() for directory in RELEASE_CRITICAL_DIRECTORIES),
        *(file.as_posix() for file in sorted(RELEASE_CRITICAL_FILES)),
    ]


def _run_git(repo_root: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
    """Run a Git read command without triggering a worktree-wide refresh."""

    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        input=input_bytes,
        check=True,
        capture_output=True,
    )
    return result.stdout


def _nul_records(payload: bytes) -> list[bytes]:
    return [record for record in payload.split(b"\0") if record]


def _head_blob_hashes(repo_root: Path, scope: list[str]) -> dict[Path, str]:
    """Read release-critical blobs from HEAD, without consulting the worktree."""

    entries: dict[Path, str] = {}
    payload = _run_git(repo_root, "ls-tree", "-r", "-z", "HEAD", "--", *scope)
    for record in _nul_records(payload):
        metadata, raw_path = record.split(b"\t", 1)
        _mode, kind, object_id = metadata.split(maxsplit=2)
        if kind == b"blob":
            entries[Path(raw_path.decode("utf-8"))] = object_id.decode("ascii")
    return entries


def _index_blob_hashes(repo_root: Path, scope: list[str]) -> tuple[dict[Path, str], set[Path]]:
    """Read index blobs and surface unresolved merge entries as dirty source."""

    entries: dict[Path, str] = {}
    conflicted: set[Path] = set()
    payload = _run_git(repo_root, "ls-files", "--stage", "-z", "--", *scope)
    for record in _nul_records(payload):
        metadata, raw_path = record.split(b"\t", 1)
        _mode, object_id, stage = metadata.split()
        path = Path(raw_path.decode("utf-8"))
        if stage == b"0":
            entries[path] = object_id.decode("ascii")
        else:
            conflicted.add(path)
    return entries, conflicted


def _untracked_release_paths(repo_root: Path, scope: list[str]) -> set[Path]:
    payload = _run_git(repo_root, "ls-files", "--others", "--exclude-standard", "-z", "--", *scope)
    return {
        Path(record.decode("utf-8"))
        for record in _nul_records(payload)
        if is_release_critical(Path(record.decode("utf-8")))
    }


def _index_stat_metadata(repo_root: Path, scope: list[str]) -> dict[Path, tuple[int, int, int]]:
    """Read the index's cached mtime and size for each release-critical file.

    Git's cache-entry metadata is read from ``.git/index`` directly.  Comparing
    it to ``os.stat`` lets this gate find ordinary worktree modifications
    without asking Git to refresh every file in a large macOS worktree.
    """

    entries: dict[Path, tuple[int, int, int]] = {}
    current_path: Path | None = None
    current_mtime: tuple[int, int] | None = None
    current_size: int | None = None

    def save_current() -> None:
        if current_path is not None and current_mtime is not None and current_size is not None:
            entries[current_path] = (*current_mtime, current_size)

    output = _run_git(repo_root, "ls-files", "--debug", "--", *scope).decode("utf-8")
    for line in output.splitlines():
        if not line.startswith("  "):
            save_current()
            current_path = Path(line)
            current_mtime = None
            current_size = None
            continue
        stripped = line.strip()
        if stripped.startswith("mtime: "):
            seconds, nanoseconds = stripped.removeprefix("mtime: ").split(":", maxsplit=1)
            current_mtime = (int(seconds), int(nanoseconds))
        elif stripped.startswith("size: "):
            current_size = int(stripped.removeprefix("size: ").split("\t", maxsplit=1)[0])
    save_current()
    return entries


def _worktree_blob_hash(repo_root: Path, path: Path) -> str:
    """Hash one worktree file using Git's configured content filters.

    An index mtime mismatch is only a candidate change: moving a clean clone
    or a stale filesystem monitor can leave the cached stat data behind. Git
    can resolve that candidate exactly by hashing just the affected path,
    avoiding the expensive worktree-wide refresh performed by ``git diff``.
    """

    return _run_git(repo_root, "hash-object", "--", path.as_posix()).decode("ascii").strip()


def dirty_release_critical_paths(repo_root: Path) -> list[tuple[str, Path]]:
    """Return all release-critical paths that differ from ``HEAD``.

    This deliberately avoids ``git status`` and ``git diff`` worktree refreshes.
    On a large macOS worktree those refreshes can exceed a release launcher's
    timeout even when only two files changed. Instead the gate compares the
    immutable HEAD tree, the Git index, and Git-filtered worktree blob hashes
    for only release-critical paths. That catches staged, unstaged, deleted,
    conflicted, and untracked source without trusting a filesystem monitor.
    """

    scope = _release_scope_arguments()
    untracked = _untracked_release_paths(repo_root, scope)
    # This is already a release-artifact mismatch. Short-circuiting keeps the
    # gate fast and deterministic in a badly dirty worktree while still
    # failing closed. A clean candidate proceeds to the tracked-file diff
    # below, which catches modifications that would otherwise be baked in.
    if untracked:
        return [("UNTRACKED", path) for path in sorted(untracked)]

    head_hashes = _head_blob_hashes(repo_root, scope)
    index_hashes, conflicted = _index_blob_hashes(repo_root, scope)
    modified: set[Path] = set(conflicted)
    all_paths = set(head_hashes) | set(index_hashes)

    for path in all_paths:
        if head_hashes.get(path) != index_hashes.get(path):
            modified.add(path)

    index_stat_metadata = _index_stat_metadata(repo_root, scope)
    for path in index_hashes:
        candidate = repo_root / path
        if not candidate.is_file():
            modified.add(path)
            continue
        cached = index_stat_metadata.get(path)
        if cached is None:
            modified.add(path)
            continue
        stat = os.stat(candidate)
        if (stat.st_mtime_ns // 1_000_000_000, stat.st_mtime_ns % 1_000_000_000, stat.st_size) != cached:
            # Cached index stat data is allowed to be stale. Hash only this
            # candidate file before declaring it modified; this preserves
            # exactness without re-scanning every release source file.
            if _worktree_blob_hash(repo_root, path) != index_hashes[path]:
                modified.add(path)

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
