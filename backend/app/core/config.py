from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Team Issue Tracker API"
    APP_ENV: str = "development"

    DATABASE_URL: str = ""
    REDIS_URL: str = "redis://localhost:6379/0"

    # Turns every cache read and write into a no-op. Off for evaluation runs:
    # a benchmark that reads a cache is not measuring the current code, it is
    # measuring whatever produced the entries — a stale filter or expansion
    # written by a previous prompt survives a prompt change and quietly
    # invalidates the comparison. Also spares a run outside Docker from
    # failing to resolve the `redis` hostname on every lookup.
    CACHE_ENABLED: bool = True

    JWT_SECRET_KEY: str = ""
    JWT_REFRESH_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"

    ACCESS_TOKEN_EXPIRES_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRES_DAYS: int = 7

    SQL_ECHO: bool = False

    REDIS_DEFAULT_TTL_SECONDS: int = 300
    # embeddings never go stale: the same text and model always give the
    # same vector, whatever happens to the corpus
    REDIS_EMBEDDING_TTL_SECONDS: int = 60 * 60 * 24 * 30
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

    # Open-AI API Key
    OPENAI_API_KEY:str = ""
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_EMBEDDING_CONCURRENCY: int = 10
    OPENAI_CHAT_MODEL: str = "gpt-5"
    OPENAI_ANSWER_MODEL: str = "gpt-5-mini"

    # Reranking has its own model because it is the single most expensive
    # stage — roughly 60% of a turn — and the eval harness showed the cheaper
    # model does the job. Across 23 ground-truth cases gpt-5-mini matched
    # gpt-5 exactly on reranking (recall@5 1.000, 0 misses, same two
    # multi-target rescues) and was marginally better end to end (answer
    # hit@5 1.000 against 0.957). It is a fifth of the price.
    #
    # Caveat: mini returned one unparseable response in 23. The reranker
    # already falls back to retrieval order there, and the confidence gate
    # treats an unscored result as no evidence rather than bad evidence, so
    # the failure is contained — but it is why this is a separate setting and
    # not a change to OPENAI_CHAT_MODEL, which the other four stages use and
    # which was not measured here.
    OPENAI_RERANK_MODEL: str = "gpt-5-mini"
    OPENAI_REASONING_EFFORT: str = "minimal"
    DAMPING_CONSTANT: int = 30

    # Below this reranker score the best retrieved result is not relevant
    # enough to answer from, and the turn is declined instead.
    #
    # Measured rather than guessed: across six questions with real matches
    # the top score ran 0.74-0.99, and across six plausible questions with
    # nothing in the corpus it ran 0.06-0.18. 0.35 sits in that gap with
    # roughly a factor of two of headroom either side. Re-measure before
    # changing the reranker model or its prompt.
    RAG_MIN_RELEVANCE_SCORE: float = 0.35

    # Ceiling on one /rag/chat turn, covering retrieval and generation.
    # The per-downstream timeouts below sit underneath it.
    RAG_REQUEST_TIMEOUT_SECONDS: int = 120

    # Per-call ceiling on any OpenAI request, and how many times the SDK
    # retries one with exponential backoff before giving up. Both are applied
    # in `app/rag/llm/client.py`, which every adapter builds its client from.
    #
    # Sized so one call's COMPLETE retry chain fits inside the turn ceiling:
    # 30 * (2 + 1) = 90s < 120s. Generous against observed latencies — the
    # slowest stage runs about 5s — so the budget only matters when something
    # is genuinely wrong. A turn runs roughly four sequential model calls, so
    # if several each burn their chain the turn ceiling cuts the request off,
    # which is the intended strict behaviour.
    OPENAI_TIMEOUT_SECONDS: int = 30
    OPENAI_MAX_RETRIES: int = 2

    # A tighter per-attempt budget for the calls that return a short JSON
    # payload — routing, rewriting, filtering, multi-query and reranking.
    #
    # Measured on the reranker: with identical input and identical output
    # (323 tokens) latency ranged 3.5s to 60s, and with retries disabled an
    # attempt timed out at exactly 30.04s. The tail is the API stalling, not
    # the prompt. At 30s a stall costs 30s before the retry even starts; at
    # 10s it costs 10s, and the retry usually lands in about 4s.
    #
    # The answer model keeps the 30s budget above: it streams, so its time is
    # spent producing tokens the user is already reading.
    OPENAI_STRUCTURED_TIMEOUT_SECONDS: int = 10

    # How long to wait for a database connection to be established. Deliberately
    # not a query timeout: ingestion runs long statements through this engine.
    DB_CONNECT_TIMEOUT_SECONDS: int = 10

    # Redis reconnect policy. A turn consults the cache roughly fifteen times,
    # so every second spent failing is multiplied by fifteen. Measured: at 2
    # retries against the 3s healthcheck timeout a turn took 77s with Redis
    # down versus 15s with it up. Hence a connect timeout of its own, an order
    # of magnitude shorter than the healthcheck's, and a single retry.
    # Two different budgets, conflated at first and split after a cold-start
    # script timed out against a HEALTHY Redis: establishing a connection has
    # to cover DNS, which on a cold process in Docker can take over a second,
    # while a command on an established connection returns in well under a
    # millisecond. One is paid per connection, the other per lookup.
    REDIS_CONNECT_TIMEOUT_SECONDS: float = 2.0
    REDIS_COMMAND_TIMEOUT_SECONDS: float = 0.5
    REDIS_RETRY_ATTEMPTS: int = 1
    REDIS_RETRY_BACKOFF_CAP_SECONDS: float = 0.1

    # Requests one user may make to /rag/chat per window. Per user, not per IP:
    # the endpoint is authenticated and each call costs real money.
    RAG_RATE_LIMIT_WINDOW_SECONDS: int = 60
    RAG_RATE_LIMIT_MAX_REQUESTS: int = 10

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
        "RAG_REQUEST_TIMEOUT_SECONDS",
        "OPENAI_TIMEOUT_SECONDS",
        "OPENAI_MAX_RETRIES",
        "DB_CONNECT_TIMEOUT_SECONDS",
        "RAG_RATE_LIMIT_WINDOW_SECONDS",
        "RAG_RATE_LIMIT_MAX_REQUESTS",
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
