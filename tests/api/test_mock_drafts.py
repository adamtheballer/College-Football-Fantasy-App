def test_backend_mock_draft_api_is_not_active(client):
    response = client.post(
        "/mock-drafts",
        json={"title": "Practice Room", "league_size": 4, "rounds": 2},
    )

    assert response.status_code == 404
