"""Определение разметки таблицы языковой моделью.

Зачем это существует, показано замером. Выписка банка, для которого никто не
писал ни парсера, ни словаря заголовков — «Күні/Дата», «Мәні», «Кредит теңге»,
«Сальдо», — давала **0 верных строк из 200 и 201 лишнюю**, причём суммой
становился остаток по счёту, а первой «транзакцией» — строка периода. Отчёт
при этом выглядел успешным: ровно тот тихий провал, который для инструмента
следствия опаснее падения.

С разметкой от модели: 200 из 200, лишних ноль.

Модель здесь решает одну задачу — что означают колонки. Данные извлекает код,
а ответ модели проверяется на самих данных: колонка, названная датой, обязана
содержать даты. Тесты закрепляют именно эту границу доверия.
"""
import pytest

from app.services.bank_analyzer.llm_layout import detect_layout, validate_layout


class FakeAI:
    """Провайдер с заданным ответом. Асинхронный, как настоящий."""

    def __init__(self, payload, provider="FakeLLM"):
        self._payload = payload
        self.calls = []

    async def generate_structured(self, prompt, schema, system_prompt=""):
        self.calls.append(prompt)
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload, "FakeLLM"


HEADER = ["Күні/Дата", "Мәні", "Кому/от кого", "Кредит теңге", "Дебет теңге", "Сальдо"]
ROWS = [
    ["06.01.2025", "Покупка", "Yandex Go", "", "26 341,94", "973 658,06"],
    ["07.01.2025", "Пополнение", "ТОО Астана", "450 000,00", "", "1 423 658,06"],
]


def columns(*pairs):
    return {"columns": [{"index": i, "role": r} for i, r in pairs]}


# ── Разметка, которую словарь заголовков не знает ────────────────

def test_unfamiliar_headers_are_understood():
    """Ни одного из этих заголовков нет в словаре — ради этого случая
    модель здесь и стоит."""
    ai = FakeAI(columns((0, "date"), (1, "type"), (2, "counterparty"),
                        (3, "credit"), (4, "debit"), (5, "balance")))

    layout = detect_layout(HEADER, ROWS, ai)

    assert layout["date"] == 0
    assert layout["counterparty"] == 2
    assert layout["balance"] == 5


def test_split_amount_is_marked_for_the_parser():
    """Приход и расход в разных колонках — парсер разбирает это по флагу,
    который выставляется здесь."""
    ai = FakeAI(columns((0, "date"), (3, "credit"), (4, "debit")))

    layout = detect_layout(HEADER, ROWS, ai)

    assert "amount_split" in layout
    assert "amount" not in layout


# ── Ответ модели проверяется на данных ───────────────────────────

def test_column_called_a_date_must_contain_dates():
    """Модель может назвать датой колонку с назначением платежа."""
    checked = validate_layout({"date": 1, "amount": 4}, HEADER, ROWS)

    assert "date" not in checked
    assert checked["amount"] == 4


def test_column_called_numeric_must_contain_numbers():
    checked = validate_layout({"date": 0, "amount": 2}, HEADER, ROWS)

    assert checked["date"] == 0
    assert "amount" not in checked


def test_layout_without_a_date_is_rejected():
    """Без даты строка не транзакция — такой разметке доверять нельзя."""
    ai = FakeAI(columns((3, "credit"), (4, "debit")))

    assert detect_layout(HEADER, ROWS, ai) is None


def test_layout_without_any_amount_is_rejected():
    ai = FakeAI(columns((0, "date"), (2, "counterparty")))

    assert detect_layout(HEADER, ROWS, ai) is None


def test_index_out_of_range_is_dropped():
    checked = validate_layout({"date": 0, "amount": 99}, HEADER, ROWS)

    assert "amount" not in checked


# ── Отсутствие модели ────────────────────────────────────────────

def test_no_model_means_no_layout_not_a_crash():
    """Разбор знакомого формата не должен зависеть от наличия модели."""
    assert detect_layout(HEADER, ROWS, None) is None


def test_provider_failure_is_survivable():
    ai = FakeAI(ConnectionError("нет сети"))

    assert detect_layout(HEADER, ROWS, ai) is None


def test_malformed_answer_is_rejected():
    assert detect_layout(HEADER, ROWS, FakeAI({"нет нужного ключа": []})) is None
    assert detect_layout(HEADER, ROWS, FakeAI("просто строка")) is None


def test_empty_header_does_not_reach_the_model():
    ai = FakeAI(columns((0, "date")))

    assert detect_layout([], ROWS, ai) is None
    assert ai.calls == []


def test_model_sees_header_and_a_few_rows_not_the_whole_table():
    """Разметка одна на файл: модели незачем показывать тысячу строк."""
    ai = FakeAI(columns((0, "date"), (3, "credit"), (4, "debit")))
    many_rows = ROWS * 100

    detect_layout(HEADER, many_rows, ai, sample=4)

    prompt = ai.calls[0]
    assert prompt.count("06.01.2025") <= 4
