from sqlalchemy.orm import Session

from app.models.file_deletion_task import FileDeletionTask
from app.services.storage_service import delete_file


def retry_file_deletions(db: Session) -> dict[str, int]:
    """
    Retry pending Backblaze B2 object deletions.

    Failed tasks remain in the database for future retries.
    """
    tasks = (
        db.query(FileDeletionTask)
        .order_by(FileDeletionTask.created_at.asc())
        .limit(100)
        .all()
    )

    deleted = 0
    failed = 0

    for task in tasks:
        task_id = task.id
        object_key = task.file_path

        try:
            delete_file(object_key)

            db.delete(task)
            db.commit()
            deleted += 1

        except Exception as exc:
            db.rollback()

            try:
                pending_task = (
                    db.query(FileDeletionTask)
                    .filter(FileDeletionTask.id == task_id)
                    .first()
                )

                if pending_task is not None:
                    pending_task.attempts += 1
                    pending_task.last_error = str(exc)[:2000]
                    db.commit()

            except Exception:
                db.rollback()

            failed += 1

    return {
        "deleted": deleted,
        "failed": failed,
    }