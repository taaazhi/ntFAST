"""Privacy layer — маскирование персональных данных перед выходом за периметр.

Единственная точка, через которую данные выписки попадают во внешние сервисы
(облачные LLM). Всё, что уходит наружу, обязано пройти через Anonymizer.
"""
from .anonymizer import Anonymizer, AnonymizationReport

__all__ = ["Anonymizer", "AnonymizationReport"]
