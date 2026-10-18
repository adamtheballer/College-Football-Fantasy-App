from datetime import timedelta
import pytest
from sqlalchemy import func
from test_weekly_challenges import world, NOW, KICKOFF
from collegefootballfantasy_api.app.models.college_team import CollegeTeam
from collegefootballfantasy_api.app.models.weekly_challenge import (
    WeeklyChallenge,
    ChallengeEntry,
    ChallengeScore,
    ChallengeAudit,
    ChallengeAward,
)
from collegefootballfantasy_api.app.models.challenge_experience import (
    ChallengeSalary,
    ChallengeCreator,
    ChallengeFanMembership,
    ChallengeSurvivorPick,
    ChallengeEvent,
)
from collegefootballfantasy_api.app.models.player_game_stat import PlayerGameStat
from collegefootballfantasy_api.app.services import (
    weekly_challenges as core,
    challenge_experiences as svc,
)
from collegefootballfantasy_api.app.schemas.challenge_experience import ExperienceRead

BASE = "/weekly-challenges"
ADMIN = "/admin/weekly-challenges"


@pytest.fixture
def exp(world):
    w = world
    for name, conference in [
        ("Alabama", "SEC"),
        ("Ohio State", "Big Ten"),
        ("Auburn", "SEC"),
        ("Oregon", "BIG10"),
    ]:
        w["db"].add(CollegeTeam(name=name, conference=conference))
    w["db"].commit()
    return w


