from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, model_validator

from pathlib import Path

class Settings(BaseSettings):
    APP_NAME: str = "Team Issue Tracker API"
    APP_ENV: str = "development"

    DATABASE_URL: str = ""
    REDIS_URL: str = "redis://localhost:6379/0"

    JWT_SECRET_KEY: str = ""
    JWT_REFRESH_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"

    ACCESS_TOKEN_EXPIRES_MINUTES: int = 5
    REFRESH_TOKEN_EXPIRES_DAYS: int = 7

    SQL_ECHO:bool = True

    SEED_ADMIN_EMAIL: str = ""
    SEED_ADMIN_PASSWORD: str = ""

    BACKEND_CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    @field_validator(
        "DATABASE_URL",
        "JWT_SECRET_KEY",
        "JWT_REFRESH_SECRET_KEY",
        "JWT_ALGORITHM",
        "BACKEND_CORS_ORIGINS"
    )
    @classmethod
    def required_string_must_not_be_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("This setting must not be empty")
        return value

    @field_validator(
        "ACCESS_TOKEN_EXPIRES_MINUTES",
        "REFRESH_TOKEN_EXPIRES_DAYS",
    )
    @classmethod
    def token_expiry_must_be_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Token expiry values must be greater than 0")
        return value

    @model_validator(mode="after")
    def production_secrets_must_not_be_placeholders(self):
        if self.APP_ENV.lower() == "production":
            placeholder_values = {
                "replace-with-access-token-secret",
                "replace-with-refresh-token-secret"
            }

            if (
                self.JWT_SECRET_KEY in placeholder_values
                or self.JWT_REFRESH_SECRET_KEY in placeholder_values
            ):
                raise ValueError("Production JWT secrets must not use placeholder values")
            
        return self


    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent.parent / ".env"), # otherwise pytest will fail the relative import of .env
        extra="ignore"
    )



settings = Settings()