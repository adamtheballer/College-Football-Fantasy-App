from api.app.db.session import SessionLocal
from api.app.services.news_ingestion import ensure_default_news_source


def main() -> None:
    db = SessionLocal()
    try:
        source = ensure_default_news_source(db)
        db.commit()
        print(f"seeded news source: {source.name} ({source.url})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
