import logging
import secrets
from pydantic_settings import BaseSettings
from typing import Optional

logger = logging.getLogger(__name__)

_DEFAULT_SECRET = "your-secret-key-change-in-production-09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
_MIN_SECRET_LEN = 32


def _generate_secret_key() -> str:
    """Generate a secure random SECRET_KEY (used only in DEBUG mode)."""
    key = secrets.token_hex(32)
    logger.warning(
        "[SECURITY] SECRET_KEY was not set — generated a random key. "
        "This key changes on every restart! Set SECRET_KEY in .env for persistent sessions."
    )
    return key


class Settings(BaseSettings):
    """Application settings — override via .env or environment variables."""

    # Application
    PROJECT_NAME: str = "ntFAST — Financial Analysis System for Transactions"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/financial_analysis"

    # Security
    SECRET_KEY: str = _DEFAULT_SECRET
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_DAYS: int = 30

    # CORS — local development origins (localhost + 127.0.0.1 + LAN)
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://192.168.8.208:5173",
    ]

    PORT: int = 8000

    # Email Configuration
    SMTP_SERVER: str = "smtp.mail.ru"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    USE_REAL_EMAIL: bool = False

    # Resend.com API (alternative to SMTP, works from cloud servers)
    RESEND_API_KEY: str = ""
    EMAIL_PROVIDER: str = "smtp"  # "smtp", "resend", or "brevo"

    # Brevo (Sendinblue) — 300 emails/day free, works without custom domain
    BREVO_API_KEY: str = ""

    # Mailjet — 200 emails/day free, no phone verification needed
    MAILJET_API_KEY: str = ""
    MAILJET_SECRET_KEY: str = ""

    # Mailtrap — 1000 emails/month free, GitHub signup supported
    MAILTRAP_API_TOKEN: str = ""

    # Courier — 10,000 emails/month free, GitHub signup
    COURIER_API_KEY: str = ""

    # Email verification toggle — set to false to skip verification on registration
    REQUIRE_EMAIL_VERIFICATION: bool = True

    # File Upload Configuration
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE: int = 50 * 1024 * 1024  # 50 MB
    ALLOWED_FILE_TYPES: list[str] = ["pdf", "csv", "xlsx", "xls"]

    # AI Configuration
    CLAUDE_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-sonnet-4-20250514"
    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3:8b"
    AI_PRIMARY_PROVIDER: str = "claude"
    AI_MAX_TOKENS: int = 4096

    # Celery & Redis Configuration
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    CELERY_TASK_TRACK_STARTED: bool = True
    CELERY_TASK_TIME_LIMIT: int = 30 * 60

    class Config:
        env_file = ".env"
        case_sensitive = True

    def validate_startup(self) -> None:
        """Validate critical settings on application startup.

        SECURITY: refuses to start in non-DEBUG mode if SECRET_KEY is missing,
        default, or too short. In DEBUG mode falls back to an ephemeral
        auto-generated key (logs a warning).
        """
        warnings = []

        # SECURITY: Never run with the default secret key in production
        is_default = (self.SECRET_KEY == _DEFAULT_SECRET) or not self.SECRET_KEY
        is_weak = len(self.SECRET_KEY) < _MIN_SECRET_LEN

        if is_default or is_weak:
            if self.DEBUG:
                # Dev convenience — auto-generate ephemeral key
                self.SECRET_KEY = _generate_secret_key()
                warnings.append(
                    "SECRET_KEY was default/weak — auto-generated ephemeral key (DEBUG mode). "
                    "Set SECRET_KEY in .env for persistent JWT sessions: "
                    "python -c \"import secrets; print(secrets.token_hex(32))\""
                )
            else:
                # Production — fail fast, do not silently weaken security
                raise RuntimeError(
                    "[SECURITY] SECRET_KEY is missing, default, or shorter than "
                    f"{_MIN_SECRET_LEN} chars. Set a strong SECRET_KEY in .env before starting "
                    "the application. Generate one with: "
                    "python -c \"import secrets; print(secrets.token_hex(32))\""
                )

        if not self.SMTP_USERNAME and self.USE_REAL_EMAIL:
            warnings.append(
                "USE_REAL_EMAIL=true but SMTP_USERNAME is empty. "
                "Emails will fail to send."
            )

        if "sqlite" not in self.DATABASE_URL and "localhost" not in self.DATABASE_URL:
            logger.info(f"Database: remote ({self.DATABASE_URL.split('@')[-1].split('/')[0]})")

        for w in warnings:
            logger.warning(f"[CONFIG] {w}")


settings = Settings()
