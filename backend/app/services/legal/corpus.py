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
import math
import re
from collections import Counter, defaultdict
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

#: Окончания, отсекаемые перед сравнением слов.
#:
#: Без этого поиск проваливался на падежах, и провал был тихим: статья 217
#: называется «Создание и руководство финансовой (инвестиционной) пирамидой»,
#: и запрос «финансовой пирамидой» находил её с релевантностью 1.00, а
#: «финансовая пирамида» — не находил вовсе. Следователь задаёт вопрос в
#: именительном падеже, закон формулирует норму в творительном, и норма
#: остаётся ненайденной. Модель в такой ситуации либо молчит, либо выдумывает
#: номер статьи.
#:
#: Список покрывает русские именные и глагольные окончания и казахские
#: падежные аффиксы. Длинные отсекаются первыми: «финансовыми» → «финанс»,
#: а не «финансовым».
_RU_SUFFIXES = tuple(sorted((
    # существительные и прилагательные
    "ами", "ями", "ого", "ому", "ыми", "ими", "ая", "яя", "ое", "ее", "ые",
    "ие", "ый", "ий", "ой", "ей", "ам", "ям", "ах", "ях", "ом", "ем", "ов",
    "ев", "ью", "ия", "ии", "у", "ю", "ы", "и", "е", "а", "я", "о", "ь",
    # глаголы и причастия
    "ется", "ются", "ать", "ять", "ить", "еть", "ует", "ают", "ени", "ния",
), key=len, reverse=True))

#: Казахские аффиксы применяются отдельно и только к казахским словам.
#: Они пересекаются с концами русских слов: «да» — казахский местный падеж,
#: и из-за него «пирамида» превращалась в «пирами», тогда как «пирамидой»
#: давало «пирамид». Формы одного слова переставали совпадать, и запрос
#: «финансовая пирамида» не находил статью 217.
_KK_SUFFIXES = tuple(sorted((
    "дың", "тың", "нің", "ның", "ден", "тен", "нен", "мен", "бен", "пен",
    "ға", "ге", "қа", "ке", "да", "де", "та", "те", "ды", "ді", "ты", "ті",
    "лар", "лер", "дар", "дер", "тар", "тер",
), key=len, reverse=True))

#: Буквы, которые есть только в казахском алфавите. По ним слово и опознаётся
#: как казахское — русское слово ни одной из них не содержит.
_KK_LETTERS = frozenset("әғқңөұүіһ")

#: Короче четырёх символов основу не режем: «дело» → «дел» ещё осмысленно,
#: «дар» → «д» уже совпадёт с чем угодно.
_MIN_STEM = 4


def stem(word: str) -> str:
    """Грубая основа слова: отсечь одно окончание, если основа не короче.

    Не морфологический анализатор и не претендует им быть. Задача узкая —
    свести «пирамида», «пирамиды» и «пирамидой» к общей форме, чтобы вопрос
    на человеческом языке находил статью, сформулированную на юридическом.
    Полноценная лемматизация потребовала бы словаря на десятки мегабайт ради
    выигрыша, которого здесь не видно.
    """
    if len(word) <= _MIN_STEM:
        return word

    suffixes = _KK_SUFFIXES if _KK_LETTERS & set(word) else _RU_SUFFIXES
    for suffix in suffixes:
        if word.endswith(suffix) and len(word) - len(suffix) >= _MIN_STEM:
            return word[: -len(suffix)]
    return word


@dataclass(frozen=True)
class Article:
    code: str
    number: str
    title: str
    text: str
    url: str
    fetched_at: str = ""
    #: Название и ссылка на казахскую редакцию. Пустые, если перевода нет:
    #: отсутствие казахского названия не повод скрывать норму целиком.
    title_kk: str = ""
    url_kk: str = ""

    def localised_title(self, language: str) -> str:
        """Название на языке отчёта, с откатом на русский.

        Официальные названия не переводятся на ходу — они берутся из
        казахской редакции того же акта на adilet.zan.kz. Там, где перевод
        не найден, показывается русское название: увидеть норму на чужом
        языке лучше, чем не увидеть её вовсе.
        """
        if language == "kk" and self.title_kk:
            return self.title_kk
        return self.title

    def localised_url(self, language: str) -> str:
        """Ссылка на ту редакцию, название которой показано."""
        if language == "kk" and self.url_kk:
            return self.url_kk
        return self.url

    @property
    def citation(self) -> str:
        return f"{self.code} ст. {self.number}"


