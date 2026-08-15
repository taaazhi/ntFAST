"""Работа с нормативными актами РК: корпус, поиск, проверка ссылок."""
from .corpus import Article, get_article, is_available, search
from .verifier import (
    CitationCheck,
    ReferenceReport,
    Verdict,
    suggest_articles,
    verify_citation,
    verify_reference_line,
)

__all__ = [
    "Article",
    "get_article",
    "is_available",
    "search",
    "CitationCheck",
    "ReferenceReport",
    "Verdict",
    "suggest_articles",
    "verify_citation",
    "verify_reference_line",
]
