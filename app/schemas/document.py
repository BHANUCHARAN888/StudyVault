from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DocumentResponse(BaseModel):
    id: int
    title: str
    original_filename: str
    file_size: int
    content_type: str
    owner_id: int
    subject_id: int | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    subject_id: int | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Document title cannot be empty")
        return value
