"""Следственный агент: инструменты и петля рассуждения поверх анализа."""
from .conclusion import Conclusion, build_conclusion, collect_facts, find_invented_numbers
from .context_factory import from_analysis, from_db_transactions
from .investigator import AgentAnswer, InvestigatorAgent
from .provider import ClaudeAgentProvider, build_agent_provider
from .tools import TOOL_SCHEMAS, TOOLS, ToolContext, run_tool

__all__ = [
    "Conclusion",
    "build_conclusion",
    "collect_facts",
    "find_invented_numbers",
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
