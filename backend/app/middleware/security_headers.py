"""
Security headers middleware — CSP, XSS protection, etc.
"""
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings


# In dev (Vite HMR), inline scripts and eval are required for hot module reload.
# In prod we drop these to maximize XSS resistance.
_IS_DEV = getattr(settings, "DEBUG", False)


def _build_csp() -> str:
    if _IS_DEV:
        script_src = "script-src 'self' 'unsafe-inline' 'unsafe-eval'"
    else:
        # Strict CSP — no unsafe-inline / no unsafe-eval. XSS payloads can't run inline.
        script_src = "script-src 'self'"
    return (
        "default-src 'self'; "
        f"{script_src}; "
        # Tailwind/Framer Motion inject inline styles → keep 'unsafe-inline' for style-src
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "font-src 'self' data:; "
        "connect-src 'self' ws: wss:; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none'"
    )


_CSP_HEADER = _build_csp()


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all HTTP responses."""

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        await super().__call__(scope, receive, send)

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Swagger UI / ReDoc need inline scripts + CDN — give them a relaxed CSP
        path = request.url.path
        is_docs = path in ("/docs", "/redoc", "/openapi.json") or path.startswith("/docs")
        if is_docs:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "img-src 'self' data: https://fastapi.tiangolo.com; "
                "font-src 'self' data:; "
                "connect-src 'self'"
            )
        else:
            response.headers["Content-Security-Policy"] = _CSP_HEADER

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # Referrer policy — don't leak URLs
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions policy — disable unused browser features
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )

        return response
