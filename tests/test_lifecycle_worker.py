from scripts import run_lifecycle_worker as worker


class _Session:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def _successful_services(monkeypatch):
    for name in (
        "process_expired_draft_picks_once",
        "refresh_open_pick_contests",
        "process_waiver_claims_once",
        "expire_trade_offers_once",
        "process_trade_offers_once",
        "advance_postseason_state",
        "process_security_email_outbox_once",
        "run_due_player_popularity_snapshot",
        "run_due_schedule_sync",
    ):
        monkeypatch.setattr(worker, name, lambda *_args, **_kwargs: {"status": "ok"})


def test_run_once_commits_schedule_sync_state(monkeypatch):
    session = _Session()
    _successful_services(monkeypatch)
    monkeypatch.setattr(worker, "SessionLocal", lambda: session)

    result = worker.run_once()

    assert result["schedule_time_sync"] == {"status": "ok"}
    assert session.commits == 1
    assert session.rollbacks == 0


def test_run_once_rolls_back_when_a_lifecycle_service_fails(monkeypatch):
    session = _Session()
    _successful_services(monkeypatch)
    monkeypatch.setattr(worker, "SessionLocal", lambda: session)
    monkeypatch.setattr(worker, "run_due_schedule_sync", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("provider failed")))

    try:
        worker.run_once()
    except RuntimeError as exc:
        assert str(exc) == "provider failed"
    else:  # pragma: no cover - assertion guard
        raise AssertionError("expected lifecycle exception")

    assert session.commits == 0
    assert session.rollbacks == 1
