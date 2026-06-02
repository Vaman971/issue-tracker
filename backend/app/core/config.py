from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Team Issue Tracker API"
    APP_ENV: str = "development"

    DATABASE_URL: str = ""
    REDIS_URL: str = "redis://localhost:6379/0"

    JWT_SECRET_KEY: str = ""
    JWT_REFRESH_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"

    ACCESS_TOKEN_EXPIRES_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRES_DAYS: int = 7

    SQL_ECHO: bool = False

    REDIS_DEFAULT_TTL_SECONDS: int = 300
    REDIS_HEALTHCHECK_TIMEOUT_SECONDS: int = 3

    AUTH_RATE_LIMIT_WINDOW_SECONDS: int = 60
    AUTH_RATE_LIMIT_LOGIN_MAX_ATTEMPTS: int = 5
    AUTH_RATE_LIMIT_REGISTER_MAX_ATTEMPTS: int = 3
    AUTH_RATE_LIMIT_REFRESH_MAX_ATTEMPTS: int = 10

    SEED_ADMIN_EMAIL: str = ""
    SEED_ADMIN_PASSWORD: str = ""

    BACKEND_CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Frontend URL (used for password-reset and email-verification links)
    FRONTEND_URL: str = "http://localhost:3000"

    # Email / SMTP
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "noreply@issuetracker.local"
    SMTP_FROM_NAME: str = "Issue Tracker"
    SMTP_USE_TLS: bool = True
    EMAILS_ENABLED: bool = False  # set True in production

    # Token expiry for email flows
    EMAIL_VERIFY_TOKEN_EXPIRES_HOURS: int = 24
    PASSWORD_RESET_TOKEN_EXPIRES_HOURS: int = 1

    # File Storage
    STORAGE_BACKEND: str = "local"  # "local" or "s3"
    LOCAL_UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE_MB: int = 10

    # AWS / S3
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "ap-south-1"
    S3_BUCKET_NAME: str = ""
    S3_PRESIGNED_URL_EXPIRES_SECONDS: int = 3600

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # Admin limit — increase by bumping this value
    MAX_ADMINS: int = 1

    @field_validator(
        "DATABASE_URL",
        "JWT_SECRET_KEY",
        "JWT_REFRESH_SECRET_KEY",
        "JWT_ALGORITHM",
        "BACKEND_CORS_ORIGINS",
    )
    @classmethod
    def required_string_must_not_be_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("This setting must not be empty")
        return value

    @field_validator(
        "ACCESS_TOKEN_EXPIRES_MINUTES",
        "REFRESH_TOKEN_EXPIRES_DAYS",
        "REDIS_DEFAULT_TTL_SECONDS",
        "REDIS_HEALTHCHECK_TIMEOUT_SECONDS",
        "AUTH_RATE_LIMIT_WINDOW_SECONDS",
        "AUTH_RATE_LIMIT_LOGIN_MAX_ATTEMPTS",
        "AUTH_RATE_LIMIT_REGISTER_MAX_ATTEMPTS",
        "AUTH_RATE_LIMIT_REFRESH_MAX_ATTEMPTS",
    )
    @classmethod
    def positive_numbers_only(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("This setting must be greater than 0")
        return value

    @model_validator(mode="after")
    def production_secrets_must_not_be_placeholders(self):
        if self.APP_ENV.lower() == "production":
            placeholder_values = {
                "replace-with-access-token-secret",
                "replace-with-refresh-token-secret",
            }

            if (
                self.JWT_SECRET_KEY in placeholder_values
                or self.JWT_REFRESH_SECRET_KEY in placeholder_values
            ):
                raise ValueError("Production JWT secrets must not use placeholder values")

        return self

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent.parent / ".env"),
        extra="ignore",
    )


settings = Settings()
