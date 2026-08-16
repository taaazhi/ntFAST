"""Схема ответа не должна отказывать в обслуживании из-за данных в базе.

Регресс, найденный при первом сквозном прогоне системы. У учётной записи с
адресом в домене `.local` (зарезервирован RFC 6762) запрос `GET /api/auth/me`
отвечал 500: `EmailStr` наследовался в схему ответа и валидировал адрес
повторно, уже на выходе.

Последствие хуже, чем кажется. Фронтенд трактует ошибку этого запроса как
просроченный токен, удаляет его и возвращает на форму входа — то есть
пользователь не может войти вообще, и причина никак не видна.

Принцип: строго на входе, терпимо на выходе. Адрес проверен при создании
учётной записи; повторная проверка при чтении способна только отказать там,
где отказывать нечему.
"""
import pytest
from pydantic import ValidationError

from app.schemas.auth import UserCreate, UserResponse


class _Row:
    """Строка из базы — то, что видит `response_model`."""

    def __init__(self, email):
        from datetime import datetime

        self.id = 1
        self.email = email
        self.full_name = "Проверка"
        self.role = "analyst"
        self.is_active = True
        self.is_online = False
        self.created_at = datetime(2025, 1, 1)
        self.last_login = None
        self.last_activity = None
        self.previous_login = None
        self.session_start = None
        self.total_online_time = 0


@pytest.mark.parametrize("email", [
    "user@ntfast.local",          # зарезервированный домен, RFC 6762
    "legacy@localhost",
    "странный@пример.қаз",
])
def test_unusual_addresses_in_the_database_still_serialise(email):
    """Запись уже в базе. Отдать её — можно, отказать — нельзя."""
    payload = UserResponse.model_validate(_Row(email), from_attributes=True)

    assert payload.email == email


def test_registration_still_rejects_a_broken_address():
    """Терпимость на выходе не означает терпимости на входе."""
    with pytest.raises(ValidationError):
        UserCreate(email="не-адрес", full_name="Имя", password="secret123")


def test_registration_accepts_a_normal_address():
    user = UserCreate(
        email="analyst@example.com", full_name="Имя", password="secret123"
    )

    assert user.email == "analyst@example.com"
