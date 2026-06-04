from datetime import datetime, timedelta, timezone

from api.app.integrations.college_football_news import parse_feed_entries, parse_index_entries
from api.app.models.news_item import NewsItem
from api.app.models.news_source import NewsSource
from api.app.models.player import Player
from api.app.services.news_classifier import classify_news
from api.app.services.news_relevance import compute_fantasy_relevance


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_user_and_token(client, suffix: str) -> str:
    response = client.post(
        "/auth/signup",
        json={
            "first_name": f"News{suffix}",
            "email": f"news-{suffix}@example.com",
            "password": "secret123",
        },
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def test_news_classifier_identifies_transfer_and_injury():
    assert classify_news("Five-star QB commits to Oregon after entering transfer portal") == "transfer"
    assert classify_news("Texas RB out after surgery with return timetable unclear") == "injury"


def test_news_relevance_prioritizes_transfer_and_injury_above_generic_preview():
    now = datetime.now(timezone.utc)
    transfer_score = compute_fantasy_relevance(
        category="transfer",
        title="QB enters portal and commits to Texas",
        published_at=now,
        player_id=1,
        canonical_team="Texas",
        position="QB",
        now=now,
    )
    injury_score = compute_fantasy_relevance(
        category="injury",
        title="Alabama WR out after injury",
        published_at=now,
        canonical_team="Alabama",
        position="WR",
        now=now,
    )
    generic_score = compute_fantasy_relevance(category="general", title="Conference preview released", now=now)
    assert transfer_score > generic_score
    assert injury_score > generic_score


def test_cfn_provider_normalizes_sample_feed_and_index_entries():
    feed_xml = """
    <rss><channel>
      <item>
        <title>LSU WR enters transfer portal</title>
        <link>https://collegefootballnews.com/news/lsu-wr-transfer</link>
        <description>Short metadata summary only.</description>
        <pubDate>Wed, 03 Jun 2026 15:00:00 GMT</pubDate>
        <guid>cfn-1</guid>
      </item>
    </channel></rss>
    """
    feed_entries = parse_feed_entries(feed_xml)
    assert feed_entries[0].title == "LSU WR enters transfer portal"
    assert feed_entries[0].summary == "Short metadata summary only."
    assert feed_entries[0].published_at is not None

    index_html = """
    <html><body>
      <a href="/news/oklahoma-qb-named-starter">Oklahoma QB Named Starter After Spring Battle</a>
      <a href="/rankings">Rankings</a>
    </body></html>
    """
    index_entries = parse_index_entries(index_html)
    assert len(index_entries) == 1
    assert index_entries[0].link == "https://collegefootballnews.com/news/oklahoma-qb-named-starter"


def test_manual_news_create_and_duplicate_source_url(client, db_session):
    token = create_user_and_token(client, "manual")
    player = Player(name="Arch Manning", position="QB", school="Texas", external_id=None)
    db_session.add(player)
    db_session.commit()

    payload = {
        "title": "Arch Manning named Texas starting quarterback",
        "summary": "Metadata summary for a fantasy-relevant role update.",
        "category": "depth_chart",
        "source_name": "Manual",
        "source_url": "https://example.com/manual-arch-starter",
        "published_at": datetime.now(timezone.utc).isoformat(),
    }
    response = client.post("/news/manual", json=payload, headers=auth_headers(token))
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["player_id"] == player.id
    assert data["category"] == "depth_chart"
    assert data["fantasy_relevance_score"] > 70

    duplicate = client.post("/news/manual", json=payload, headers=auth_headers(token))
    assert duplicate.status_code == 409


def test_news_feed_sorting_transfers_and_hidden_filter(client, db_session):
    now = datetime.now(timezone.utc)
    high = NewsItem(
        source_name="Manual",
        source_url="https://example.com/high-transfer",
        source_type="manual",
        title="Ohio State RB enters transfer portal",
        summary="Portal movement.",
        content_hash="hash-high-transfer",
        category="transfer",
        status="new",
        published_at=now,
        discovered_at=now,
        fantasy_relevance_score=90,
        confidence_score=0,
        fantasy_impact="Potential role change.",
        tags_json=["transfer"],
        raw_payload_json={},
    )
    low = NewsItem(
        source_name="Manual",
        source_url="https://example.com/low-preview",
        source_type="manual",
        title="Generic team preview",
        summary="Preview.",
        content_hash="hash-low-preview",
        category="general",
        status="new",
        published_at=now - timedelta(days=2),
        discovered_at=now,
        fantasy_relevance_score=15,
        confidence_score=0,
        fantasy_impact="Monitor.",
        tags_json=["general"],
        raw_payload_json={},
    )
    hidden = NewsItem(
        source_name="Manual",
        source_url="https://example.com/hidden-transfer",
        source_type="manual",
        title="Hidden transfer",
        summary="Hidden.",
        content_hash="hash-hidden-transfer",
        category="transfer",
        status="hidden",
        published_at=now,
        discovered_at=now,
        fantasy_relevance_score=95,
        confidence_score=0,
        fantasy_impact="Hidden.",
        tags_json=["transfer"],
        raw_payload_json={},
    )
    db_session.add_all([high, low, hidden])
    db_session.commit()

    feed = client.get("/news/feed")
    assert feed.status_code == 200
    rows = feed.json()["data"]
    assert rows[0]["title"] == "Ohio State RB enters transfer portal"
    assert all(row["title"] != "Hidden transfer" for row in rows)

    transfers = client.get("/news/transfers")
    assert transfers.status_code == 200
    transfer_rows = transfers.json()["data"]
    assert len(transfer_rows) == 1
    assert transfer_rows[0]["category"] == "transfer"


def test_news_feed_recent_sort_and_team_news_group(client, db_session):
    now = datetime.now(timezone.utc)
    rows = []
    for index, category in enumerate(["depth_chart", "coaching", "eligibility", "team_news", "general", "injury"]):
        rows.append(
            NewsItem(
                source_name="Manual",
                source_url=f"https://example.com/recent-{index}",
                source_type="manual",
                title=f"Recent {category} item {index}",
                summary="Recent item.",
                content_hash=f"hash-recent-{index}",
                category=category,
                status="new",
                published_at=now - timedelta(minutes=index),
                discovered_at=now - timedelta(minutes=index),
                fantasy_relevance_score=50 + index,
                confidence_score=0,
                fantasy_impact="Monitor.",
                tags_json=[category],
                raw_payload_json={},
            )
        )
    hidden = NewsItem(
        source_name="Manual",
        source_url="https://example.com/recent-hidden",
        source_type="manual",
        title="Hidden recent team item",
        summary="Hidden.",
        content_hash="hash-recent-hidden",
        category="team_news",
        status="hidden",
        published_at=now + timedelta(minutes=1),
        discovered_at=now + timedelta(minutes=1),
        fantasy_relevance_score=100,
        confidence_score=0,
        fantasy_impact="Hidden.",
        tags_json=["team_news"],
        raw_payload_json={},
    )
    db_session.add_all([*rows, hidden])
    db_session.commit()

    recent = client.get("/news/feed?sort=recent&limit=5")
    assert recent.status_code == 200
    recent_rows = recent.json()["data"]
    assert len(recent_rows) == 5
    assert recent_rows[0]["title"] == "Recent depth_chart item 0"
    assert all(row["title"] != "Hidden recent team item" for row in recent_rows)

    team_news = client.get("/news/feed?categories=team_news,depth_chart,coaching,eligibility&sort=recent&limit=5")
    assert team_news.status_code == 200
    team_categories = [row["category"] for row in team_news.json()["data"]]
    assert team_categories == ["depth_chart", "coaching", "eligibility", "team_news"]


def test_news_ingestion_does_not_crash_if_cfn_unavailable(client, db_session, monkeypatch):
    token = create_user_and_token(client, "ingest")
    source = NewsSource(
        name="College Football News",
        source_type="html_index",
        url="https://collegefootballnews.com/",
        active=True,
        priority=80,
        poll_interval_minutes=60,
    )
    db_session.add(source)
    db_session.commit()

    def fail_fetch(_self, *, limit=50):
        raise RuntimeError("source unavailable")

    monkeypatch.setattr("api.app.services.news_ingestion.CollegeFootballNewsProvider.fetch_entries", fail_fetch)
    response = client.post("/news/ingest?source=cfn&force=true", headers=auth_headers(token))
    assert response.status_code == 200
    assert response.json()["errors"]
