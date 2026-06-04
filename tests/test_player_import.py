import pytest

from api.app.models.player import Player
from api.app.services.player_import import import_players_from_csv_rows, read_csv_rows_from_text


def import_csv(db_session, text: str):
    rows, headers = read_csv_rows_from_text(text)
    return import_players_from_csv_rows(db_session, rows, headers, source="test_sheet")


def test_import_players_creates_players(client, db_session):
    result = import_csv(
        db_session,
        "Player,Pos,College,Rank,FPTS\n"
        "Arch Manning,QB,Texas,1,300\n"
        "Jeremiyah Love,RB,Notre Dame,2,280\n",
    )
    assert result.created == 2
    assert db_session.query(Player).count() == 2
    player = db_session.query(Player).filter(Player.name == "Arch Manning").one()
    assert player.position == "QB"
    assert player.school == "Texas"
    assert player.sheet_adp == 1
    assert player.sheet_projected_season_points == 300


def test_import_players_updates_existing_players(client, db_session):
    import_csv(db_session, "name,position,school,rank,projection\nQB One,QB,Texas,9,100\n")
    result = import_csv(db_session, "player,pos,team,rank,projection\nQB One,QB,Texas,3,140\n")
    assert result.created == 0
    assert result.updated == 1
    assert db_session.query(Player).count() == 1
    player = db_session.query(Player).one()
    assert player.sheet_adp == 3
    assert player.sheet_projected_season_points == 140


def test_import_players_updates_existing_canonical_player_with_external_id(client, db_session):
    db_session.add(Player(external_id="sportsdata-1", name="Aaron Philo", position="QB", school="Florida"))
    db_session.commit()

    result = import_csv(db_session, "player,pos,team,rank,projection\nAaron Philo,QB,FLORIDA,151,274.92\n")

    assert result.created == 0
    assert result.updated == 1
    assert db_session.query(Player).count() == 1
    player = db_session.query(Player).one()
    assert player.external_id == "sportsdata-1"
    assert player.sheet_adp == 151
    assert player.sheet_projected_season_points == 274.92


def test_import_players_skips_missing_required_fields(client, db_session):
    result = import_csv(db_session, "name,position,school\nMissing School,QB,\nMissing Pos,,Texas\n")
    assert result.created == 0
    assert result.skipped == 2
    assert db_session.query(Player).count() == 0


def test_import_players_is_idempotent(client, db_session):
    csv_text = "name,position,school,rank\nSame QB,QB,Texas,1\n"
    first = import_csv(db_session, csv_text)
    second = import_csv(db_session, csv_text)
    assert first.created == 1
    assert second.updated == 1
    assert db_session.query(Player).count() == 1


def test_import_players_handles_column_aliases(client, db_session):
    result = import_csv(
        db_session,
        "full_name,pos,university,big_board_rank,avg_draft_position,proj_points,headshot\n"
        "Alias WR,wr,Ohio State,12,10.5,220,http://image.test/wr.png\n",
    )
    assert result.created == 1
    player = db_session.query(Player).one()
    assert player.name == "Alias WR"
    assert player.position == "WR"
    assert player.school == "Ohio State"
    assert player.sheet_adp == 10.5
    assert player.image_url == "http://image.test/wr.png"


def test_import_players_normalizes_rank_suffixed_positions(client, db_session):
    result = import_csv(db_session, "name,position,school,rank\nRanked QB,QB1,Texas,1\n")
    assert result.created == 1
    assert db_session.query(Player).one().position == "QB"


def test_import_players_fails_when_required_columns_missing(client, db_session):
    rows, headers = read_csv_rows_from_text("name,school\nOnly Name,Texas\n")
    with pytest.raises(ValueError, match="missing required columns"):
        import_players_from_csv_rows(db_session, rows, headers)
