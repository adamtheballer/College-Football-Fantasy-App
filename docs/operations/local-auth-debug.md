# Local Auth Debugging

Use these checks when a previously working local account suddenly cannot sign in. The most common cause is that the app is pointed at a different Docker database volume, so the user row is missing or has different lockout/password state.

## Check the current user row

```bash
docker compose exec db psql -U postgres -d collegefootballfantasy -c "
select id,
       email,
       email_verified_at,
       failed_login_attempts,
       locked_until,
       last_failed_login_at,
       last_login,
       created_at
from users
where lower(email) = lower('emmab1167@icloud.com');
"
```

Interpretation:

- No row returned: the account does not exist in this local database.
- `locked_until` is in the future: the account is temporarily locked.
- `failed_login_attempts` is high: the account is close to lockout.
- Row exists, is not locked, and still fails: the password hash does not match the password being entered.

## Unlock a local account

```bash
docker compose exec db psql -U postgres -d collegefootballfantasy -c "
update users
set failed_login_attempts = 0,
    locked_until = null,
    last_failed_login_at = null
where lower(email) = lower('emmab1167@icloud.com');
"
```

## Repair a local account password

If the row exists, is active, is verified, is not locked, and login still returns `401`, the stored password hash does not match the password being entered. Do not add a login bypass. Repair the local row explicitly:

```bash
PYTHONPATH=. uv run python scripts/repair_local_auth_account.py --email emmab1167@icloud.com --first-name Emma
```

The command prompts for the password without echoing it, then:

- creates the user if this local database lost the row;
- marks the email verified;
- clears failed login and lockout state;
- stores a fresh Argon2 hash for the entered password;
- never prints or logs the password.

For Postgres.app local databases, make sure `DATABASE_URL` points at that database before running the command.

## Avoid accidental user deletion

Do not run `docker compose down -v` against the main local stack unless you intentionally want to delete all local users and league data.

For disposable clean database testing, use an isolated Compose project name:

```bash
COMPOSE_PROJECT_NAME=cff_disposable DB_PORT=55438 docker compose up --build -d
COMPOSE_PROJECT_NAME=cff_disposable docker compose down -v
```