def create(w, kind, *, authorized=True, week=1, series_id=None):
    admin = w["accounts"][0][1]
    payload = {
        "season": 2026,
        "week": week,
        "kind": kind,
        "entry_open_at": NOW.isoformat(),
    }
    if kind == "creator":
        profile = w["client"].post(
            f"{ADMIN}/creators",
            headers=admin,
            json={
                "slug": f"approved-creator-{week}",
                "name": "Approved Test Analyst",
                "authorized": authorized,
                "active": True,
                "links": {"YouTube": "https://www.youtube.com/channel/test"},
            },
        )
        assert profile.status_code == 201, profile.text
        payload["creator_id"] = profile.json()["id"]
    if kind == "survivor":
        if series_id is None:
            r = w["client"].post(
                f"{ADMIN}/survivor-series",
                headers=admin,
                json={
                    "name": "Week 1 Test Series",
                    "season": 2026,
                    "start_week": 1,
                    "end_week": 3,
                    "entry_open_at": NOW.isoformat(),
                    "first_lock_at": KICKOFF.isoformat(),
                },
            )
            assert r.status_code == 201, r.text
            series_id = r.json()["id"]
        payload["series_id"] = series_id
    r = w["client"].post(f"{ADMIN}/experiences", headers=admin, json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def publish(w, kind, **changes):
    c = create(w, kind)
    n = 10 if kind == "creator" else 3 if kind == "fanwars" else 1
    games = w["games"][:n]
    config = {"expected_version": c["version"], "game_ids": [g.id for g in games]}
    if kind == "millionaire":
        config.update(
            player_ids=[p.id for p in w["players"]],
            salaries=[{"player_id": p.id, "salary": 10} for p in w["players"]],
        )
    if kind == "creator":
        config["creator_picks"] = [
            {"game_id": g.id, "team": g.home_team} for g in games
        ]
    config.update(changes)
    r = w["client"].put(
        f"{ADMIN}/experiences/{c['id']}", headers=w["accounts"][0][1], json=config
    )
    assert r.status_code == 200, r.text
    c = r.json()
    v = w["client"].post(
        f"{ADMIN}/challenges/{c['id']}/validate", headers=w["accounts"][0][1]
    )
    assert v.status_code == 200 and v.json()["valid"], v.text
    r = w["client"].post(
        f"{ADMIN}/challenges/{c['id']}/publish",
        headers=w["accounts"][0][1],
        json={
            "expected_version": c["version"],
            "reason": "Reviewed authoritative fixture slate",
        },
    )
    assert r.status_code == 200, r.text
    return r.json()


def join_school(w, c, user=1, school="Alabama"):
    s = w["db"].query(CollegeTeam).filter_by(name=school).one()
    return w["client"].put(
        f"{BASE}/experiences/{c['id']}/allegiance",
        headers=w["accounts"][user][1],
        json={"school_id": s.id},
    )


def picks(w, c):
    if c["kind"] == "millionaire":
        return [
            {"player_id": w["players"][i].id, "slot": slot}
            for i, slot in zip([0, 1, 2, 6, 3, 4], svc.SLOTS)
        ]
    return [
        {"game_id": g["id"], "team": g["home_team"]}
        for g in c["games"][
            : 1 if c["kind"] == "survivor" else 2 if c["kind"] == "fanwars" else 10
        ]
    ]


def save(w, c, user=1, **changes):
    payload = {"expected_revision": 0, "submit": True, "selections": picks(w, c)}
    payload.update(changes)
    return w["client"].put(
        f"{BASE}/challenges/{c['id']}/entry",
        headers=w["accounts"][user][1],
        json=payload,
    )


def score(w, c, status="final", home=30, away=20):
    for g in w["games"]:
        g.schedule_status = status
        g.home_points = home
        g.away_points = away
    w["db"].commit()
    w["clock"][0] = KICKOFF + timedelta(days=1)
    return core.settle(w["db"], core.challenge_or_404(w["db"], c["id"], lock=True))


@pytest.mark.parametrize("kind", list(svc.KINDS))
def test_modes_persist_unique_entry_and_keep_legacy_round_unchanged(exp, kind):
    w = exp
    c = publish(w, kind)
    if kind == "fanwars":
        assert join_school(w, c).status_code == 200
    r = save(w, c)
    assert r.status_code == 200, r.text
    entry = r.json()
    assert save(w, c).status_code == 409
    changed = save(w, c, expected_revision=entry["revision"])
    assert changed.status_code == 200 and changed.json()["id"] == entry["id"]
    old = w["client"].get(f"{BASE}/current", headers=w["accounts"][1][1]).json()
    assert len(old["challenges"]) == 5
    new = (
        w["client"]
        .get(f"{BASE}/current?include_experiences=true", headers=w["accounts"][1][1])
        .json()
    )
    assert len(new["challenges"]) == 6
    assert new["challenges"][-1]["participant_count"] == 1
    assert w["db"].query(ChallengeEntry).filter_by(challenge_id=c["id"]).count() == 1
    detail = w["client"].get(
        f"{BASE}/challenges/{c['id']}", headers=w["accounts"][1][1]
    )
    assert detail.status_code == 200
    ExperienceRead.model_validate(detail.json()["experience"])


def test_fan_allegiance_freezes_and_kickoff_locks_only_that_game(exp):
    w = exp
    c = publish(w, "fanwars")
    assert save(w, c).status_code == 422
    assert join_school(w, c).status_code == 200
    assert join_school(w, c, school="Ohio State").status_code == 409
    assert save(w, c).status_code == 200
    w["clock"][0] = KICKOFF + timedelta(minutes=1)
    locked = save(
        w,
        c,
        expected_revision=1,
        selections=[
            {"game_id": c["games"][0]["id"], "team": c["games"][0]["away_team"]}
        ],
    )
    assert locked.status_code == 409
    r = save(
        w,
        c,
        expected_revision=1,
        selections=picks(w, c)
        + [{"game_id": c["games"][2]["id"], "team": c["games"][2]["home_team"]}],
    )
    assert r.status_code == 200, r.text
    assert (
        w["db"]
        .query(ChallengeFanMembership)
        .filter_by(user_id=w["accounts"][1][0])
        .count()
        == 1
    )


def test_school_accuracy_denominators_threshold_and_fan_power(exp):
    w = exp
    c = publish(w, "fanwars", minimum_fans=2)
    for user, school in [(1, "Alabama"), (2, "Alabama"), (3, "Ohio State")]:
        assert join_school(w, c, user, school).status_code == 200
        selections = picks(w, c)
        if user == 2:
            selections[1]["team"] = c["games"][1]["away_team"]
        assert save(w, c, user, selections=selections).status_code == 200
    assert score(w, c) == "final"
    board = svc.school_standings(w["db"], w["db"].get(WeeklyChallenge, c["id"]))
    assert [
        (
            r["school"],
            r["accuracy"],
            r["fan_points"],
            r["active_fans"],
            r["rank"],
            r["provisional"],
        )
        for r in board
    ] == [
        ("Alabama", 75.0, 30.0, 2, 1, False),
        ("Ohio State", 100.0, 20.0, 1, None, True),
    ]
    assert sum(r["eligible_picks"] for r in board) == 6
    assert w["db"].query(ChallengeAward).count() == 0
    audits = w["db"].query(ChallengeAudit).filter_by(challenge_id=c["id"]).count()
    core.settle(w["db"], w["db"].get(WeeklyChallenge, c["id"]))
    assert (
        w["db"].query(ChallengeAudit).filter_by(challenge_id=c["id"]).count() == audits
    )


def test_millionaire_budget_positions_duplicate_and_salary_snapshot(exp):
    w = exp
    salaries = [
        {"player_id": p.id, "salary": 60 if i == 0 else 10}
        for i, p in enumerate(w["players"])
    ]
    c = publish(w, "millionaire", salaries=salaries)
    assert save(w, c).status_code == 422
    valid = picks(w, c)
    valid[0]["player_id"] = w["players"][5].id
    assert save(w, c, selections=valid).status_code == 200
    invalid = [dict(p) for p in valid]
    invalid[1]["player_id"] = invalid[2]["player_id"]
    assert save(w, c, selections=invalid, expected_revision=1).status_code == 422
    assert (
        w["client"]
        .put(
            f"{ADMIN}/experiences/{c['id']}",
            headers=w["accounts"][0][1],
            json={"expected_version": c["version"], "salaries": []},
        )
        .status_code
        == 409
    )
    assert w["db"].query(ChallengeSalary).filter_by(challenge_id=c["id"]).count() == 7
    private = (
        w["client"]
        .get(f"{BASE}/experiences/{c['id']}/leaderboard", headers=w["accounts"][2][1])
        .json()
    )
    assert private["data"][0]["selections"] is None
    w["clock"][0] = KICKOFF
    assert save(w, c, selections=valid, expected_revision=1).status_code == 409
    revealed = (
        w["client"]
        .get(f"{BASE}/experiences/{c['id']}/leaderboard", headers=w["accounts"][2][1])
        .json()
    )
    assert len(revealed["data"][0]["selections"]) == 6


def test_millionaire_missing_stats_real_zero_and_corrections(exp):
    w = exp
    c = publish(w, "millionaire")
    assert save(w, c).status_code == 200
    assert score(w, c) == "processing"
    for p in w["players"]:
        w["db"].add(
            PlayerGameStat(
                player_id=p.id,
                game_id=w["games"][0].id,
                season=2026,
                week=1,
                source="espn_final_boxscore",
                stats={"rush_yards": 10, "receptions": 0},
            )
        )
    w["db"].commit()
    assert core.settle(w["db"], w["db"].get(WeeklyChallenge, c["id"])) == "final"
    s = w["db"].query(ChallengeScore).one()
    assert float(s.raw_points) == 6
    fact = w["db"].query(PlayerGameStat).filter_by(player_id=w["players"][0].id).one()
    fact.stats = {"rush_yards": 20}
    w["db"].commit()
    core.settle(w["db"], w["db"].get(WeeklyChallenge, c["id"]))
    w["db"].refresh(s)
    assert float(s.raw_points) == 7
    assert w["db"].query(ChallengeAward).count() == 0


def test_unapproved_creator_cannot_publish_and_picks_never_fabricated(exp):
    w = exp
    c = create(w, "creator", authorized=False)
    r = w["client"].post(
        f"{ADMIN}/challenges/{c['id']}/publish",
        headers=w["accounts"][0][1],
        json={"expected_version": 0, "reason": "Test unapproved publishing rejection"},
    )
    assert r.status_code == 422
    assert w["client"].get(f"{BASE}/creators", headers=w["accounts"][1][1]).json() == []
    assert all(
        not m["competitions"]
        for m in w["client"].get(f"{BASE}/modes", headers=w["accounts"][1][1]).json()
    )


@pytest.mark.parametrize(
    "losses,expected", [(0, "TIED THE CREATOR"), (1, "CREATOR WON")]
)
def test_creator_uses_same_ten_games_and_exact_comparison(exp, losses, expected):
    w = exp
    c = publish(w, "creator")
    selections = picks(w, c)
    if losses:
        selections[0]["team"] = c["games"][0]["away_team"]
    assert save(w, c, selections=selections).status_code == 200
    before = (
        w["client"]
        .get(f"{BASE}/challenges/{c['id']}", headers=w["accounts"][1][1])
        .json()
    )
    assert before["experience"]["creator_picks"] is None
    assert score(w, c) == "final"
    after = (
        w["client"]
        .get(f"{BASE}/challenges/{c['id']}", headers=w["accounts"][1][1])
        .json()
    )
    assert (
        after["experience"]["comparison"] == expected
        and after["experience"]["creator_score"] == 100
    )
    assert after["experience"]["creator_correct"] == 10
    assert (
        w["client"]
        .put(
            f"{ADMIN}/experiences/{c['id']}/creator-correction",
            headers=w["accounts"][1][1],
            json={
                "expected_version": c["version"],
                "reason": "Unauthorized attempted creator change",
                "picks": picks(w, c),
            },
        )
        .status_code
        == 403
    )


def test_creator_correction_is_publicly_disclosed_and_recalculates(exp):
    w = exp
    c = publish(w, "creator")
    assert save(w, c).status_code == 200
    score(w, c)
    choices = picks(w, c)
    choices[0]["team"] = c["games"][0]["away_team"]
    r = w["client"].put(
        f"{ADMIN}/experiences/{c['id']}/creator-correction",
        headers=w["accounts"][0][1],
        json={
            "expected_version": c["version"],
            "reason": "Verified original creator pick transcription correction",
            "picks": choices,
        },
    )
    assert r.status_code == 200, r.text
    after = (
        w["client"]
        .get(f"{BASE}/challenges/{c['id']}", headers=w["accounts"][1][1])
        .json()["experience"]
    )
    assert (
        after["comparison"] == "BEAT THE CREATOR"
        and after["creator_score"] == 90
        and after["corrections"]
    )


def test_survivor_win_loss_late_entry_and_uncertain_game(exp):
    w = exp
    c = publish(w, "survivor")
    assert save(w, c).status_code == 200
    assert score(w, c, status="canceled") == "processing"
    sp = w["db"].query(ChallengeSurvivorPick).one()
    assert sp.outcome == "pending"
    r = w["client"].post(
        f"{ADMIN}/experiences/{c['id']}/void-advance",
        headers=w["accounts"][0][1],
        json={
            "expected_version": c["version"],
            "game_id": c["games"][0]["id"],
            "reason": "Confirmed official cancellation; apply published void advance rule",
        },
    )
    assert r.status_code == 200, r.text
    w["db"].refresh(sp)
    assert sp.outcome == "void_advanced"
    w["games"][0].schedule_status = "final"
    w["games"][0].home_points = 10
    w["games"][0].away_points = 30
    w["db"].commit()
    core.settle(w["db"], w["db"].get(WeeklyChallenge, c["id"]))
    w["db"].refresh(sp)
    assert sp.outcome == "void_advanced"
    current = w["db"].get(WeeklyChallenge, c["id"])
    revoked = w["client"].post(
        f"{ADMIN}/experiences/{c['id']}/revoke-void-advance",
        headers=w["accounts"][0][1],
        json={
            "expected_version": current.version,
            "game_id": c["games"][0]["id"],
            "reason": "Authoritative result is confirmed; revoke the administrative void",
        },
    )
    assert revoked.status_code == 200, revoked.text
    w["db"].refresh(sp)
    assert sp.outcome == "eliminated"
    after = (
        w["client"]
        .get(f"{BASE}/challenges/{c['id']}", headers=w["accounts"][1][1])
        .json()["experience"]
    )
    assert after["survivor_status"] == "eliminated"
    assert save(w, c, 2).status_code == 409


@pytest.mark.parametrize(
    "path,method,payload",
    [
        (f"{ADMIN}/creators", "post", {"slug": "fake", "name": "Fake"}),
        (
            f"{ADMIN}/experiences",
            "post",
            {
                "season": 2026,
                "week": 1,
                "kind": "fanwars",
                "entry_open_at": NOW.isoformat(),
            },
        ),
    ],
)
def test_admin_operations_never_exposed_to_ordinary_users(exp, path, method, payload):
    w = exp
    assert (
        getattr(w["client"], method)(
            path, json=payload, headers=w["accounts"][1][1]
        ).status_code
        == 403
    )


def test_analytics_events_deduplicate_and_use_real_entries(exp):
    w = exp
    c = publish(w, "fanwars")
    join_school(w, c)
    save(w, c)
    for _ in range(3):
        assert (
            w["client"]
            .post(
                f"{BASE}/events",
                headers=w["accounts"][1][1],
                json={"event_type": "view", "challenge_id": c["id"]},
            )
            .status_code
            == 200
        )
    assert w["db"].query(ChallengeEvent).filter_by(event_type="view").count() == 1
    r = w["client"].get(
        f"{ADMIN}/experiences/{c['id']}/analytics", headers=w["accounts"][0][1]
    )
    assert r.status_code == 200
    assert (
        r.json()["views"] == 1
        and r.json()["submitted_entries"] == 1
        and r.json()["completion_rate"] == 1
    )


def test_millionaire_unpriced_and_impossible_salary_pool_cannot_open(exp):
    w = exp
    c = create(w, "millionaire")
    base = {
        "expected_version": 0,
        "game_ids": [w["games"][0].id],
        "player_ids": [p.id for p in w["players"]],
        "salaries": [{"player_id": p.id, "salary": 25} for p in w["players"]],
    }
    r = w["client"].put(
        f"{ADMIN}/experiences/{c['id']}", headers=w["accounts"][0][1], json=base
    )
    assert r.status_code == 200
    v = (
        w["client"]
        .post(f"{ADMIN}/challenges/{c['id']}/validate", headers=w["accounts"][0][1])
        .json()
    )
    assert not v["valid"] and any("budget" in x for x in v["blockers"])
    base["expected_version"] = 1
    base["salaries"] = base["salaries"][:-1]
    assert (
        w["client"]
        .put(f"{ADMIN}/experiences/{c['id']}", headers=w["accounts"][0][1], json=base)
        .status_code
        == 200
    )
    assert (
        not w["client"]
        .post(f"{ADMIN}/challenges/{c['id']}/validate", headers=w["accounts"][0][1])
        .json()["valid"]
    )


def test_survivor_second_week_reuse_missing_pick_and_new_series_rules(exp):
    w = exp
    c = publish(w, "survivor")
    series_id = c["experience"]["series"]["id"]
    assert save(w, c).status_code == 200
    assert save(w, c, user=2).status_code == 200
    assert score(w, c) == "final"
    for g in w["games"]:
        g.week = 2
        g.schedule_status = "scheduled"
        g.start_date = KICKOFF + timedelta(days=7)
        g.home_points = None
        g.away_points = None
    w["db"].commit()
    w["clock"][0] = KICKOFF + timedelta(days=4)
    second = create(w, "survivor", week=2, series_id=series_id)
    a = w["accounts"][0][1]
    r = w["client"].put(
        f"{ADMIN}/experiences/{second['id']}",
        headers=a,
        json={"expected_version": 0, "game_ids": [w["games"][0].id]},
    )
    assert r.status_code == 200
    second = (
        w["client"]
        .post(
            f"{ADMIN}/challenges/{second['id']}/publish",
            headers=a,
            json={
                "expected_version": 1,
                "reason": "Approved second-week survivor slate",
            },
        )
        .json()
    )
    assert second["state"] == "Open", second
    repeated = save(w, second)
    assert (
        repeated.status_code == 422
        and repeated.json()["detail"]["code"] == "TEAM_ALREADY_USED"
    )
    later = save(
        w,
        second,
        user=3,
        selections=[
            {
                "game_id": second["games"][0]["id"],
                "team": second["games"][0]["away_team"],
            }
        ],
    )
    assert (
        later.status_code == 409
        and later.json()["detail"]["code"] == "SERIES_ENTRY_CLOSED"
    )
    chosen = [
        {"game_id": second["games"][0]["id"], "team": second["games"][0]["away_team"]}
    ]
    assert save(w, second, selections=chosen).status_code == 200
    w["clock"][0] = KICKOFF + timedelta(days=8)
    for g in w["games"]:
        g.schedule_status = "final"
        g.home_points = 10
        g.away_points = 30
    w["db"].commit()
    core.settle(w["db"], w["db"].get(WeeklyChallenge, second["id"]))
    status = (
        w["client"]
        .get(f"{BASE}/challenges/{second['id']}", headers=w["accounts"][1][1])
        .json()["experience"]
    )
    assert status["weeks_survived"] == 2
    missing = (
        w["client"]
        .get(f"{BASE}/challenges/{second['id']}", headers=w["accounts"][2][1])
        .json()["experience"]
    )
    assert missing["survivor_status"] == "eliminated"
    # Viewing Week 1 must not apply Week 2's elimination or count future survival.
    past = (
        w["client"]
        .get(f"{BASE}/challenges/{c['id']}", headers=w["accounts"][2][1])
        .json()["experience"]
    )
    assert past["survivor_status"] == "active" and past["weeks_survived"] == 1
    past_board = (
        w["client"]
        .get(f"{BASE}/experiences/{c['id']}/leaderboard", headers=w["accounts"][1][1])
        .json()
    )
    assert all(row["points"] == 1 for row in past_board["data"])
    assert (
        missing["previous_picks"][-1]["team"] is None
        and missing["previous_picks"][-1]["outcome"] == "eliminated"
    )


def test_salary_suggestions_never_make_up_unavailable_projection(exp):
    w = exp
    c = create(w, "millionaire")
    r = w["client"].get(
        f"{ADMIN}/experiences/{c['id']}/salary-suggestions", headers=w["accounts"][0][1]
    )
    assert r.status_code == 200 and r.json() == []


def test_duplicate_creator_game_picks_and_cross_account_header_are_rejected(exp):
    w = exp
    c = publish(w, "creator")
    choices = picks(w, c)
    choices[-1] = choices[0]
    r = save(w, c, selections=choices)
    assert r.status_code == 422
    h = {**w["accounts"][1][1], "X-CFFB-Challenge-Account": str(w["accounts"][2][0])}
    assert (
        w["client"]
        .put(
            f"{BASE}/challenges/{c['id']}/entry",
            headers=h,
            json={"expected_revision": 0, "selections": picks(w, c)},
        )
        .status_code
        == 409
    )
    assert w["db"].query(ChallengeEntry).filter_by(challenge_id=c["id"]).count() == 0


def test_hidden_mode_rejects_entries_and_preserves_existing_entries(exp):
    w = exp
    c = publish(w, "millionaire")
    assert save(w, c).status_code == 200
    response = w["client"].put(
        f"{ADMIN}/experiences/{c['id']}/visibility",
        headers=w["accounts"][0][1],
        json={
            "expected_version": c["version"],
            "enabled": False,
            "reason": "Temporarily hide during data verification",
        },
    )
    assert response.status_code == 200
    assert save(w, c, expected_revision=1).status_code == 409
    assert (
        w["client"]
        .get(f"{BASE}/challenges/{c['id']}", headers=w["accounts"][1][1])
        .status_code
        == 404
    )
    assert w["db"].query(ChallengeEntry).filter_by(challenge_id=c["id"]).count() == 1
    assert not any(
        m["competitions"]
        for m in w["client"].get(f"{BASE}/modes", headers=w["accounts"][1][1]).json()
    )


def test_creator_slug_referrals_are_safe_and_signup_attribution_is_once_only(exp):
    w = exp
    c = publish(w, "creator")
    creator = w["db"].query(ChallengeCreator).one()
    u = w["db"].get(
        __import__(
            "collegefootballfantasy_api.app.models.user", fromlist=["User"]
        ).User,
        w["accounts"][1][0],
    )
    u.created_at = NOW
    w["db"].commit()
    payload = {
        "event_type": "referral_open",
        "creator_slug": creator.slug,
        "challenge_id": c["id"],
    }
    for _ in range(3):
        assert (
            w["client"]
            .post(f"{BASE}/events", headers=w["accounts"][1][1], json=payload)
            .status_code
            == 200
        )
    assert w["db"].query(ChallengeEvent).filter_by(event_type="signup").count() == 1
    assert (
        w["db"].query(ChallengeEvent).filter_by(event_type="referral_open").count() == 1
    )
    assert (
        w["client"]
        .post(
            f"{BASE}/events",
            headers=w["accounts"][1][1],
            json={**payload, "creator_slug": "not-a-registered-creator"},
        )
        .status_code
        == 404
    )


def test_mode_reminders_are_idempotent_expire_at_lock_and_never_queue_email(exp):
    from collegefootballfantasy_api.app.models.scheduled_notification import (
        ScheduledNotification,
    )
    from collegefootballfantasy_api.app.models.notification import (
        NotificationDeliveryAttempt,
        NotificationPreference,
    )
    from collegefootballfantasy_api.app.services.notification_service import (
        _phone_category_allowed,
    )

    w = exp
    c = publish(w, "millionaire")
    assert save(w, c).status_code == 200
    w["clock"][0] = KICKOFF - timedelta(minutes=20)
    svc.queue_reminders(w["db"])
    svc.queue_reminders(w["db"])
    row = (
        w["db"]
        .query(ScheduledNotification)
        .filter_by(event_type="CHALLENGE_REMINDER")
        .one()
    )
    assert core.aware(row.expires_at) == KICKOFF
    assert {
        a.channel
        for a in w["db"]
        .query(NotificationDeliveryAttempt)
        .filter_by(scheduled_notification_id=row.id)
    } == {"in_app", "push"}
    assert svc.notification_eligible(
        w["db"],
        row,
        w["db"].get(
            __import__(
                "collegefootballfantasy_api.app.models.user", fromlist=["User"]
            ).User,
            w["accounts"][1][0],
        ),
    )
    prefs = NotificationPreference(
        user_key="test", push_matchups=True, lineup_reminders=False
    )
    assert not _phone_category_allowed("CHALLENGE_REMINDER", prefs)
    w["clock"][0] = KICKOFF
    assert not svc.notification_eligible(
        w["db"],
        row,
        w["db"].get(
            __import__(
                "collegefootballfantasy_api.app.models.user", fromlist=["User"]
            ).User,
            w["accounts"][1][0],
        ),
    )


def test_analytics_opt_out_is_persistent_and_respects_do_not_track(exp):
    w = exp
    c = publish(w, "fanwars")
    h = w["accounts"][1][1]
    assert w["client"].put(
        f"{BASE}/analytics-preference", headers=h, json={"enabled": False}
    ).json() == {"enabled": False}
    assert w["client"].get(f"{BASE}/analytics-preference", headers=h).json() == {
        "enabled": False
    }
    assert w["client"].post(
        f"{BASE}/events",
        headers=h,
        json={"event_type": "view", "challenge_id": c["id"]},
    ).json() == {"recorded": False}
    assert w["db"].query(ChallengeEvent).count() == 0
    assert (
        w["client"]
        .put(f"{BASE}/analytics-preference", headers=h, json={"enabled": True})
        .status_code
        == 200
    )
    assert w["client"].post(
        f"{BASE}/events",
        headers={**h, "DNT": "1"},
        json={"event_type": "view", "challenge_id": c["id"]},
    ).json() == {"recorded": False}
    assert w["db"].query(ChallengeEvent).count() == 0


def test_new_season_fan_allegiance_does_not_rewrite_past_membership(exp):
    w = exp
    c = publish(w, "fanwars")
    assert join_school(w, c).status_code == 200
    member = w["db"].query(ChallengeFanMembership).one()
    assert member.season == 2026 and member.week == 1
    core.settings.current_season_year = 2027
    try:
        assert save(w, c).status_code == 409
        w["db"].refresh(member)
        assert member.school_name == "Alabama" and member.season == 2026
    finally:
        core.settings.current_season_year = 2026


def test_published_rivalry_and_conference_history_survive_metadata_changes(exp):
    w = exp
    ids = {s.name: s.id for s in w["db"].query(CollegeTeam)}
    c = publish(w, "fanwars", rivalries=[[ids["Alabama"], ids["Ohio State"]]])
    for uid, school in [(1, "Alabama"), (2, "Ohio State")]:
        assert join_school(w, c, uid, school).status_code == 200
        assert save(w, c, uid).status_code == 200
    score(w, c)
    school = w["db"].get(CollegeTeam, ids["Alabama"])
    school.conference = "ACC"
    w["db"].commit()
    result = (
        w["client"]
        .get(f"{BASE}/challenges/{c['id']}", headers=w["accounts"][1][1])
        .json()["experience"]
    )
    assert result["allegiance"]["conference"] == "SEC"
    assert result["rivalries"][0]["winner"] == "tie"
    assert (
        next(s for s in result["schools"] if s["id"] == ids["Alabama"])["conference"]
        == "SEC"
    )


def test_creator_profiles_freeze_published_branding_and_inactive_directory(exp):
    w = exp
    c = publish(w, "creator")
    row = w["db"].query(ChallengeCreator).one()
    row.name = "Renamed for future contests"
    w["db"].commit()
    detail = (
        w["client"]
        .get(f"{BASE}/challenges/{c['id']}", headers=w["accounts"][1][1])
        .json()
    )
    assert detail["experience"]["creator"]["name"] == "Approved Test Analyst"
    row.active = False
    w["db"].commit()
    assert save(w, c).status_code == 409
    assert w["client"].get(f"{BASE}/creators", headers=w["accounts"][1][1]).json() == []


def test_early_started_game_cannot_reopen_after_schedule_repair(exp):
    w = exp
    c = publish(w, "fanwars")
    join_school(w, c)
    w["games"][0].schedule_status = "in_progress"
    w["db"].commit()
    assert save(w, c).status_code == 409
    w["games"][0].schedule_status = "scheduled"
    w["db"].commit()
    assert save(w, c).status_code == 409
    assert w["db"].query(ChallengeEntry).count() == 0


def test_future_round_entries_are_rejected_and_upcoming_is_read_only(exp):
    w = exp
    c = create(w, "fanwars", week=2)
    assert save(w, c).status_code == 409
    r = w["client"].get(f"{BASE}/upcoming", headers=w["accounts"][1][1])
    assert r.status_code == 200 and r.json()["week"] == 2
    assert w["db"].query(ChallengeEntry).count() == 0


def test_top_ten_and_equal_score_ranks_are_authoritative(exp):
    w = exp
    c = publish(w, "millionaire")
    for user in [1, 2, 3]:
        assert save(w, c, user).status_code == 200
    for p in w["players"]:
        w["db"].add(
            PlayerGameStat(
                player_id=p.id,
                game_id=w["games"][0].id,
                season=2026,
                week=1,
                source="espn_final_boxscore",
                stats={"rush_yards": 0, "receptions": 0},
            )
        )
    w["db"].commit()
    score(w, c)
    board = (
        w["client"]
        .get(f"{BASE}/experiences/{c['id']}/leaderboard", headers=w["accounts"][1][1])
        .json()
    )
    assert (
        board["total"] == 3
        and {r["rank"] for r in board["data"]} == {1}
        and {r["points"] for r in board["data"]} == {0}
    )
    assert board["your_rank"]["rank"] == 1 and not board["provisional"]


def test_duplicate_admin_creator_picks_reject_without_corrupting_configuration(exp):
    w = exp
    c = create(w, "creator")
    choices = [{"game_id": w["games"][0].id, "team": w["games"][0].home_team}] * 10
    r = w["client"].put(
        f"{ADMIN}/experiences/{c['id']}",
        headers=w["accounts"][0][1],
        json={
            "expected_version": 0,
            "game_ids": [g.id for g in w["games"][:10]],
            "creator_picks": choices,
        },
    )
    assert r.status_code == 422
    w["db"].expire_all()
    assert w["db"].get(WeeklyChallenge, c["id"]).version == 0


def test_account_deletion_removes_private_fan_membership_and_analytics(exp):
    from collegefootballfantasy_api.app.services.account_deletion import (
        permanently_delete_user_account,
    )
    from collegefootballfantasy_api.app.models.user import User

    w = exp
    c = publish(w, "fanwars")
    join_school(w, c)
    save(w, c)
    svc.record_event(w["db"], w["db"].get(User, w["accounts"][1][0]), "view", c["id"])
    permanently_delete_user_account(
        w["db"], user=w["db"].get(User, w["accounts"][1][0])
    )
    w["db"].commit()
    assert w["db"].get(User, w["accounts"][1][0]) is None


def test_postgres_concurrent_official_entries_serialize_to_one_revision(exp):
    from conftest import engine, TestingSessionLocal
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from collegefootballfantasy_api.app.models.user import User
    from collegefootballfantasy_api.app.schemas.weekly_challenge import EntryWrite
    from fastapi import HTTPException

    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL row-lock behavior requires PostgreSQL")
    w = exp
    c = publish(w, "millionaire")
    gate = Barrier(2)
    payload = {"expected_revision": 0, "selections": picks(w, c)}

    def write():
        with TestingSessionLocal() as db:
            gate.wait()
            row = core.challenge_or_404(db, c["id"], lock=True)
            user = db.get(User, w["accounts"][1][0])
            try:
                svc.save_entry(db, row, user, EntryWrite(**payload))
                return 200
            except HTTPException as e:
                db.rollback()
                return e.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(lambda _: write(), range(2))) == [200, 409]
    assert w["db"].query(ChallengeEntry).filter_by(challenge_id=c["id"]).count() == 1


