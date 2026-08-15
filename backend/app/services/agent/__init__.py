"""Следственный агент: инструменты и петля рассуждения поверх анализа."""
from .context_factory import from_analysis, from_db_transactions
from .investigator import AgentAnswer, InvestigatorAgent
from .provider import ClaudeAgentProvider, build_agent_provider
from .tools import TOOL_SCHEMAS, TOOLS, ToolContext, run_tool

__all__ = [
    "AgentAnswer",
    "InvestigatorAgent",
    "ClaudeAgentProvider",
    "build_agent_provider",
    "from_analysis",
    "from_db_transactions",
    "TOOL_SCHEMAS",
    "TOOLS",
    "ToolContext",
    "run_tool",
]
