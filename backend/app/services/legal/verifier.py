"""Проверка ссылок на нормы права против официального текста.

Зачем. Ссылки на статьи писались людьми по памяти, и сверка с ИПС «Әділет»
показала, что пять из шести указывали не на ту статью: мошенничество значилось
как ст. 205 (на деле — неправомерный доступ к информации), торговля людьми
как ст. 135 (торговля несовершеннолетними). Языковая модель ошибается так же,
только увереннее и в больших количествах — она охотно назовёт номер статьи,
которой не существует, и перескажет её содержание правдоподобными словами.

Отчёт ntFAST ложится в материалы уголовного дела. Поэтому здесь принят
порядок, обратный привычному: ссылка считается недостоверной, пока не
подтверждена текстом закона. Не «доверяй и проверяй», а «не показывай
непроверенное».

Модуль ничего не исправляет и не подсказывает замену — он только выносит
вердикт. Что делать с непроверенной ссылкой, решает вызывающий код: скрыть,
пометить или отказаться от вывода.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from . import corpus

#: Название кодекса: «УК РК», «ЗРК О ПОД/ФТ», «НК РК».
CODE_NAMES = ("ЗРК О ПОД/ФТ", "УК РК", "НК РК", "ГК РК", "КоАП РК")

#: «УК РК ст. 218», «ЗРК О ПОД/ФТ ст. 4», «НК РК ст. 321-1», а также «ст. 190»
#: без кодекса: в отчёте перечисление вида «УК РК ст. 232 (…); ст. 190 (…)»
#: означает, что вторая статья — из того же кодекса. Без этого проверялась бы
#: только первая ссылка строки, а остальные молча считались бы отсутствующими.
CITATION_PATTERN = re.compile(
    r'(?:(?P<code>' + "|".join(re.escape(c) for c in CODE_NAMES) + r')\s*)?'
    r'ст(?:атья|\.)\s*(?P<number>\d+(?:-\d+)?)',
    re.IGNORECASE,
)


class Verdict(str, Enum):
    """Что удалось установить о ссылке."""

    VERIFIED = "verified"
    #: Статьи с таким номером в кодексе нет — типичная выдумка модели.
    ARTICLE_NOT_FOUND = "article_not_found"
    #: Статья есть, но её содержание не про то, что утверждает ссылка.
    TITLE_MISMATCH = "title_mismatch"
    #: Приведённой цитаты в тексте статьи нет.
    QUOTE_NOT_FOUND = "quote_not_found"
    #: Корпус не собран — проверить нечем. Не то же самое, что «неверно».
    CORPUS_UNAVAILABLE = "corpus_unavailable"


@dataclass
class CitationCheck:
    """Результат проверки одной ссылки."""

    code: str
    number: str
    verdict: Verdict
    title: Optional[str] = None
    url: Optional[str] = None
    detail: str = ""

    @property
    def is_trustworthy(self) -> bool:
        """Можно ли показывать ссылку следователю как подтверждённую."""
        return self.verdict is Verdict.VERIFIED

    @property
    def citation(self) -> str:
        return f"{self.code} ст. {self.number}"


@dataclass
class ReferenceReport:
    """Итог по строке вида «УК РК ст. 232 (…); ст. 190 (…); FATF R.15»."""

    checks: List[CitationCheck] = field(default_factory=list)

    @property
    def all_verified(self) -> bool:
        return bool(self.checks) and all(c.is_trustworthy for c in self.checks)

    @property
    def problems(self) -> List[CitationCheck]:
        return [c for c in self.checks if not c.is_trustworthy]


def _normalise(text: str) -> str:
    """Для сравнения: регистр, ё/е и пунктуация значения не имеют."""
    lowered = (text or "").lower().replace("ё", "е")
    return re.sub(r"[^а-яa-z0-9әғқңөұүіһ]+", " ", lowered).strip()


def verify_citation(
    code: str,
    number: str,
    expected_title: Optional[str] = None,
    quote: Optional[str] = None,
    corpus_dir: Optional[str] = None,
) -> CitationCheck:
    """Проверить одну ссылку против текста закона."""
    if not corpus.is_available(corpus_dir):
        return CitationCheck(
            code, number, Verdict.CORPUS_UNAVAILABLE,
            detail="корпус НПА не собран: python scripts/fetch_legal_corpus.py",
        )

    article = corpus.get_article(code, number, corpus_dir)
    if article is None:
        return CitationCheck(
            code, number, Verdict.ARTICLE_NOT_FOUND,
            detail=f"в корпусе нет статьи {number} кодекса «{code}»",
        )

    if expected_title:
        # Сравниваем по вхождению: в отчёте название часто сокращают
        # («легализация (отмывание) денег» вместо полной формулировки).
        actual, claimed = _normalise(article.title), _normalise(expected_title)
        if claimed not in actual and actual not in claimed:
            return CitationCheck(
                code, number, Verdict.TITLE_MISMATCH,
                title=article.title, url=article.url,
                detail=f"статья называется «{article.title}», а не «{expected_title}»",
            )

    if quote:
        if _normalise(quote) not in _normalise(article.text):
            return CitationCheck(
                code, number, Verdict.QUOTE_NOT_FOUND,
                title=article.title, url=article.url,
                detail="приведённой цитаты в тексте статьи нет",
            )

    return CitationCheck(
        code, number, Verdict.VERIFIED, title=article.title, url=article.url,
    )


def verify_reference_line(
    reference: str, corpus_dir: Optional[str] = None
) -> ReferenceReport:
    """Проверить все ссылки в строке `regulatory_reference`.

    Строка может содержать несколько норм и ссылки на источники, которых в
    корпусе нет по определению — рекомендации FATF, например. Такие
    упоминания не разбираются: проверяется то, что заявлено как статья
    казахстанского акта.
    """
    report = ReferenceReport()
    current_code: Optional[str] = None

    for match in CITATION_PATTERN.finditer(reference or ""):
        if match.group("code"):
            # Приводим к написанию, принятому в корпусе: в отчёте регистр
            # может отличаться.
            spelled = match.group("code").upper()
            current_code = next(
                (name for name in CODE_NAMES if name.upper() == spelled), spelled
            )
        if current_code is None:
            # «ст. 190» до того, как назван хоть один кодекс: определить, из
            # какого он, нельзя, а угадывать в правовом документе нельзя тем
            # более.
            continue

        report.checks.append(
            verify_citation(current_code, match.group("number"), corpus_dir=corpus_dir)
        )
    return report


def suggest_articles(description: str, limit: int = 3, corpus_dir: Optional[str] = None):
    """Статьи, подходящие описанию схемы, — подсказка, а не квалификация.

    Итоговое решение о применимости нормы принимает следователь. Задача
    системы — сузить поиск и дать ссылку на первоисточник, а не поставить
    правовую оценку.
    """
    return [
        {
            "citation": article.citation,
            "title": article.title,
            "url": article.url,
            "relevance": round(score, 3),
        }
        for article, score in corpus.search(description, limit=limit, corpus_dir=corpus_dir)
    ]
