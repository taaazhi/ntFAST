"""Доступ к корпусу нормативных актов РК и поиск по нему.

Корпус собирается локально (`python scripts/fetch_legal_corpus.py`) и в
репозитории не лежит. Поэтому первое требование к этому модулю — работать,
когда корпуса нет: система обязана продолжать анализ, просто без цитат.
Отсутствие текстов законов не должно ронять разбор выписки.

Поиск здесь лексический, а не векторный. Причина не в лени: запрос к корпусу
почти всегда содержит термин из самого закона — «финансовая пирамида»,
«легализация», «финансовый мониторинг», — потому что формулировки схем
писались от него же. На таких запросах совпадение по словам работает
предсказуемо и объяснимо, а объяснимость здесь дороже отзыва: следователь
должен видеть, почему предложена именно эта статья. Векторный поиск имеет
смысл добавлять там, где запрос формулирует человек своими словами.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

#: Каталог, куда `scripts/fetch_legal_corpus.py` складывает статьи.
CORPUS_DIR = Path(__file__).resolve().parents[4] / "data" / "legal"

#: Слова, которые есть в любой статье и потому ничего не различают.
STOPWORDS = frozenset("""
и или в на с по за от до для не что как это тот при над под о об а но
если то же бы ли их его её они она оно мы вы я ты быть был была было
которые который которая иным иными либо также том числе
""".split())

WORD = re.compile(r"[а-яёәғқңөұүіһa-z0-9]+", re.IGNORECASE)


@dataclass(frozen=True)
class Article:
    code: str
    number: str
    title: str
    text: str
    url: str
    fetched_at: str = ""

    @property
    def citation(self) -> str:
        return f"{self.code} ст. {self.number}"


def tokenize(text: str) -> List[str]:
    return [
        word for word in (w.lower() for w in WORD.findall(text or ""))
        if len(word) > 2 and word not in STOPWORDS
    ]


@lru_cache(maxsize=1)
def load_articles(corpus_dir: Optional[str] = None) -> Tuple[Article, ...]:
    """Прочитать корпус. Пустой кортеж, если он не собран.

    Кэшируется: корпус читается один раз на процесс. Это ~7 МБ текста, и
    перечитывать его на каждый флаг в отчёте незачем.
    """
    directory = Path(corpus_dir) if corpus_dir else CORPUS_DIR
    if not directory.exists():
        logger.info(
            "Корпус НПА не найден в %s — цитаты недоступны. "
            "Соберите: python scripts/fetch_legal_corpus.py", directory,
        )
        return ()

    articles: List[Article] = []
    for path in sorted(directory.glob("*.jsonl")):
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                    articles.append(Article(
                        code=payload["code"],
                        number=payload["number"],
                        title=payload["title"],
                        text=payload["text"],
                        url=payload["url"],
                        fetched_at=payload.get("fetched_at", ""),
                    ))
                except (ValueError, KeyError) as exc:
                    logger.warning("Пропущена строка корпуса в %s: %s", path.name, exc)

    logger.info("Корпус НПА: %d статей", len(articles))
    return tuple(articles)


def is_available(corpus_dir: Optional[str] = None) -> bool:
    return bool(load_articles(corpus_dir))


def get_article(
    code: str, number: str, corpus_dir: Optional[str] = None
) -> Optional[Article]:
    """Статья по коду и номеру — точное совпадение, без догадок."""
    for article in load_articles(corpus_dir):
        if article.code == code and article.number == str(number):
            return article
    return None


def search(
    query: str, limit: int = 5, code: Optional[str] = None,
    corpus_dir: Optional[str] = None,
) -> List[Tuple[Article, float]]:
    """Статьи, наиболее подходящие запросу, с оценкой релевантности.

    Оценка — доля слов запроса, найденных в статье, с надбавкой за совпадения
    в заголовке: название статьи гораздо информативнее её тела, где те же
    слова могут встретиться в перечислении исключений.
    """
    terms = set(tokenize(query))
    if not terms:
        return []

    scored: List[Tuple[Article, float]] = []
    for article in load_articles(corpus_dir):
        if code and article.code != code:
            continue

        title_words = set(tokenize(article.title))
        body_words = set(tokenize(article.text))

        title_hits = len(terms & title_words)
        body_hits = len(terms & body_words)
        if not title_hits and not body_hits:
            continue

        score = (3.0 * title_hits + body_hits) / (3.0 * len(terms))
        scored.append((article, min(score, 1.0)))

    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:limit]


def clear_cache() -> None:
    """Сбросить кэш — нужно тестам и после пересборки корпуса."""
    load_articles.cache_clear()