def tokenize(text: str) -> List[str]:
    """Слова текста, приведённые к основам, без стоп-слов.

    Ё приводится к Е: официальные тексты печатают «платежных», человек пишет
    «платёжные», и без этого запрос про поддельные платёжные карточки не
    находил статью 232, которая ровно про них.
    """
    lowered = (text or "").lower().replace("ё", "е")
    return [
        stem(word) for word in WORD.findall(lowered)
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
                        title_kk=payload.get("title_kk", ""),
                        url_kk=payload.get("url_kk", ""),
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


# ── Ранжирование: BM25 ────────────────────────────────────────────
#
# Раньше оценкой была голая доля совпавших слов с бустом заголовка ×3. Она не
# различала редкие слова и частые: «финансовой» весила как «пирамидой», хотя
# второе однозначно указывает на статью, а первое встречается в десятках. На
# полном корпусе это стоило точности — правильная статья уходила вниз выдачи.
# BM25 добавляет IDF (редкое слово важнее), насыщение частоты и нормировку на
# длину статьи. Замер до/после — scripts/eval_retrieval.py.
BM25_K1 = 1.5
BM25_B = 0.75
#: Доля, на которую понижается оценка производной статьи («217-1» против
#: «217»). Правит перекос BM25-нормировки в пользу более коротких названий.
DERIVED_PENALTY = 0.9
#: Заголовок весит втрое: название статьи информативнее тела, где те же слова
#: могут мелькнуть в перечне исключений. Реализовано утроением токенов
#: заголовка в «документе» — так буст переносится и в IDF, и в длину.
TITLE_WEIGHT = 3


@lru_cache(maxsize=1)
def _corpus_index(corpus_dir: Optional[str] = None):
    """Предпосчёт для BM25: по каждой статье — частоты токенов (заголовок
    утроен), плюс документная частота термина, число статей и средняя длина.
    Кэшируется вместе с корпусом: считается один раз на процесс."""
    articles = load_articles(corpus_dir)
    doc_counts: List[Counter] = []
    df: Dict[str, int] = defaultdict(int)
    total_len = 0
    for article in articles:
        tokens = tokenize(article.title) * TITLE_WEIGHT + tokenize(article.text)
        counts = Counter(tokens)
        doc_counts.append(counts)
        total_len += sum(counts.values())
        for term in counts:
            df[term] += 1
    n = len(articles)
    avgdl = (total_len / n) if n else 0.0
    return articles, tuple(doc_counts), dict(df), n, avgdl


def search(
    query: str, limit: int = 5, code: Optional[str] = None,
    corpus_dir: Optional[str] = None,
) -> List[Tuple[Article, float]]:
    """Статьи, наиболее подходящие запросу, с оценкой релевантности.

    Ранжирование — BM25: слова, редкие в корпусе, весят больше; заголовок
    втрое важнее тела. Оценка нормируется так, что у лучшего результата она
    равна 1.0 — число для показа, а не абсолютная вероятность.
    """
    terms = set(tokenize(query))
    if not terms:
        return []

    articles, doc_counts, df, n, avgdl = _corpus_index(corpus_dir)
    if not articles or avgdl == 0:
        return []

    # +1 внутри логарифма — чтобы очень частый термин не давал отрицательный
    # вклад и не «штрафовал» статью за общее слово.
    idf = {t: math.log(1 + (n - df.get(t, 0) + 0.5) / (df.get(t, 0) + 0.5)) for t in terms}

    scored: List[Tuple[Article, float]] = []
    for article, counts in zip(articles, doc_counts):
        if code and article.code != code:
            continue
        dl = sum(counts.values())
        score = 0.0
        matched = 0
        for t in terms:
            freq = counts.get(t, 0)
            if not freq:
                continue
            matched += 1
            denom = freq + BM25_K1 * (1 - BM25_B + BM25_B * dl / avgdl)
            score += idf[t] * (freq * (BM25_K1 + 1)) / denom
        if not matched:
            continue
        # Мягкий приоритет основной статьи над производной. BM25 нормирует на
        # длину, поэтому у более короткого названия «217-1 Реклама пирамиды»
        # оценка выходит чуть выше «217 Создание пирамиды» при равном
        # совпадении — и производная всплывала первой. Небольшой штраф решает
        # near-ties в пользу основного состава, но явно более релевантную
        # производную (запрос прямо про «рекламу») не топит.
        if "-" in article.number:
            score *= DERIVED_PENALTY
        scored.append((article, score))

    if not scored:
        return []

    top = max(score for _, score in scored)
    scored = [(article, (score / top) if top else 0.0) for article, score in scored]

    # При равной оценке впереди основная статья, а не производная: «217»
    # (создание пирамиды) важнее «217-1» (реклама пирамиды), и «218» важнее
    # «218-1». У производной название короче, поэтому при прочих равных она
    # всплывала выше — без этой поправки вытесняла основной состав.
    def rank(pair):
        article, score = pair
        derived = "-" in article.number
        return (-score, derived, len(article.title))

    scored.sort(key=rank)
    return scored[:limit]


def clear_cache() -> None:
    """Сбросить кэш — нужно тестам и после пересборки корпуса."""
    load_articles.cache_clear()
    _corpus_index.cache_clear()
