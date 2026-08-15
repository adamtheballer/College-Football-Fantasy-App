import argparse
import importlib.util
from pathlib import Path


def _load_worker_module():
    path = Path(__file__).resolve().parents[2] / "scripts" / "run_notification_worker.py"
    spec = importlib.util.spec_from_file_location("run_notification_worker_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_notification_worker_registers_models_before_its_first_queue_query(monkeypatch):
    worker = _load_worker_module()
    calls: list[str] = []

    class SessionContext:
        def __enter__(self):
            calls.append("session")
            return object()

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(worker, "parse_args", lambda: argparse.Namespace(once=True, limit=1, interval_seconds=1))
    monkeypatch.setattr(worker, "ensure_models_registered", lambda: calls.append("models"))
    monkeypatch.setattr(worker, "configure_logging", lambda *_args: None)
    monkeypatch.setattr(worker, "SessionLocal", SessionContext)
    monkeypatch.setattr(worker, "process_due_notifications_once", lambda *_args, **_kwargs: calls.append("process") or {})
    monkeypatch.setattr(worker, "notification_queue_health", lambda *_args: {})
    monkeypatch.setattr(worker, "record_worker_heartbeat", lambda *_args, **_kwargs: calls.append("heartbeat"))

    worker.main()

    assert calls == ["models", "session", "process", "heartbeat"]
