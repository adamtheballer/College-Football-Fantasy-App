"""Regression coverage for the retired permanent-rival feature."""


def test_permanent_rivalry_routes_are_not_exposed(client) -> None:
    """Retiring rivalries must make every former API surface unreachable."""
    league_id = 999_999

    assert client.get(f"/leagues/{league_id}/rivalry").status_code == 404
    assert client.post(f"/leagues/{league_id}/rivalry/invites", json={}).status_code == 404
    assert client.post(f"/leagues/{league_id}/rivalry/invites/1/accept").status_code == 404
    assert client.post(f"/leagues/{league_id}/rivalry/invites/1/decline").status_code == 404
    assert client.delete(f"/leagues/{league_id}/rivalry/invites/1").status_code == 404
    assert client.get("/insights/rivalries").status_code == 404
