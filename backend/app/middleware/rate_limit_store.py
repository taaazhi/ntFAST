"""Счётчик обращений: общий для процессов, если есть Redis.

Зачем понадобилось выносить. Счётчик жил в памяти процесса, а бэкенд
запускается несколькими воркерами. Каждый вёл свой счёт, и «5 попыток входа
в минуту» на четырёх воркерах означало двадцать: подбирающий пароль просто
попадал в разные процессы, ничего для этого не делая. Заявленный предел и
действующий расходились в разы, и по журналу это не видно — каждый воркер
честно докладывает о своих пяти.

Redis в проекте уже есть — на нём работает очередь Celery. Отдельная база
(`/1`) держит счётчики: смешивать их с очередью задач незачем, а очистку
по времени Redis делает сам.

Что происходит, если Redis недоступен. Ограничение переходит в память
процесса и продолжает работать, только слабее. Это осознанный выбор:
альтернатива — либо пускать всех без ограничений, либо не пускать никого.
Первое отдаёт форму входа на перебор, второе кладёт систему целиком из-за
вспомогательной службы. Ослабленная защита лучше обеих крайностей, но о
переходе пишется предупреждение — молчаливая деградация защиты хуже самой
деградации.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

#: Счётчики лежат в отдельной базе Redis, чтобы не мешаться с очередью Celery.
COUNTER_DB = 1

#: Сколько ждать Redis, прежде чем считать его недоступным.
#:
#: Полсекунды, а не «сколько получится»: на этом пути стоит форма входа.
#: Redis, который не отвечает, не должен подвешивать вход — лучше перейти в
#: память процесса и продолжить работу. Без явного предела клиент ждёт
#: десятки секунд, и зависшая вспомогательная служба выглядит как упавшая
#: система.
CONNECT_TIMEOUT = 0.5


class InMemoryStore:
    """Скользящее окно в памяти процесса.

    Годится для одного воркера и для тестов. При нескольких процессах даёт
    предел, умноженный на их число, — об этом сказано в модуле выше.
    """

    def __init__(self) -> None:
        self._hits: Dict[str, List[float]] = defaultdict(list)
        self._last_cleanup = time.time()

    async def hit(self, key: str, limit: int, window: int) -> Tuple[bool, int]:
        now = time.time()
        fresh = [ts for ts in self._hits[key] if now - ts < window]
        self._hits[key] = fresh

        if len(fresh) >= limit:
            return False, max(int(window - (now - fresh[0])), 1)

        fresh.append(now)
        self._cleanup(now, window)
        return True, 0

    def _cleanup(self, now: float, window: int) -> None:
        """Раз в минуту выбрасывать ключи, по которым давно не обращались."""
        if now - self._last_cleanup < 60:
            return
        self._last_cleanup = now
        for key in [k for k, v in self._hits.items() if not v or now - v[-1] > window]:
            del self._hits[key]


class RedisStore:
    """Скользящее окно в Redis — общее для всех воркеров.

    Окно хранится упорядоченным множеством: метка времени и как вес, и как
    значение. Старые метки выбрасываются перед подсчётом, поэтому окно
    действительно скользящее, а не «раз в минуту обнулилось».

    Все команды идут одним конвейером: между проверкой и записью не должно
    быть промежутка, в который поместится ещё один запрос.
    """

    def __init__(self, url: str) -> None:
        self._url = self._with_counter_db(url)
        self._client = None

    @staticmethod
    def _with_counter_db(url: str) -> str:
        """Подменить базу в URL на ту, где живут счётчики.

        Параметр `db=` для `from_url` не помогает: путь в URL сильнее, и
        «redis://host:6379/0» отправлял счётчики в базу очереди Celery —
        ровно туда, куда их класть не хотелось. Проверено: ключи «rl:*»
        оказались в нулевой базе рядом с задачами.

        Разбирается через urlsplit, а не отрезанием хвоста по слэшу: в
        «redis://host:6379» пути нет, и наивное отрезание съедало имя хоста
        вместе со слэшами схемы.
        """
        from urllib.parse import urlsplit, urlunsplit

        parts = urlsplit(url)
        return urlunsplit(parts._replace(path=f"/{COUNTER_DB}"))

    async def _connect(self):
        if self._client is None:
            import redis.asyncio as redis

            self._client = redis.from_url(
                self._url,
                socket_connect_timeout=CONNECT_TIMEOUT,
                socket_timeout=CONNECT_TIMEOUT,
            )
        return self._client

    async def hit(self, key: str, limit: int, window: int) -> Tuple[bool, int]:
        client = await self._connect()
        now = time.time()

        pipe = client.pipeline()
        pipe.zremrangebyscore(key, 0, now - window)
        pipe.zcard(key)
        pipe.zrange(key, 0, 0, withscores=True)
        _, used, oldest = await pipe.execute()

        if used >= limit:
            first = oldest[0][1] if oldest else now
            return False, max(int(window - (now - first)), 1)

        # Значение уникально по времени: две попытки в одну миллисекунду
        # иначе слились бы в одну запись множества.
        pipe = client.pipeline()
        pipe.zadd(key, {f"{now:.6f}": now})
        # Ключ живёт ровно окно: чистить его отдельно не нужно.
        pipe.expire(key, window)
        await pipe.execute()
        return True, 0


class RateLimitStore:
    """Redis, если он отвечает; память — если нет."""

    def __init__(self, redis_url: Optional[str] = None) -> None:
        self._memory = InMemoryStore()
        self._redis = RedisStore(redis_url) if redis_url else None
        self._warned = False

    async def hit(self, key: str, limit: int, window: int) -> Tuple[bool, int]:
        if self._redis is not None:
            try:
                return await self._redis.hit(key, limit, window)
            except Exception as exc:  # noqa: BLE001 — падение Redis не должно ронять вход
                if not self._warned:
                    logger.warning(
                        "Redis недоступен (%s). Ограничение частоты перешло в память "
                        "процесса: при нескольких воркерах предел выше заявленного.",
                        exc,
                    )
                    self._warned = True

        return await self._memory.hit(key, limit, window)
