from collegefootballfantasy_api.app.models.player import Player


def test_players_expose_and_sort_by_sheet_board_rank(client, db_session):
    db_session.add_all(
        [
            Player(name="Later Player", position="RB", school="Georgia", sheet_adp=22.0),
            Player(name="Top Player", position="WR", school="Ohio State", sheet_adp=1.0),
            Player(name="Unranked Player", position="QB", school="Florida", sheet_adp=None),
        ]
    )
    db_session.commit()

    response = client.get("/players", params={"sort": "draft_rank", "limit": 10})
    assert response.status_code == 200
    rows = response.json()["data"]

    assert [row["name"] for row in rows[:3]] == ["Top Player", "Later Player", "Unranked Player"]
    assert rows[0]["board_rank"] == 1
    assert rows[0]["sheet_adp"] == 1.0
    assert rows[1]["board_rank"] == 22
