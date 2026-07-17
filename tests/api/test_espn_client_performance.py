from collegefootballfantasy_api.app.integrations import espn as espn_integration
from collegefootballfantasy_api.app.integrations.espn import ESPNClient


class _FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {}


class _FakeHttpClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict | None]] = []
        self.closed = False

    def get(self, url: str, params: dict | None = None) -> _FakeResponse:
        self.calls.append((url, params))
        return _FakeResponse()

    def close(self) -> None:
        self.closed = True


def test_espn_client_reuses_one_http_connection_pool(monkeypatch):
    created_clients: list[_FakeHttpClient] = []

    def create_client(**_kwargs):
        client = _FakeHttpClient()
        created_clients.append(client)
        return client

    monkeypatch.setattr(espn_integration.httpx, "Client", create_client)
    client = ESPNClient()

    client.get_scoreboard_events(2026, 1)
    client.get_summary("event-1")
    client.close()

    assert len(created_clients) == 1
    assert len(created_clients[0].calls) == 2
    assert created_clients[0].closed is True


def test_weekly_boxscore_summary_fetches_preserve_event_order(monkeypatch):
    client = ESPNClient(summary_concurrency=2, http_client=_FakeHttpClient())
    monkeypatch.setattr(client, "get_scoreboard_events", lambda **_kwargs: [{"id": "one"}, {"id": "two"}])
    monkeypatch.setattr(client, "get_summary", lambda event_id: {"summary": event_id})

    summaries = client.get_weekly_boxscore_summaries(2026, 1)

    assert summaries == [
        {"summary": "one", "event_id": "one"},
        {"summary": "two", "event_id": "two"},
    ]
