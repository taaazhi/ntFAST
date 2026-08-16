"""Ограничение частоты обращений к чувствительным эндпоинтам.

Защищает форму входа от перебора паролей, регистрацию и восстановление
доступа — от массовой рассылки, загрузку файлов — от исчерпания диска.

Два решения, каждое стоило дефекта.

**Адресу клиента верят только тогда, когда есть кому.** Раньше заголовок
`X-Forwarded-For` принимался как есть, а его ставит сам клиент. Достаточно
было слать новое значение с каждой попыткой, чтобы ограничение перестало
существовать: каждый запрос выглядел приходящим от нового адреса, счётчик
никогда не набирался. Теперь заголовки читаются, только если
`TRUST_PROXY_HEADERS=true` — то есть когда перед приложением стоит прокси,
который их перезаписывает.

**Счёт общий для воркеров.** Он лежит в Redis, а не в памяти процесса;
почему это важно и что происходит при недоступности Redis — в
`rate_limit_store.py`.
"""
from __future__ import annotations

import logging

from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import settings

from .rate_limit_store import RateLimitStore

logger = logging.getLogger(__name__)

#: Путь → (сколько обращений, за сколько секунд).
RATE_LIMITS = {
    "/api/auth/login": (5, 60),
    "/api/auth/register": (3, 60),
    "/api/auth/forgot-password": (3, 300),
    "/api/auth/reset-password": (5, 300),
    "/api/analyses/upload": (10, 600),
}


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Скользящее окно по адресу клиента и пути."""

    def __init__(self, app, store: RateLimitStore | None = None):
        super().__init__(app)
        self._store = store or RateLimitStore(
            getattr(settings, "RATE_LIMIT_REDIS_URL", "") or None
        )

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        await super().__call__(scope, receive, send)

    async def dispatch(self, request: Request, call_next):
        if request.method != "POST":
            return await call_next(request)

        path = request.url.path
        limit_config = RATE_LIMITS.get(path) or RATE_LIMITS.get(path.rstrip("/"))
        if not limit_config:
            return await call_next(request)

        max_requests, window_seconds = limit_config
        client = self._client_address(request)
        allowed, retry_after = await self._store.hit(
            f"rl:{client}:{path}", max_requests, window_seconds
        )

        if not allowed:
            logger.warning(
                "Превышена частота обращений: %s на %s (предел %s за %s с)",
                client, path, max_requests, window_seconds,
            )
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Too many requests. Please try again later.",
                    "retry_after": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)

    @staticmethod
    def _client_address(request: Request) -> str:
        """Адрес, по которому ведётся счёт.

        Заголовкам от прокси верим только по явной настройке: их ставит
        клиент, и пока им верят на слово, ограничение обходится подстановкой
        нового значения в каждый запрос.
        """
        if getattr(settings, "TRUST_PROXY_HEADERS", False):
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                # Первый адрес в цепочке — исходный клиент, остальные добавили
                # промежуточные прокси.
                return forwarded.split(",")[0].strip()

            real_ip = request.headers.get("X-Real-IP")
            if real_ip:
                return real_ip.strip()

        return request.client.host if request.client else "unknown"
