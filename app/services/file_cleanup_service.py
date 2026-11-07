from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.file_deletion_task import FileDeletionTask


def retry_file_deletions(db: Session) -> dict[str, int]:
    """
    Retry pending file deletions.

    Only files inside the configured storage directory may be deleted.
    Failed tasks remain in the database for future retries.
    """
    storage_root = settings.storage_path.resolve()

    tasks = (
        db.query(FileDeletionTask)
        .order_by(FileDeletionTask.created_at.asc())
        .all()
    )

    deleted = 0
    failed = 0

    for task in tasks:
        task_id = task.id

        try:
            file_path = Path(task.file_path).resolve()

            # Reject paths outside the configured storage directory.
            if not file_path.is_relative_to(storage_root):
                raise ValueError(
                    "File path is outside the configured storage directory."
                )

            file_path.unlink(missing_ok=True)

            db.delete(task)
            db.commit()
            deleted += 1

        except Exception as exc:
            db.rollback()

            # Record the failure if the task still exists.
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