"""Адаптер локальной модели: перевод между диалектами Ollama и петли агента.

Проверяется без сети. Ollama описывает инструменты по-своему
(`{"type": "function", ...}`), возвращает вызовы в `message.tool_calls` и
не выдаёт идентификатор вызова. Ошибка в переводе не проявится как падение:
петля просто не увидит ни одного инструмента и решит, что модель ответила
текстом, — а модель при этом честно просила данные.

Отдельно закреплён выбор провайдера. Для настоящих выписок предпочтителен
локальный режим — данные не покидают машину, и требование закона №94-V
выполняется отсутствием передачи, а не обещанием её защитить.
"""
import json

import pytest

from app.services.agent.ollama_provider import OllamaAgentProvider
from app.services.agent.tools import TOOL_SCHEMAS


@pytest.fixture
def provider():
    return OllamaAgentProvider(model="qwen2.5:3b")


# ── Схемы инструментов ───────────────────────────────────────────

def test_tool_schema_is_translated_for_ollama(provider):
    source = TOOL_SCHEMAS[0]
    translated = provider._tool_schema(source)

    assert translated["type"] == "function"
    assert translated["function"]["name"] == source["name"]
    assert translated["function"]["parameters"] == source["input_schema"]


def test_every_tool_survives_translation(provider):
    """Потерянный инструмент модель просто не сможет вызвать, и это будет
    выглядеть как её неспособность, а не как наша ошибка."""
    translated = [provider._tool_schema(t) for t in TOOL_SCHEMAS]

    assert len(translated) == len(TOOL_SCHEMAS)
    assert all(t["function"]["name"] for t in translated)


# ── Аргументы вызова ─────────────────────────────────────────────

def test_arguments_accept_an_object(provider):
    assert provider._arguments({"direction": "income"}) == {"direction": "income"}


def test_arguments_accept_a_json_string(provider):
    """Ollama возвращает аргументы то объектом, то строкой — зависит от модели."""
    assert provider._arguments('{"limit": 5}') == {"limit": 5}


def test_broken_arguments_do_not_crash_the_run(provider):
    """Мелкая модель иногда выдаёт незакрытый JSON. Инструмент вызовется без
    параметров и вернёт что-то осмысленное — это лучше, чем падение разбора."""
    assert provider._arguments("{не json") == {}


def test_non_object_arguments_are_ignored(provider):
    assert provider._arguments('"строка"') == {}


# ── История сообщений ────────────────────────────────────────────

def test_plain_text_message_passes_through(provider):
    result = provider._to_ollama({"role": "user", "content": "Сколько расходов?"})

    assert result == {"role": "user", "content": "Сколько расходов?"}


def test_tool_result_becomes_readable_text(provider):
    """Петля хранит историю в формате Anthropic, где результат инструмента —
    блок внутри сообщения пользователя. Ollama такого не понимает."""
    message = {
        "role": "user",
        "content": [{
            "type": "tool_result",
            "tool_use_id": "ollama_0",
            "content": '{"found": 3}',
        }],
    }

    result = provider._to_ollama(message)

    assert "Результат инструмента" in result["content"]
    assert '{"found": 3}' in result["content"]


def test_assistant_tool_call_is_described_in_history(provider):
    """Без этого модель не помнит, что уже спрашивала, и зациклится."""
    message = {
        "role": "assistant",
        "content": [{
            "type": "tool_use", "id": "ollama_0",
            "name": "query_transactions", "input": {"direction": "expense"},
        }],
    }

    result = provider._to_ollama(message)

    assert "query_transactions" in result["content"]
    assert "expense" in result["content"]


# ── Разбор ответа ────────────────────────────────────────────────

class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_text_answer_is_returned_as_a_block(provider, monkeypatch):
    import httpx

    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResponse(
        {"message": {"content": "Расходов три."}}
    ))

    result = provider.run(system="s", messages=[{"role": "user", "content": "?"}])

    assert result["content"] == [{"type": "text", "text": "Расходов три."}]
    assert "qwen2.5:3b" in result["provider"]


