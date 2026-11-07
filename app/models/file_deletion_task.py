from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class FileDeletionTask(Base):
    __tablename__ = "file_deletion_tasks"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    file_path: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        unique=True,
    )

    attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    last_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )