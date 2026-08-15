from collegefootballfantasy_api.app.db.session import normalize_database_url


def test_normalize_database_url_uses_psycopg_v3_for_generic_postgres_urls():
    assert (
        normalize_database_url("postgresql://user:password@db.example/app")
        == "postgresql+psycopg://user:password@db.example/app"
    )
    assert (
        normalize_database_url("postgres://user:password@db.example/app")
        == "postgresql+psycopg://user:password@db.example/app"
    )


def test_normalize_database_url_preserves_explicit_sqlalchemy_drivers():
    assert (
        normalize_database_url("postgresql+psycopg://user:password@db.example/app")
        == "postgresql+psycopg://user:password@db.example/app"
    )
