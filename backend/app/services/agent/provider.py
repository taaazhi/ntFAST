"""Провайдер модели для следственного агента.

Отдельно от `services/ai/`: тем провайдерам нужен один ответ на один запрос,
а агенту — цикл с инструментами, где ответ модели может быть не текстом, а
требованием вызвать функцию. Натягивать одно на другое значило бы усложнить
оба.

Клиент синхронный намеренно. Петля агента последовательна по существу —
следующий вопрос модели зависит от результата предыдущего инструмента, —
и асинхронность здесь ничего не ускоряет, зато заставляет вызывающий код
подстраиваться. FastAPI выполнит синхронный обработчик в пуле потоков.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ClaudeAgentProvider:
    """Anthropic Messages API с поддержкой tool use.

    Возвращает ответ в том виде, в каком его ждёт петля: список блоков
    `text` и `tool_use` плюс имя провайдера.
    """

    def __init__(self, api_key: str, model: str, max_tokens: int = 4096) -> None:
        if not api_key:
            raise ValueError("не задан CLAUDE_API_KEY")

        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    @property
    def name(self) -> str:
        return f"Claude ({self._model})"

    def run(
        self,
        system: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system,
            messages=messages,
            tools=tools or [],
        )

        blocks: List[Dict[str, Any]] = []
        for block in response.content:
            if block.type == "text":
                blocks.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                blocks.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })

        return {
            "content": blocks,
            "provider": self.name,
            # Стоимость запроса складывается из этих чисел — они попадают в
            # отчёт, чтобы расход на анализ был виден, а не угадывался.
            "usage": {
                "input_tokens": getattr(response.usage, "input_tokens", 0),
                "output_tokens": getattr(response.usage, "output_tokens", 0),
            },
        }


def build_agent_provider(settings: Any = None) -> Optional[Any]:
    """Собрать провайдера из настроек — или ничего, если его нет.

    Порядок выбора задаётся `AGENT_PROVIDER`:

    * `local` — только Ollama. Данные не покидают машину, и для работы с
      настоящими выписками это предпочтительный режим: закон РК №94-V
      ограничивает передачу персональных данных третьим лицам, а здесь
      передачи нет вовсе.
    * `cloud` — только Claude. Качество выше, но выписка уходит наружу,
      поэтому включается осознанно и с обязательной анонимизацией.
    * `auto` (по умолчанию) — сначала локальная модель, при её отсутствии
      облачная. Так система сама предпочитает вариант, при котором данные
      остаются внутри периметра.

    None означает «модели нет» — рабочее состояние, а не сбой: анализ
    выписки от языковой модели не зависит.
    """
    if settings is None:
        from app.core.config import settings as default_settings

        settings = default_settings

    if not getattr(settings, "AI_ENRICHMENT_ENABLED", False):
        logger.info("Агент выключен: AI_ENRICHMENT_ENABLED=false")
        return None

    preference = str(getattr(settings, "AGENT_PROVIDER", "auto")).lower()

    if preference in ("auto", "local"):
        from .ollama_provider import build_ollama_provider

        local = build_ollama_provider(settings)
        if local is not None:
            logger.info("Агент работает локально: %s", local.name)
            return local
        if preference == "local":
            logger.info("Локальная модель недоступна, а облако не разрешено")
            return None

    api_key = getattr(settings, "CLAUDE_API_KEY", "")
    if not api_key:
        logger.info("Агент недоступен: нет локальной модели и не задан CLAUDE_API_KEY")
        return None

    try:
        return ClaudeAgentProvider(
            api_key=api_key,
            # Для рассуждений модель сильнее, чем для классификации: связать
            # факты из шести инструментов и не выдумать норму права — задача
            # другого класса, чем «магазин это или человек».
            model=getattr(settings, "CLAUDE_REASONING_MODEL", "claude-sonnet-5"),
            max_tokens=getattr(settings, "AI_MAX_TOKENS", 4096),
        )
    except Exception as exc:
        logger.warning("Не удалось создать провайдера агента: %s", exc)
        return None