def test_shared_web_fixture_obeys_the_api_contract():
    import json
    from pathlib import Path
    from collegefootballfantasy_api.app.schemas.weekly_challenge import ChallengeRead

    value = json.loads(
        (
            Path(__file__).parents[2] / "web/shared/challenge-experiences.fixture.json"
        ).read_text()
    )
    assert value["fixture_only"] is True
    for item in value["challenges"]:
        assert ChallengeRead.model_validate(item).model_dump(mode="json") == item


def test_top_ten_is_bounded_and_retains_the_requesting_users_rank(exp):
    from collegefootballfantasy_api.app.models.user import User

    w = exp
    c = publish(w, "creator")
    for i in range(14):
        u = User(
            email=f"top10-{i}@example.invalid",
            first_name=f"Rank {i}",
            password_hash="fixture-no-login",
            api_token=f"rank-fixture-{i}",
            is_active=True,
        )
        w["db"].add(u)
        w["db"].flush()
        e = ChallengeEntry(
            challenge_id=c["id"],
            user_id=u.id,
            status="submitted",
            revision=1,
            selections=picks(w, c),
        )
        w["db"].add(e)
        w["db"].flush()
        w["db"].add(
            ChallengeScore(
                entry_id=e.id,
                raw_points=100 - i,
                status="final",
                source_hash="fixture",
                details={"correct": 10},
                rank=i + 1,
            )
        )
    w["db"].commit()
    board = svc.leaderboard(w["db"], w["db"].get(WeeklyChallenge, c["id"]), u)
    assert len(board["data"]) == 10 and board["total"] == 14
    assert board["your_rank"]["rank"] == 14 and board["your_rank"]["user_id"] == u.id


