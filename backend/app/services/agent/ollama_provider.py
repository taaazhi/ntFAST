"""Локальная модель через Ollama как провайдер агента.

Почему это не «дешёвый вариант», а основной для боевого применения.
ntFAST читает выписки граждан по поручению следственных органов; закон РК
№94-V ограничивает передачу таких данных третьим лицам. С локальной моделью
вопрос снимается целиком: данные не покидают машину, и анонимизация из
обязательного условия превращается в дополнительный рубеж.

Плата за это — качество. Модель на 3B слабее облачной, и полагаться на её
формулировки как на истину нельзя. Поэтому арифметика и поиск по-прежнему
живут в инструментах, а ссылки на нормы проверяются по корпусу — независимо
от того, какая модель их назвала.

Ollama говорит на своём диалекте: инструменты описываются как
`{"type": "function", "function": {...}}`, вызовы приходят в
`message.tool_calls`, результаты отправляются ролью `tool`. Здесь этот
диалект переводится в формат, на котором написана петля агента, — чтобы
`InvestigatorAgent` не знал, с кем разговаривает.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_HOST = "http://localhost:11434"
#: Локальная генерация на процессоре идёт долго; обрывать её на середине
#: рассуждения бессмысленно, поэтому таймаут щедрый.
REQUEST_TIMEOUT = 300.0


class OllamaAgentProvider:
    """Провайдер поверх `/api/chat` Ollama с поддержкой tool calling."""

    def __init__(
        self,
        model: str = "qwen2.5:3b",
        host: str = DEFAULT_HOST,
        timeout: float = REQUEST_TIMEOUT,
    ) -> None:
        self._model = model
        self._host = host.rstrip("/")
        self._timeout = timeout

    @property
    def name(self) -> str:
        return f"Ollama ({self._model})"

    def is_available(self) -> bool:
        """Поднят ли сервер и есть ли нужная модель.

        Проверяется отдельно от вызова: агент должен уметь сказать «локальная
        модель недоступна», а не падать на первом запросе.
        """
        import httpx

        try:
            response = httpx.get(f"{self._host}/api/tags", timeout=5.0)
            response.raise_for_status()
            names = {m.get("name", "") for m in response.json().get("models", [])}
        except Exception as exc:
            logger.info("Ollama недоступна: %s", exc)
            return False

        # Ollama хранит модель как «qwen2.5:3b»; в настройках её могут указать
        # без тега, и это та же модель.
        return any(
            name == self._model or name.split(":")[0] == self._model.split(":")[0]
            for name in names
        )

    def run(
        self,
        system: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        import httpx

        payload = {
            "model": self._model,
            "messages": [{"role": "system", "content": system}]
            + [self._to_ollama(m) for m in messages],
            "stream": False,
            # Нулевая температура: следственный отчёт не то место, где нужна
            # вариативность формулировок.
            "options": {"temperature": 0},
        }
        if tools:
            payload["tools"] = [self._tool_schema(t) for t in tools]

        response = httpx.post(
            f"{self._host}/api/chat", json=payload, timeout=self._timeout
        )
        response.raise_for_status()
        message = response.json().get("message", {}) or {}

        blocks: List[Dict[str, Any]] = []
        text = (message.get("content") or "").strip()
        if text:
            blocks.append({"type": "text", "text": text})

        for index, call in enumerate(message.get("tool_calls") or []):
            function = call.get("function", {}) or {}
            blocks.append({
                "type": "tool_use",
                # У Ollama своего идентификатора вызова нет — генерируем,
                # чтобы результат можно было сопоставить с запросом.
                "id": call.get("id") or f"ollama_{index}",
                "name": function.get("name", ""),
                "input": self._arguments(function.get("arguments")),
            })

        return {"content": blocks, "provider": self.name}

    # ── Перевод форматов ─────────────────────────────────────────

    @staticmethod
    def _tool_schema(tool: Dict[str, Any]) -> Dict[str, Any]:
        """Схема Anthropic → схема Ollama (совместима с OpenAI)."""
        return {
            "type": "function",
            "function": {
                "name": tool.get("name", ""),
                "description": tool.get("description", ""),
                "parameters": tool.get("input_schema", {"type": "object"}),
            },
        }

    @staticmethod
    def _arguments(raw: Any) -> Dict[str, Any]:
        """Аргументы вызова: объект или строка с JSON — встречается и то, и то."""
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
                return parsed if isinstance(parsed, dict) else {}
            except ValueError:
                logger.warning("Ollama вернула нечитаемые аргументы: %s", raw[:120])
        return {}

    @classmethod
    def _to_ollama(cls, message: Dict[str, Any]) -> Dict[str, Any]:
        """Сообщение петли → сообщение Ollama.

        Петля хранит историю в формате Anthropic: содержимое бывает строкой
        или списком блоков, а результаты инструментов приходят внутри
        пользовательского сообщения. Ollama ждёт плоский текст и отдельную
        роль `tool`.
        """
        content = message.get("content")
        role = message.get("role", "user")

        if isinstance(content, str):
            return {"role": role, "content": content}

        if not isinstance(content, list):
            return {"role": role, "content": str(content or "")}

        texts: List[str] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                texts.append(block.get("text", ""))
            elif block.get("type") == "tool_result":
                # Ollama ожидает роль `tool`, но склеивать сообщения ролей
                # здесь нельзя — возвращаем результат текстом, помечая
                # источник, чтобы модель поняла, что это ответ инструмента.
                texts.append(f"Результат инструмента: {block.get('content', '')}")
            elif block.get("type") == "tool_use":
                texts.append(
                    f"Вызов инструмента {block.get('name')} "
                    f"с параметрами {json.dumps(block.get('input') or {}, ensure_ascii=False)}"
                )
        return {"role": role, "content": "\n".join(t for t in texts if t)}


def build_ollama_provider(settings: Any = None) -> Optional[OllamaAgentProvider]:
    """Собрать локального провайдера, если он поднят и модель на месте."""
    if settings is None:
        from app.core.config import settings as default_settings

        settings = default_settings

    provider = OllamaAgentProvider(
        model=getattr(settings, "OLLAMA_MODEL", "qwen2.5:3b"),
        host=getattr(settings, "OLLAMA_HOST", DEFAULT_HOST),
    )
    if not provider.is_available():
        return None
    return provider
