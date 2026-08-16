import logging
import logging.config
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import traceback

# Configure logging for the entire app
logging.config.dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "stream": "ext://sys.stdout",
        },
    },
    "root": {
        "level": "INFO",
        "handlers": ["console"],
    },
    "loggers": {
        "app": {"level": "DEBUG"},
        "uvicorn": {"level": "INFO"},
    },
})
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.config import settings
from app.core.database import init_db
from app.api import auth, subjects, analyses, transactions, email_verification, users, websocket, bank_analysis, notifications
from app.middleware.activity_tracker import ActivityTrackerMiddleware
from app.middleware.rate_limiter import RateLimiterMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware

# Import models to ensure they are registered with SQLAlchemy
from app.models.user import User
from app.models.login_history import LoginHistory
from app.models.notification import Notification  # noqa: F401 — registers table

logger = logging.getLogger(__name__)


class ClientHintsMiddleware(BaseHTTPMiddleware):
    """
    Middleware to request User-Agent Client Hints from browsers
    This enables accurate Windows 11 detection and detailed device info

    CRITICAL: Explicitly bypasses WebSocket connections in __call__
    to prevent BaseHTTPMiddleware from interfering with WS upgrade.
    """
    async def __call__(self, scope, receive, send):
        # Bypass non-HTTP requests (WebSocket, lifespan)
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        await super().__call__(scope, receive, send)

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["Accept-CH"] = "Sec-CH-UA, Sec-CH-UA-Platform, Sec-CH-UA-Platform-Version, Sec-CH-UA-Mobile, Sec-CH-UA-Model, Sec-CH-UA-Arch, Sec-CH-UA-Bitness, Sec-CH-UA-Full-Version-List"
        response.headers["Critical-CH"] = "Sec-CH-UA-Platform-Version"
        return response


# Create FastAPI application
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="ntFAST — Financial Analysis System for Transactions"
)

# Global exception handlers — ensures CORS headers are always present on error responses
# Without these, unhandled exceptions bypass CORSMiddleware and browser sees "CORS error"
#
# CRITICAL: We manually add CORS headers to every error response because when
# BaseHTTPMiddleware subclasses throw exceptions, they bypass CORSMiddleware.
# This means the browser sees "CORS error" instead of the real error message.
def _cors_headers(request: Request) -> dict:
    """Build CORS headers for error responses so they pass browser CORS checks."""
    origin = request.headers.get("origin", "")
    if origin in settings.BACKEND_CORS_ORIGINS:
        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        }
    return {}

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # In DEBUG mode log the full traceback (helps local debugging).
    # In production log only the exception type + message to avoid leaking
    # sensitive paths/queries/credentials into log aggregators.
    if settings.DEBUG:
        logger.error(
            f"Unhandled exception on {request.method} {request.url.path}: {exc}",
            exc_info=True,
        )
    else:
        logger.error(
            f"Unhandled {type(exc).__name__} on {request.method} {request.url.path}"
        )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
        headers=_cors_headers(request),
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": str(exc)},
        headers=_cors_headers(request),
    )

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=_cors_headers(request),
    )

# Middleware order: last added = outermost (runs first on request)
# CORS must be outermost so it handles OPTIONS preflight before other middleware

# Activity tracking (last_activity updates) — innermost
app.add_middleware(ActivityTrackerMiddleware)

# Client Hints for accurate device detection
app.add_middleware(ClientHintsMiddleware)

# Rate limiting on auth endpoints
app.add_middleware(RateLimiterMiddleware)

# Security headers (CSP, X-Frame-Options, etc.)
app.add_middleware(SecurityHeadersMiddleware)

# CORS — outermost (added last = runs first, handles OPTIONS preflight)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "Sec-CH-UA", "Sec-CH-UA-Platform", "Sec-CH-UA-Platform-Version", "Sec-CH-UA-Mobile", "Sec-CH-UA-Model", "Sec-CH-UA-Arch", "Sec-CH-UA-Bitness"],
    expose_headers=["Accept-CH", "Critical-CH"],
)

