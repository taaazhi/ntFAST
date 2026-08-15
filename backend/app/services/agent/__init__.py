"""Следственный агент: инструменты и петля рассуждения поверх анализа."""
from .investigator import AgentAnswer, InvestigatorAgent
from .tools import TOOL_SCHEMAS, TOOLS, ToolContext, run_tool

__all__ = [
    "AgentAnswer",
    "InvestigatorAgent",
    "TOOL_SCHEMAS",
    "TOOLS",
    "ToolContext",
    "run_tool",
]