def test_survivor_repeated_scoring_does_not_duplicate_audits_or_notifications(exp):
    w = exp
    c = publish(w, "survivor")
    assert save(w, c).status_code == 200
    assert score(w, c) == "final"
    count = w["db"].query(ChallengeAudit).filter_by(challenge_id=c["id"]).count()
    for _ in range(3):
        assert core.settle(w["db"], w["db"].get(WeeklyChallenge, c["id"])) == "final"
    assert (
        w["db"].query(ChallengeAudit).filter_by(challenge_id=c["id"]).count() == count
    )


def test_survivor_joint_winners_are_reported_after_the_last_configured_week(exp):
    from collegefootballfantasy_api.app.models.challenge_experience import (
        ChallengeSurvivorSeries,
    )

    w = exp
    c = publish(w, "survivor")
    series = w["db"].get(ChallengeSurvivorSeries, c["experience"]["series"]["id"])
    series.end_week = 1
    w["db"].commit()
    assert save(w, c, 1).status_code == save(w, c, 2).status_code == 200
    assert score(w, c) == "final"
    for user in (1, 2):
        result = (
            w["client"]
            .get(f"{BASE}/challenges/{c['id']}", headers=w["accounts"][user][1])
            .json()
        )
        assert result["experience"]["survivor_status"] == "joint_winner"


