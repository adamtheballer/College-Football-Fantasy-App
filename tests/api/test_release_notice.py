from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.models.user_release_notice import UserReleaseNotice
from collegefootballfantasy_api.app.services.release_notice import claim_release_notice
from conftest import TestingSessionLocal, engine

PATH = "/release-notes/1.03/claim"


def account(client, suffix="one"):
    response = client.post("/auth/signup", json={"first_name": "Update Manager", "email": f"update-{suffix}@example.com", "password": "StrongPass123!"})
    assert response.status_code == 201
    data = response.json()
    from datetime import datetime, timezone
    with TestingSessionLocal() as db:
        db.get(User,data["user"]["id"]).created_at=datetime(2026,10,1,tzinfo=timezone.utc)
        db.commit()
    return data['user']['id'], {"Authorization": f"Bearer {data['access_token']}", "X-CFFB-Release-Account": str(data['user']['id'])}


def test_once_per_account_survives_profile_changes_and_new_sessions(client, db_session):
    uid, headers = account(client)
    first = client.post(PATH, headers=headers, json={})
    assert first.status_code == 200
    assert first.json() == {"account_id": uid, "release_key": "1.03", "authorization": "granted", "claimed_at": first.json()['claimed_at']}
    row = db_session.get(UserReleaseNotice, (uid, "1.03"))
    assert row is not None
    user = db_session.get(User, uid)
    assert user.review_request_claimed_at is None  # Independent App Review lifetime.
    user.first_name = 'Renamed Manager'
    db_session.commit()
    login = client.post('/auth/login', json={'email': 'update-one@example.com', 'password': 'StrongPass123!'}).json()
    headers['Authorization'] = f"Bearer {login['access_token']}"
    for _ in range(3):
        result = client.post(PATH, headers=headers, json={}).json()
        assert result == {**first.json(), 'authorization': 'already_seen'}
    assert db_session.query(UserReleaseNotice).count() == 1


def test_all_accounts_receive_their_own_opportunity(client):
    for name in ('first', 'second'):
        uid, headers = account(client, name)
        assert client.post(PATH, headers=headers, json={}).json()['account_id'] == uid
        assert client.post(PATH, headers=headers, json={}).json()['authorization'] == 'already_seen'


def test_authentication_account_switch_and_no_client_owner_selector(client, db_session):
    uid, first = account(client, 'first')
    other_id, other = account(client, 'other')
    assert client.post(PATH, json={}).status_code == 401
    assert client.post(PATH, headers={'Authorization': first['Authorization']}, json={}).status_code == 409
    assert client.post(PATH, headers={**other, 'X-CFFB-Release-Account': str(uid)}, json={}).status_code == 409
    assert client.post(PATH, headers=first, json={'account_id': other_id}).status_code == 422
    assert client.post('/release-notes/1.04/claim', headers=first, json={}).status_code == 404
    assert db_session.query(UserReleaseNotice).count() == 0
    assert client.post(PATH, headers=other, json={}).json()['authorization'] == 'granted'


def test_failed_storage_does_not_consume_the_notice(client, db_session, monkeypatch):
    uid, _ = account(client)
    commit = db_session.commit
    def fail(): raise RuntimeError('local test write failed')
    monkeypatch.setattr(db_session, 'commit', fail)
    with pytest.raises(RuntimeError): claim_release_notice(db_session, uid)
    db_session.rollback()
    monkeypatch.setattr(db_session, 'commit', commit)
    assert db_session.get(UserReleaseNotice, (uid, '1.03')) is None
    assert claim_release_notice(db_session, uid).authorization == 'granted'


def test_database_enforces_account_release_uniqueness(client, db_session):
    uid, headers = account(client)
    result = client.post(PATH, headers=headers, json={}).json()
    from datetime import datetime
    db_session.add(UserReleaseNotice(user_id=uid, release_key='1.03', claimed_at=datetime.fromisoformat(result['claimed_at'])))
    with pytest.raises(IntegrityError): db_session.commit()
    db_session.rollback()
    assert db_session.query(UserReleaseNotice).count() == 1


@pytest.mark.skipif(engine.dialect.name != 'postgresql', reason='PostgreSQL row locking required')
def test_two_devices_receive_exactly_one_presentation_grant(client):
    uid, _ = account(client)
    barrier = Barrier(2)
    def claim():
        with TestingSessionLocal() as db:
            barrier.wait(timeout=10)
            return claim_release_notice(db, uid).authorization
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(claim) for _ in range(2)]
        assert sorted(f.result(timeout=15) for f in futures) == ['already_seen', 'granted']
    with TestingSessionLocal() as db:
        assert len(db.scalars(select(UserReleaseNotice)).all()) == 1
