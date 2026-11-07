
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "StudyVault API"
    app_env: str = "development"

    database_url: str

    jwt_secret_key: SecretStr = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 465
    smtp_email: str | None = None
    smtp_app_password: SecretStr | None = None
    email_from: str | None = None

    frontend_url: str = "http://localhost:5173"

    storage_dir: str = "storage/documents"
    max_file_size_mb: int = 50

    @field_validator("jwt_algorithm")
    @classmethod
    def validate_jwt_algorithm(cls, value: str) -> str:
        if value != "HS256":
            raise ValueError("Only HS256 is supported")
        return value

    @field_validator("access_token_expire_minutes")
    @classmethod
    def validate_token_expiry(cls, value: int) -> int:
        if value <= 0:
            raise ValueError(
                "Access token expiry must be greater than zero"
            )
        return value

    @field_validator("max_file_size_mb")
    @classmethod
    def validate_max_file_size(cls, value: int) -> int:
        if value <= 0:
            raise ValueError(
                "Maximum file size must be greater than zero"
            )
        return value

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def storage_path(self) -> Path:
        path = Path(self.storage_dir)

        if not path.is_absolute():
            path = BASE_DIR / path

        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