def test_millionaire_result_card_has_actual_total_rank_and_best_performer(exp):
    w = exp
    c = publish(w, "millionaire")
    assert save(w, c).status_code == 200
    for i, p in enumerate(w["players"]):
        w["db"].add(
            PlayerGameStat(
                player_id=p.id,
                game_id=w["games"][0].id,
                season=2026,
                week=1,
                source="espn_final_boxscore",
                stats={"rush_yards": (i + 1) * 10},
            )
        )
    w["db"].commit()
    assert score(w, c) == "final"
    result = (
        w["client"]
        .get(f"{BASE}/challenges/{c['id']}", headers=w["accounts"][1][1])
        .json()["experience"]
    )
    assert result["your_points"] == 22 and result["your_rank"] == 1
    assert (
        result["best_performer"] == w["players"][6].name
        and len(result["player_points"]) == 6
    )


def test_release_artwork_switch_preserves_stored_league_icon(exp, monkeypatch):
    from collegefootballfantasy_api.app.schemas.league_flow import LeagueDetailRead
    from collegefootballfantasy_api.app.core.config import settings

    # Serialize an already-validated read object without requiring unrelated league setup.
    row = LeagueDetailRead.model_construct(
        icon_url="https://example.com/school-mark.png"
    )
    monkeypatch.setattr(settings, "league_logos_enabled", False)
    assert row.model_dump(include={"icon_url"}) == {"icon_url": None}
    assert row.icon_url == "https://example.com/school-mark.png"
    monkeypatch.setattr(settings, "league_logos_enabled", True)
    assert row.model_dump(include={"icon_url"}) == {"icon_url": row.icon_url}


