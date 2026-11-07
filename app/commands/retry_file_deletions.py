from app.db.database import SessionLocal
from app.services.file_cleanup_service import retry_file_deletions


def main() -> None:
    db = SessionLocal()

    try:
        result = retry_file_deletions(db)

        print("File cleanup completed.")
        print(f"Tasks completed: {result['deleted']}")
        print(f"Tasks failed: {result['failed']}")

    finally:
        db.close()


if __name__ == "__main__":
    main()