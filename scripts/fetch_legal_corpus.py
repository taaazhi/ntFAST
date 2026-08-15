"""Сборка корпуса нормативных актов РК из ИПС «Әділет».

Что это даёт. Проверка ссылок в `legal_references.py` держит соответствие
номера и названия статьи, но не более: она не знает, что́ в статье написано.
Чтобы отчёт мог приводить норму дословно — и чтобы можно было проверить, не
выдумана ли цитата, — нужен текст.

Тексты в репозиторий не кладутся. Уголовный кодекс — мегабайты, поправки
выходят по нескольку раз в год, а устаревшая копия закона в инструменте для
следствия хуже, чем её отсутствие: она выглядит достоверной. Поэтому корпус
собирается локально этим скриптом, а в репозитории живут только проверка
целостности и выверенная таблица ссылок.

    python scripts/fetch_legal_corpus.py

Разметка у документов разная, хотя портал один: ЗРК и УК размечают статьи
как `<h3 id="z34">Статья 4. …</h3>`, Налоговый кодекс — как
`<p><b><a name="z17802"></a>Статья 321. …</b></p>`. Поддерживаются обе;
незнакомая разметка приводит к явной ошибке, а не к пустому корпусу —
молча собранный корпус из нуля статей выглядел бы как успех.

Якорь `#z34` сохраняется: по нему ссылка ведёт прямо на статью, и
следователь может открыть первоисточник, а не искать её глазами в кодексе.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterator, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.services.fraud.legal_references import NK_URL, UK_URL, ZRK_URL  # noqa: E402

#: Куда складывается корпус. В .gitignore — см. пояснение выше.
CORPUS_DIR = REPO_ROOT / "data" / "legal"

#: Имя файла задаётся явно, а не выводится из названия кодекса. Вывод из
#: кириллицы давал всем трём документам один и тот же slug «rk», и они молча
#: перезаписывали друг друга — в корпусе оставался последний.
DOCUMENTS = {
    "УК РК": {
        "slug": "uk_rk",
        "url": UK_URL,
        "title": "Уголовный кодекс Республики Казахстан от 3 июля 2014 года № 226-V",
    },
    "ЗРК О ПОД/ФТ": {
        "slug": "zrk_pod_ft",
        "url": ZRK_URL,
        "title": (
            "Закон РК от 28 августа 2009 года № 191-IV «О противодействии "
            "легализации (отмыванию) доходов, полученных преступным путем, "
            "финансированию терроризма…»"
        ),
    },
    "НК РК": {
        "slug": "nk_rk",
        "url": NK_URL,
        "title": (
            "Кодекс РК от 25 декабря 2017 года № 120-VI «О налогах и других "
            "обязательных платежах в бюджет (Налоговый кодекс)»"
        ),
    },
}

#: `<h3 id="z34"> Статья 4. Название</h3>` — ЗРК и УК.
HEADING_H3 = re.compile(
    r'<h3[^>]*id="(?P<anchor>z\d+)"[^>]*>\s*Статья\s+(?P<number>\d+(?:-\d+)?)\.\s*'
    r'(?P<title>[^<]{1,300}?)\s*</h3>',
    re.IGNORECASE,
)

#: `<p><b><a name="z17802"></a>Статья 321. Название </b></p>` — Налоговый кодекс.
HEADING_BOLD = re.compile(
    r'<a\s+name="(?P<anchor>z\d+)"[^>]*>\s*</a>\s*Статья\s+(?P<number>\d+(?:-\d+)?)\.\s*'
    r'(?P<title>[^<]{1,300}?)\s*</b>',
    re.IGNORECASE,
)

TAG = re.compile(r"<[^>]+>")
SPACES = re.compile(r"[ \t ]+")


@dataclass(frozen=True)
class Article:
    """Одна статья нормативного акта."""

    code: str
    number: str
    title: str
    text: str
    url: str
    fetched_at: str

    @property
    def key(self) -> str:
        return f"{self.code} ст. {self.number}"


def fetch(url: str) -> str:
    """Скачать страницу.

    Через curl, а не через http-клиент Python: у adilet.zan.kz неполная
    цепочка сертификатов, и большинство клиентов отказываются её проверять,
    тогда как системное хранилище Windows её принимает.
    """
    result = subprocess.run(
        ["curl", "-s", "--max-time", "180", url],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0 or len(result.stdout) < 10_000:
        raise RuntimeError(
            f"не удалось скачать {url}: код {result.returncode}, "
            f"получено {len(result.stdout)} байт"
        )
    return result.stdout.decode("utf-8", errors="replace")


def clean(fragment: str) -> str:
    """HTML-фрагмент → читаемый текст с сохранением абзацев."""
    text = re.sub(r"<br\s*/?>|</p>", "\n", fragment, flags=re.IGNORECASE)
    text = TAG.sub(" ", text)
    text = (
        text.replace("&nbsp;", " ")
        .replace("&laquo;", "«")
        .replace("&raquo;", "»")
        .replace("&quot;", '"')
        .replace("&amp;", "&")
    )
    text = SPACES.sub(" ", text)
    return "\n".join(line.strip() for line in text.split("\n") if line.strip())


def split_articles(html: str, code: str, url: str) -> List[Article]:
    """Разрезать документ по заголовкам статей.

    Текстом статьи считается всё до следующего заголовка. Сноски о поправках
    остаются внутри намеренно: следователю важно видеть, что норма менялась и
    когда, — это часть её актуальности.
    """
    matches = sorted(
        (m for pattern in (HEADING_H3, HEADING_BOLD) for m in pattern.finditer(html)),
        key=lambda m: m.start(),
    )
    if not matches:
        raise RuntimeError(
            f"в документе {code} не найдено ни одного заголовка статьи — "
            f"разметка портала изменилась, парсер нужно поправить"
        )

    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    articles: List[Article] = []
    seen: set[str] = set()

    for index, match in enumerate(matches):
        number = match.group("number")
        if number in seen:
            # Оглавление дублирует заголовки: берём первое вхождение, у него
            # и якорь, и текст.
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(html)
        body = clean(html[match.end():end])
        if len(body) < 40:
            continue

        seen.add(number)
        articles.append(Article(
            code=code,
            number=number,
            title=clean(match.group("title")),
            text=body,
            url=f"{url}#{match.group('anchor')}",
            fetched_at=stamp,
        ))
    return articles


def build_corpus(out_dir: Path = CORPUS_DIR) -> Dict[str, int]:
    out_dir.mkdir(parents=True, exist_ok=True)
    counts: Dict[str, int] = {}

    for code, meta in DOCUMENTS.items():
        print(f"Скачиваю {code}…", flush=True)
        html = fetch(meta["url"])
        articles = split_articles(html, code, meta["url"])

        path = out_dir / f"{meta['slug']}.jsonl"
        with path.open("w", encoding="utf-8") as handle:
            for article in articles:
                handle.write(json.dumps(asdict(article), ensure_ascii=False) + "\n")

        counts[code] = len(articles)
        print(f"  {len(articles)} статей → {path.relative_to(REPO_ROOT)}")

    return counts


def load_corpus(out_dir: Path = CORPUS_DIR) -> Iterator[Article]:
    """Прочитать собранный корпус. Пустой каталог — не ошибка, а «ещё не собран»."""
    for path in sorted(out_dir.glob("*.jsonl")):
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    yield Article(**json.loads(line))


def find_article(code: str, number: str, out_dir: Path = CORPUS_DIR) -> Optional[Article]:
    """Найти статью по номеру — основа проверки цитат."""
    for article in load_corpus(out_dir):
        if article.code == code and article.number == number:
            return article
    return None


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(CORPUS_DIR), help="каталог корпуса")
    args = parser.parse_args(argv)

    counts = build_corpus(Path(args.out))
    total = sum(counts.values())
    print(f"\nВсего статей: {total}")
    print(
        "Корпус не коммитится: тексты объёмны и часто меняются, "
        "а устаревшая копия закона хуже её отсутствия."
    )
    return 0 if total else 1


if __name__ == "__main__":
    raise SystemExit(main())