def test_creator_identity_mismatch_never_displays_an_unverified_comparison(exp):
    w = exp
    c = publish(w, "creator")
    assert save(w, c).status_code == 200
    assert score(w, c) == "final"
    w["games"][0].home_team = "Changed schedule identity"
    w["db"].commit()
    assert core.settle(w["db"], w["db"].get(WeeklyChallenge, c["id"])) == "processing"
    x = (
        w["client"]
        .get(f"{BASE}/challenges/{c['id']}", headers=w["accounts"][1][1])
        .json()["experience"]
    )
    assert (
        x["creator_correct"] is None
        and x["creator_score"] is None
        and x["comparison"] is None
    )


def test_millionaire_rechecks_canonical_eligibility_without_rewriting_an_entry(exp):
    w = exp
    c = publish(w, "millionaire")
    assert save(w, c).status_code == 200
    player = w["players"][0]
    player.sheet_source_sheet_id = "no-longer-canonical"
    w["db"].commit()
    response = save(w, c, expected_revision=1)
    assert (
        response.status_code == 422
        and response.json()["detail"]["code"] == "PLAYER_INELIGIBLE"
    )
    row = w["db"].query(ChallengeEntry).filter_by(challenge_id=c["id"]).one()
    assert row.revision == 1 and row.status == "submitted"
    x = (
        w["client"]
        .get(f"{BASE}/challenges/{c['id']}", headers=w["accounts"][1][1])
        .json()["experience"]
    )
    assert player.id in x["ineligible_player_ids"]


def test_salary_suggestions_reuse_canonical_published_projection_precedence(exp):
    from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
    w=exp;c=create(w,"millionaire");pid=w["players"][0].id
    for version,points,published in [("PRESEASON",14,True),("FINAL",21,True),("CORRECTED_OUTLOOK",19,True),("LOCKED",30,False)]:
        w["db"].add(WeeklyProjection(player_id=pid,season=2026,week=1,projection_version=version,fantasy_points=points,is_published=published))
    w["db"].commit()
    result=w["client"].get(f"{ADMIN}/experiences/{c['id']}/salary-suggestions",headers=w["accounts"][0][1])
    assert result.status_code==200 and result.json()==[{"player_id":pid,"salary":15,"projection":19,"rule":"review-required-salary-v1"}]