def test_tool_calls_are_given_ids(provider, monkeypatch):
    """У Ollama идентификатора вызова нет, а петле он нужен, чтобы вернуть
    результат именно на этот запрос."""
    import httpx

    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResponse({
        "message": {
            "content": "",
            "tool_calls": [
                {"function": {"name": "get_period_totals", "arguments": {}}},
                {"function": {"name": "query_transactions", "arguments": '{"limit": 2}'}},
            ],
        }
    }))

    blocks = provider.run(system="s", messages=[], tools=TOOL_SCHEMAS)["content"]

    assert [b["type"] for b in blocks] == ["tool_use", "tool_use"]
    assert len({b["id"] for b in blocks}) == 2
    assert blocks[1]["input"] == {"limit": 2}


def test_tools_are_sent_in_ollama_dialect(provider, monkeypatch):
    import httpx

    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured.update(json or {})
        return FakeResponse({"message": {"content": "ok"}})

    monkeypatch.setattr(httpx, "post", fake_post)
    provider.run(system="s", messages=[], tools=TOOL_SCHEMAS)

    assert captured["tools"][0]["type"] == "function"
    assert captured["options"]["temperature"] == 0
    assert captured["messages"][0]["role"] == "system"


# ── Доступность и выбор провайдера ───────────────────────────────

def test_unavailable_server_is_reported_not_raised(provider, monkeypatch):
    import httpx

    def boom(*a, **k):
        raise httpx.ConnectError("сервер не запущен")

    monkeypatch.setattr(httpx, "get", boom)

    assert provider.is_available() is False


def test_model_absence_is_detected(provider, monkeypatch):
    """Сервер поднят, но модель не скачана — самая частая ситуация после
    установки."""
    import httpx

    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResponse({"models": []}))

    assert provider.is_available() is False


def test_model_matches_without_the_tag(provider, monkeypatch):
    import httpx

    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResponse(
        {"models": [{"name": "qwen2.5:3b-instruct-q4_K_M"}]}
    ))

    assert provider.is_available() is True


class _Settings:
    def __init__(self, preference="auto", key="", enabled=True):
        self.AI_ENRICHMENT_ENABLED = enabled
        self.AGENT_PROVIDER = preference
        self.CLAUDE_API_KEY = key
        self.CLAUDE_REASONING_MODEL = "claude-sonnet-5"
        self.OLLAMA_MODEL = "qwen2.5:3b"
        self.OLLAMA_HOST = "http://localhost:11434"
        self.AI_MAX_TOKENS = 1024


def test_local_only_never_falls_back_to_the_cloud(monkeypatch):
    """Режим `local` — гарантия, а не предпочтение: если локальной модели нет,
    правильный ответ «агент недоступен», а не тихая отправка выписки наружу."""
    from app.services.agent import provider as provider_module

    monkeypatch.setattr(
        provider_module, "build_agent_provider",
        provider_module.build_agent_provider,
    )
    import app.services.agent.ollama_provider as ollama_module

    monkeypatch.setattr(ollama_module, "build_ollama_provider", lambda s: None)

    result = provider_module.build_agent_provider(
        _Settings(preference="local", key="sk-test")
    )

    assert result is None


def test_local_agent_runs_without_the_cloud_consent_flag(monkeypatch):
    """Локальный агент не зависит от AI_ENRICHMENT_ENABLED. Флаг — про право
    отправить данные третьему лицу; Ollama наружу ничего не шлёт, поэтому
    запускается и при выключенном флаге. Иначе следователь видит 503 там, где
    никакой передачи ПД нет."""
    from app.services.agent import provider as provider_module
    import app.services.agent.ollama_provider as ollama_module

    class _FakeLocal:
        name = "qwen2.5:3b (fake)"

    fake = _FakeLocal()
    monkeypatch.setattr(ollama_module, "build_ollama_provider", lambda s: fake)

    result = provider_module.build_agent_provider(
        _Settings(preference="auto", enabled=False)
    )

    assert result is fake


def test_cloud_still_needs_consent_when_local_is_down(monkeypatch):
    """Расцепление локального пути не должно приоткрыть облако: в auto без
    локальной модели и без согласия агент молчит, даже когда ключ задан."""
    from app.services.agent import provider as provider_module
    import app.services.agent.ollama_provider as ollama_module

    monkeypatch.setattr(ollama_module, "build_ollama_provider", lambda s: None)

    result = provider_module.build_agent_provider(
        _Settings(preference="auto", key="sk-test", enabled=False)
    )

    assert result is None
