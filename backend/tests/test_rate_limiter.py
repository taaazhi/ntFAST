"""Проверки ограничения частоты обращений.

Главное здесь — не то, что предел срабатывает, а то, что его нельзя обойти.
Ограничение, снимаемое одним заголовком, хуже отсутствующего: оно создаёт
уверенность, что форма входа защищена от перебора.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.middleware.rate_limit_store import InMemoryStore, RateLimitStore  # noqa: E402
from app.middleware.rate_limiter import RateLimiterMiddleware  # noqa: E402


class _FakeClient:
    def __init__(self, host: str) -> None:
        self.host = host


class _FakeRequest:
    """Ровно то, что читает middleware: адрес и заголовки."""

    def __init__(self, host: str = "10.0.0.1", headers: dict | None = None) -> None:
        self.client = _FakeClient(host)
        self.headers = headers or {}


def _address(request: _FakeRequest) -> str:
    return RateLimiterMiddleware._client_address(request)


# ── Подделка адреса ──────────────────────────────────────────────────

def test_forwarded_header_is_ignored_by_default(monkeypatch):
    """X-Forwarded-For не должен приниматься на слово.

    Заголовок ставит клиент. Пока ему верят, подбирающий пароль шлёт новое
    значение с каждой попыткой и никогда не упирается в предел — счётчик
    считает разные адреса.
    """
    from app.core import config

    monkeypatch.setattr(config.settings, "TRUST_PROXY_HEADERS", False, raising=False)

    spoofed = _FakeRequest(host="10.0.0.1", headers={"X-Forwarded-For": "1.2.3.4"})
    assert _address(spoofed) == "10.0.0.1"


def test_real_ip_header_is_ignored_by_default(monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "TRUST_PROXY_HEADERS", False, raising=False)

    spoofed = _FakeRequest(host="10.0.0.1", headers={"X-Real-IP": "1.2.3.4"})
    assert _address(spoofed) == "10.0.0.1"


def test_forwarded_header_is_used_behind_a_proxy(monkeypatch):
    """За прокси заголовок — единственный способ узнать клиента.

    Без него все запросы выглядят приходящими от самого прокси, и предел
    срабатывает сразу для всех разом.
    """
    from app.core import config

    monkeypatch.setattr(config.settings, "TRUST_PROXY_HEADERS", True, raising=False)

    request = _FakeRequest(host="172.17.0.2", headers={"X-Forwarded-For": "203.0.113.7"})
    assert _address(request) == "203.0.113.7"


def test_first_address_in_the_chain_wins(monkeypatch):
    """В цепочке прокси исходный клиент стоит первым."""
    from app.core import config

    monkeypatch.setattr(config.settings, "TRUST_PROXY_HEADERS", True, raising=False)

    request = _FakeRequest(headers={"X-Forwarded-For": "203.0.113.7, 10.0.0.5, 10.0.0.6"})
    assert _address(request) == "203.0.113.7"


def test_missing_client_does_not_crash():
    """Запрос без адреса не должен ронять обработку."""
    request = _FakeRequest()
    request.client = None
    assert _address(request) == "unknown"


# ── Скользящее окно ──────────────────────────────────────────────────

def test_limit_allows_up_to_the_threshold():
    store = InMemoryStore()

    for attempt in range(5):
        allowed, _ = asyncio.run(store.hit("rl:10.0.0.1:/api/auth/login", 5, 60))
        assert allowed, f"попытка {attempt + 1} из 5 должна проходить"


def test_limit_blocks_beyond_the_threshold():
    store = InMemoryStore()
    for _ in range(5):
        asyncio.run(store.hit("rl:10.0.0.1:/api/auth/login", 5, 60))

    allowed, retry_after = asyncio.run(store.hit("rl:10.0.0.1:/api/auth/login", 5, 60))
    assert not allowed
    assert retry_after > 0, "клиенту надо сказать, когда возвращаться"


def test_counters_are_separate_per_client():
    """Перебор с одного адреса не должен блокировать остальных."""
    store = InMemoryStore()
    for _ in range(5):
        asyncio.run(store.hit("rl:10.0.0.1:/api/auth/login", 5, 60))

    allowed, _ = asyncio.run(store.hit("rl:10.0.0.2:/api/auth/login", 5, 60))
    assert allowed


def test_counters_are_separate_per_path():
    """Исчерпанный вход не должен закрывать восстановление пароля."""
    store = InMemoryStore()
    for _ in range(5):
        asyncio.run(store.hit("rl:10.0.0.1:/api/auth/login", 5, 60))

    allowed, _ = asyncio.run(store.hit("rl:10.0.0.1:/api/auth/reset-password", 5, 300))
    assert allowed


def test_window_slides():
    """Окно скользит, а не обнуляется целиком.

    Попытки, вышедшие за окно, перестают учитываться — иначе после пяти
    неудач вход был бы закрыт навсегда.
    """
    store = InMemoryStore()
    for _ in range(3):
        asyncio.run(store.hit("rl:10.0.0.1:/api/auth/login", 3, 60))

    blocked, _ = asyncio.run(store.hit("rl:10.0.0.1:/api/auth/login", 3, 60))
    assert not blocked

    # Сдвигаем сохранённые метки в прошлое — то же, что подождать минуту.
    store._hits["rl:10.0.0.1:/api/auth/login"] = [
        ts - 61 for ts in store._hits["rl:10.0.0.1:/api/auth/login"]
    ]
    allowed, _ = asyncio.run(store.hit("rl:10.0.0.1:/api/auth/login", 3, 60))
    assert allowed


# ── Деградация ───────────────────────────────────────────────────────

def test_broken_redis_falls_back_to_memory(caplog):
    """Недоступный Redis ослабляет защиту, но не снимает её.

    Пускать всех без счёта — отдать форму входа на перебор; не пускать
    никого — положить систему из-за вспомогательной службы.
    """
    store = RateLimitStore(redis_url="redis://127.0.0.1:1/0")

    results = [asyncio.run(store.hit("rl:x:/api/auth/login", 2, 60)) for _ in range(3)]

    assert results[0][0] and results[1][0], "первые две попытки проходят"
    assert not results[2][0], "третья упирается в предел уже в памяти"


def test_fallback_is_announced(caplog):
    """О переходе в память пишется предупреждение.

    Молчаливая деградация защиты хуже самой деградации: никто не узнает,
    что предел перестал быть общим.
    """
    import logging

    store = RateLimitStore(redis_url="redis://127.0.0.1:1/0")
    with caplog.at_level(logging.WARNING):
        asyncio.run(store.hit("rl:y:/api/auth/login", 2, 60))

    assert any("Redis" in record.message for record in caplog.records)


def test_warning_is_not_repeated_every_request(caplog):
    """Предупреждение пишется один раз, а не на каждый запрос.

    Иначе журнал заполнится одной строкой и перестанет читаться.
    """
    import logging

    store = RateLimitStore(redis_url="redis://127.0.0.1:1/0")
    with caplog.at_level(logging.WARNING):
        for _ in range(5):
            asyncio.run(store.hit("rl:z:/api/auth/login", 10, 60))

    redis_warnings = [r for r in caplog.records if "Redis" in r.message]
    assert len(redis_warnings) == 1


# ── Куда пишутся счётчики ────────────────────────────────────────────

def test_counters_go_to_a_separate_redis_database():
    """Счётчики не должны лежать в базе очереди Celery.

    Параметр `db=` для from_url не помогает: путь в URL сильнее. Проверено
    вживую — ключи «rl:*» оказались в нулевой базе рядом с задачами.
    """
    from app.middleware.rate_limit_store import COUNTER_DB, RedisStore

    assert RedisStore._with_counter_db("redis://localhost:6379/0") \
        == f"redis://localhost:6379/{COUNTER_DB}"


def test_url_without_a_path_keeps_its_host():
    """«redis://host:6379» — законная запись, и хост из неё терять нельзя.

    Наивное отрезание хвоста по слэшу превращало её в «redis://1»: слэши
    схемы принимались за разделитель пути.
    """
    from app.middleware.rate_limit_store import RedisStore

    assert RedisStore._with_counter_db("redis://localhost:6379") \
        == "redis://localhost:6379/1"


def test_credentials_and_tls_survive_the_rewrite():
    from app.middleware.rate_limit_store import RedisStore

    assert RedisStore._with_counter_db("rediss://user:pw@host:6380/3") \
        == "rediss://user:pw@host:6380/1"
