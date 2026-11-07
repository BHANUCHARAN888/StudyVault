from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.subject import Subject
from app.models.user import User
from app.schemas.subject import SubjectCreate, SubjectUpdate


def create_subject(
    db: Session,
    data: SubjectCreate,
    current_user: User,
) -> Subject:
    name = data.name.strip()

    if not name:
        raise ValueError("Subject name cannot be empty")

    existing = db.scalar(
        select(Subject).where(
            Subject.owner_id == current_user.id,
            Subject.name == name,
        )
    )

    if existing:
        raise ValueError("Subject already exists")

    subject = Subject(name=name, owner_id=current_user.id)

    try:
        db.add(subject)
        db.commit()
        db.refresh(subject)
        return subject
    except Exception:
        db.rollback()
        raise


def list_subjects(db: Session, current_user: User) -> list[Subject]:
    return list(
        db.scalars(
            select(Subject)
            .where(Subject.owner_id == current_user.id)
            .order_by(Subject.name.asc())
        ).all()
    )


def update_subject(
    db: Session,
    subject_id: int,
    data: SubjectUpdate,
    current_user: User,
) -> Subject:
    subject = db.scalar(
        select(Subject).where(
            Subject.id == subject_id,
            Subject.owner_id == current_user.id,
        )
    )

    if subject is None:
        raise LookupError("Subject not found")

    name = data.name.strip()

    if not name:
        raise ValueError("Subject name cannot be empty")

    duplicate = db.scalar(
        select(Subject).where(
            Subject.owner_id == current_user.id,
            Subject.name == name,
            Subject.id != subject_id,
        )
    )

    if duplicate:
        raise ValueError("Subject already exists")

    subject.name = name

    try:
        db.commit()
        db.refresh(subject)
        return subject
    except Exception:
        db.rollback()
        raise


def delete_subject(
    db: Session,
    subject_id: int,
    current_user: User,
) -> None:
    subject = db.scalar(
        select(Subject).where(
            Subject.id == subject_id,
            Subject.owner_id == current_user.id,
        )
    )

    if subject is None:
        raise LookupError("Subject not found")

    try:
        db.delete(subject)
        db.commit()
    except Exception:
        db.rollback()
        raise