# Include routers
app.include_router(auth.router, prefix=f"{settings.API_PREFIX}/auth", tags=["Authentication"])
app.include_router(email_verification.router, prefix=f"{settings.API_PREFIX}/email-verification", tags=["Email Verification"])
app.include_router(users.router, prefix=f"{settings.API_PREFIX}/users", tags=["Users Management"])
app.include_router(subjects.router, prefix=f"{settings.API_PREFIX}/subjects", tags=["Subjects"])
app.include_router(analyses.router, prefix=f"{settings.API_PREFIX}/analyses", tags=["Analyses"])
app.include_router(transactions.router, prefix=f"{settings.API_PREFIX}/transactions", tags=["Transactions"])
app.include_router(websocket.router, tags=["WebSocket"])
app.include_router(bank_analysis.router, prefix=f"{settings.API_PREFIX}/bank", tags=["Bank Statement Analysis"])
app.include_router(notifications.router, prefix=f"{settings.API_PREFIX}/notifications", tags=["Notifications"])


@app.on_event("startup")
async def startup_event():
    """Initialize database and validate configuration on startup"""
    settings.validate_startup()
    init_db()

    # CRITICAL: Reset all users to offline on startup (clean state after restart)
    # Without this, users who were online when the server crashed stay "online" forever
    from app.api.websocket import reset_all_online_statuses, start_cleanup_task
    reset_all_online_statuses()

    # CRITICAL: Start auto-offline background task immediately
    # Without this, the task only starts when someone connects via WebSocket
    # and stale online statuses are never cleaned up
    start_cleanup_task()

    _warn_if_proxy_headers_are_trusted_blindly()

    logger.info(f"ntFAST v{settings.VERSION} started")


def _warn_if_proxy_headers_are_trusted_blindly() -> None:
    """Сказать вслух, если ограничение частоты обходится заголовком.

    uvicorn по умолчанию запускается с proxy_headers=True и доверяет
    X-Forwarded-For всем, кто пришёл с localhost. Он переписывает адрес
    клиента ещё до того, как запрос попадёт в приложение, поэтому наша
    настройка TRUST_PROXY_HEADERS тут уже ничего не решает.

    Проверено вживую: после пяти отказов вход отдавал 429, а те же запросы
    с подставным «X-Forwarded-For: 9.9.9.1» проходили снова — в Redis
    появлялись отдельные счётчики на каждый выдуманный адрес.

    За обратным прокси такое поведение правильно. При прямом доступе к порту
    приложения оно снимает защиту от перебора паролей, поэтому здесь об этом
    предупреждают, а не молчат.
    """
    import os

    allowed = os.environ.get("FORWARDED_ALLOW_IPS", "127.0.0.1")
    if not getattr(settings, "TRUST_PROXY_HEADERS", False) and allowed:
        logger.warning(
            "Адрес клиента может быть подменён заголовком X-Forwarded-For: "
            "uvicorn доверяет ему для %s. Ограничение частоты обходится "
            "подстановкой нового адреса в каждый запрос. Если приложение не "
            "стоит за обратным прокси, запускайте его с "
            'FORWARDED_ALLOW_IPS="" (или --forwarded-allow-ips=""); если '
            "стоит — включите TRUST_PROXY_HEADERS=true и закройте прямой "
            "доступ к порту.",
            allowed,
        )


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "ntFAST — Financial Analysis System for Transactions",
        "version": settings.VERSION,
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint with system status.

    Uses parameterless SQLAlchemy literal `select(1)` to avoid raw SQL text
    and reduce false-positive matches in security scanners.
    """
    from sqlalchemy import select
    from app.core.database import SessionLocal

    db_ok = False
    db = None
    try:
        db = SessionLocal()
        db.execute(select(1))
        db_ok = True
    except Exception:
        logger.exception("health_check: database probe failed")
    finally:
        if db is not None:
            try:
                db.close()
            except Exception:
                pass

    return {
        "status": "healthy" if db_ok else "degraded",
        "version": settings.VERSION,
        "database": "connected" if db_ok else "error",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
