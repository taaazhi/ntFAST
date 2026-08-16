"""Отличить описание операции от стороны сделки.

Зачем отдельный модуль и отдельные тесты. Банк кладёт в поле контрагента
и «ТОО Астана Строй», и «Комиссия за перевод на карту др. банка». Вторая
строка — не тот, кому платят, а то, что произошло, и попадая в граф связей
она становится узлом: система показывает следователю, что человек шестьдесят
раз переводил деньги «Комиссии». Схемы вывода средств ищут именно в этом
графе, поэтому мусорные узлы в нём — не косметика.

Правило, а не модель: на эталонном наборе оно даёт 16 из 16, локальная
модель давала 5.
"""
import pytest

from app.services.enrichment.operation_words import is_operation_description


@pytest.mark.parametrize("name", [
    "Комиссия за перевод на карту др. банка",
    "Commission for transfer of other banks",
    "Басқа банктің картасына аударғаны үшін комиссия",
    "Transaction Fee",
    "Withdraw fee is included",
    "Monthlyfeeforcardservice Regular Charge",
    "Карточный перевод",
    "Transfertoanothercard",
    "Басқакартағааударым",
    "Аппарат самообслуживания",
    "Transfer Between Spot Account and UM Futures Account",
    "Binance Convert",
    "Жалақы",
])
def test_operation_descriptions_are_recognised(name):
    assert is_operation_description(name), name


@pytest.mark.parametrize("name", [
    "С карты другого банка",
    "From card of other banks",
    "Kaspi Gold-ты басқа банктің картасынан толықтыру",
])
def test_channel_wins_over_the_word_bank(name):
    """«С карты другого банка» содержит слово «банк», но конкретного банка
    не называет — это способ пополнения, а не сторона сделки."""
    assert is_operation_description(name), name


@pytest.mark.parametrize("name", [
    "ТОО \"KASPI MAGAZIN\"",
    "Halyk Bank",
    "АО Финансовый центр",
    "ИП BEREKET",
    "Magnum Cash&Carry",
    "YANDEX.GO",
    "Ержан О.",
    "ГЦВП",
])
def test_real_counterparties_are_not_mistaken_for_operations(name):
    assert not is_operation_description(name), name


@pytest.mark.parametrize("name", ["Coffee Boom", "Master Coffee", "ZEBRA COFFEE Ainakol"])
def test_coffee_is_not_a_fee(name):
    """Регресс: маркер «fee» ловил «cof-fee», и три кофейни уезжали в каналы."""
    assert not is_operation_description(name), name


def test_self_service_car_wash_is_a_merchant():
    """«Аппарат самообслуживания» — канал, «Автомойка самообслуживания» —
    обычная торговая точка. Одного слова для решения мало."""
    assert is_operation_description("Аппарат самообслуживания")
    assert not is_operation_description("Автомойка самообслуживания. AVD.SERVICE")


def test_glued_legal_form_still_marks_an_organisation():
    """«Қаражаттыңшотқатүсуі АОФинансовый центр» — банк, к названию которого
    прилипло описание операции. Форма «АО» перестала быть словом, но
    признаком организации осталась."""
    assert not is_operation_description("Қаражаттыңшотқатүсуі АОФинансовый центр")
    assert not is_operation_description("ReceipttotheaccountАО Финансовый центр")


def test_empty_input_is_not_an_operation():
    assert not is_operation_description("")
    assert not is_operation_description("   ")
