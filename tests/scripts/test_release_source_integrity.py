"""Regression coverage for the release-artifact provenance gate."""

from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "check_release_source_integrity.py"
SPEC = importlib.util.spec_from_file_location("release_source_integrity", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
release_source_integrity = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release_source_integrity)


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "core.fsmonitor=false", *args], cwd=repo, check=True, capture_output=True)


def make_repository(tmp_path: Path) -> Path:
    repo = tmp_path / "release-source"
    (repo / "api" / "app").mkdir(parents=True)
    (repo / "web" / "client").mkdir(parents=True)
    (repo / "api" / "app" / "main.py").write_text("version = 1\n", encoding="utf-8")
    (repo / "web" / "client" / "App.tsx").write_text("export const app = 1;\n", encoding="utf-8")
    (repo / "README.md").write_text("not release critical\n", encoding="utf-8")
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "release-test@example.test")
    git(repo, "config", "user.name", "Release Test")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "initial source")
    return repo


def test_release_source_integrity_git_calls_disable_filesystem_monitor(monkeypatch, tmp_path: Path):
    calls: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs):
        calls.append(command)
        return SimpleNamespace(stdout=b"ok")

    monkeypatch.setattr(release_source_integrity.subprocess, "run", fake_run)

    assert release_source_integrity._run_git(tmp_path, "rev-parse", "HEAD") == b"ok"
    assert calls == [["git", "-c", "core.fsmonitor=false", "rev-parse", "HEAD"]]


def test_release_source_integrity_ignores_noncritical_changes(tmp_path: Path):
    repo = make_repository(tmp_path)
    (repo / "README.md").write_text("changed documentation only\n", encoding="utf-8")

    assert release_source_integrity.dirty_release_critical_paths(repo) == []


def test_release_source_integrity_detects_untracked_critical_file(tmp_path: Path):
    repo = make_repository(tmp_path)
    path = Path("api/app/new_runtime_code.py")
    (repo / path).write_text("enabled = True\n", encoding="utf-8")

    assert release_source_integrity.dirty_release_critical_paths(repo) == [("UNTRACKED", path)]


def test_release_source_integrity_detects_untracked_frontend_build_configuration(tmp_path: Path):
    repo = make_repository(tmp_path)
    path = Path("web/.npmrc")
    (repo / path).write_text("engine-strict=true\n", encoding="utf-8")

    assert release_source_integrity.dirty_release_critical_paths(repo) == [("UNTRACKED", path)]


def test_release_source_integrity_ignores_stale_index_timestamp_when_content_matches(tmp_path: Path):
    repo = make_repository(tmp_path)
    path = repo / "api" / "app" / "main.py"
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 10_000_000_000))

    assert release_source_integrity.dirty_release_critical_paths(repo) == []


def test_release_source_integrity_detects_staged_and_unstaged_critical_changes(tmp_path: Path):
    repo = make_repository(tmp_path)
    staged_path = Path("api/app/main.py")
    unstaged_path = Path("web/client/App.tsx")
    (repo / staged_path).write_text("version = 2\n", encoding="utf-8")
    git(repo, "add", staged_path.as_posix())
    (repo / unstaged_path).write_text("export const app = 2;\n", encoding="utf-8")

    assert release_source_integrity.dirty_release_critical_paths(repo) == [
        ("MODIFIED", staged_path),
        ("MODIFIED", unstaged_path),
    ]
