"""Seed PostgreSQL chat data and assert the unread query uses the chat index.

Run after Alembic migrations against a disposable PostgreSQL database:

    DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:55493/collegefootballfantasy \
      PYTHONPATH=. uv run python scripts/explain_chat_query_indexes.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from collegefootballfantasy_api.app.db.session import SessionLocal, engine
from collegefootballfantasy_api.app.models import player as _player
from collegefootballfantasy_api.app.models import roster as _roster
from collegefootballfantasy_api.app.models.chat import ChatMessage, ChatReadState, ChatThread
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_member import LeagueMember
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.user import User


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _plan_index_names(node: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    index_name = node.get("Index Name")
    if isinstance(index_name, str):
        names.add(index_name)
    for child in node.get("Plans", []):
        if isinstance(child, dict):
            names.update(_plan_index_names(child))
    return names


def _seed_chat_data(thread_count: int, messages_per_thread: int) -> dict[str, Any]:
    suffix = uuid.uuid4().hex[:12]
    now = _utcnow()
    with SessionLocal() as db:
        reader = User(
            email=f"chat-index-reader-{suffix}@example.com",
            first_name="Chat Index Reader",
            password_hash="not-used",
            api_token=f"chat-index-reader-{suffix}",
            email_verified_at=now,
        )
        peers = [
            User(
                email=f"chat-index-peer-{position}-{suffix}@example.com",
                first_name=f"Chat Index Peer {position}",
                password_hash="not-used",
                api_token=f"chat-index-peer-{position}-{suffix}",
                email_verified_at=now,
            )
            for position in range(thread_count)
        ]
        db.add_all([reader, *peers])
        db.flush()
        league = League(
            name=f"Chat index benchmark {suffix}",
            season_year=2026,
            commissioner_user_id=reader.id,
            max_teams=max(2, thread_count + 1),
        )
        db.add(league)
        db.flush()
        db.add(LeagueMember(league_id=league.id, user_id=reader.id, role="commissioner"))

        threads = [
            ChatThread(
                league_id=league.id,
                thread_type="direct",
                created_by_user_id=reader.id,
                direct_user_low_id=min(reader.id, peer.id),
                direct_user_high_id=max(reader.id, peer.id),
            )
            for peer in peers
        ]
        db.add_all(threads)
        db.flush()

        created_at = now - timedelta(days=1)
        payloads = []
        for thread, peer in zip(threads, peers, strict=True):
            payloads.extend(
                {
                    "thread_id": thread.id,
                    "league_id": league.id,
                    "sender_user_id": peer.id,
                    "message_type": "user",
                    "body": f"Indexed chat message {message_number}",
                    "metadata_json": {},
                    "created_at": created_at + timedelta(seconds=message_number),
                    "updated_at": created_at + timedelta(seconds=message_number),
                }
                for message_number in range(messages_per_thread)
            )
        db.bulk_insert_mappings(ChatMessage, payloads)
        db.flush()

        sampled_threads = threads[: min(3, len(threads))]
        for thread in sampled_threads:
            latest_message_id = db.scalar(
                text("SELECT max(id) FROM chat_messages WHERE thread_id = :thread_id"),
                {"thread_id": thread.id},
            )
            db.add(
                ChatReadState(
                    thread_id=thread.id,
                    user_id=reader.id,
                    last_read_message_id=latest_message_id - 100,
                    last_read_at=now,
                )
            )
        db.commit()
        return {
            "league_id": league.id,
            "reader_id": reader.id,
            "thread_ids": [thread.id for thread in sampled_threads],
            "all_thread_ids": [thread.id for thread in threads],
            "peer_ids": [peer.id for peer in peers],
        }


def _explain_unread_query(seed: dict[str, Any]) -> tuple[dict[str, Any], set[str]]:
    with SessionLocal() as db:
        db.execute(text("ANALYZE chat_messages"))
        db.execute(text("ANALYZE chat_read_states"))
        plan_json = db.execute(
            text(
                """
                EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
                SELECT message.thread_id, count(message.id)
                FROM chat_messages AS message
                LEFT JOIN chat_read_states AS read_state
                  ON read_state.thread_id = message.thread_id
                 AND read_state.user_id = :reader_id
                WHERE message.thread_id = ANY(:thread_ids)
                  AND message.deleted_at IS NULL
                  AND (message.sender_user_id IS NULL OR message.sender_user_id <> :reader_id)
                  AND (
                    read_state.last_read_message_id IS NULL
                    OR message.id > read_state.last_read_message_id
                  )
                GROUP BY message.thread_id
                """
            ),
            {"reader_id": seed["reader_id"], "thread_ids": seed["thread_ids"]},
        ).scalar_one()
    root = plan_json[0]["Plan"] if isinstance(plan_json, list) else json.loads(plan_json)[0]["Plan"]
    return root, _plan_index_names(root)


def _cleanup(seed: dict[str, Any]) -> None:
    with SessionLocal() as db:
        db.execute(text("DELETE FROM chat_read_states WHERE thread_id = ANY(:thread_ids)"), {"thread_ids": seed["all_thread_ids"]})
        db.execute(text("DELETE FROM chat_messages WHERE thread_id = ANY(:thread_ids)"), {"thread_ids": seed["all_thread_ids"]})
        db.execute(text("DELETE FROM chat_threads WHERE id = ANY(:thread_ids)"), {"thread_ids": seed["all_thread_ids"]})
        db.execute(text("DELETE FROM league_members WHERE league_id = :league_id"), {"league_id": seed["league_id"]})
        db.execute(text("DELETE FROM leagues WHERE id = :league_id"), {"league_id": seed["league_id"]})
        db.execute(text("DELETE FROM users WHERE id = ANY(:user_ids)"), {"user_ids": [seed["reader_id"], *seed["peer_ids"]]})
        db.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify PostgreSQL uses chat indexes for unread counts.")
    parser.add_argument("--threads", type=int, default=40, help="Number of direct threads to seed.")
    parser.add_argument("--messages-per-thread", type=int, default=4000, help="Messages to seed in each thread.")
    parser.add_argument("--keep-data", action="store_true", help="Keep benchmark rows for manual plan inspection.")
    args = parser.parse_args()
    if engine.dialect.name != "postgresql":
        raise SystemExit("This benchmark requires PostgreSQL; set DATABASE_URL to a PostgreSQL database.")

    seed = _seed_chat_data(max(4, args.threads), max(100, args.messages_per_thread))
    try:
        plan, index_names = _explain_unread_query(seed)
        expected_indexes = {"ix_chat_messages_thread_id"}
        missing_indexes = expected_indexes - index_names
        if missing_indexes:
            raise AssertionError(
                f"Unread query did not use required chat indexes: {sorted(missing_indexes)}; plan={json.dumps(plan)}"
            )
        print(
            json.dumps(
                {
                    "thread_count": len(seed["all_thread_ids"]),
                    "queried_threads": len(seed["thread_ids"]),
                    "indexes_used": sorted(index_names),
                }
            )
        )
    finally:
        if not args.keep_data:
            _cleanup(seed)


if __name__ == "__main__":
    main()
