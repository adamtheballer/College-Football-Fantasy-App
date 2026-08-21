from collegefootballfantasy_api.app.models.postseason import LeaguePostseasonSettings, PostseasonBracket, PostseasonFinalStanding, PostseasonMatchup


def test_postseason_orm_declares_every_migration_created_index_and_constraint():
    matchup_indexes = {index.name for index in PostseasonMatchup.__table__.indexes}
    final_indexes = {index.name for index in PostseasonFinalStanding.__table__.indexes}
    final_constraints = {
        constraint.name
        for constraint in PostseasonFinalStanding.__table__.constraints
        if constraint.name
    }

    assert matchup_indexes >= {
        "ix_postseason_matchups_bracket",
        "ix_postseason_matchups_fantasy_matchup",
    }
    assert final_indexes >= {"ix_postseason_final_standings_bracket"}
    assert final_constraints >= {
        "uq_postseason_final_standing_team",
        "uq_postseason_final_standing_place",
        "uq_postseason_final_standing_bracket_team",
        "uq_postseason_final_standing_bracket_place",
    }


def test_postseason_orm_preserves_calendar_provenance_snapshots():
    settings_columns = set(LeaguePostseasonSettings.__table__.columns.keys())
    bracket_columns = set(PostseasonBracket.__table__.columns.keys())

    expected = {
        "calendar_policy_version",
        "calendar_source_identity",
        "calendar_source_revision",
        "calendar_source_sha256",
        "calendar_source_format_version",
    }
    assert expected <= settings_columns
    assert expected | {"championship_week"} <= bracket_columns
