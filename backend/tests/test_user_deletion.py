"""Удаление аналитика не должно стирать его заключения.

Найдено при сквозной проверке: `db.delete(user)` падал нарушением внешнего
ключа, и наверх это приходило как 500 без объяснения. Причина оказалась не
только технической.

Анализ выписки — материал по делу, а не собственность сотрудника. Аналитик
увольняется, его заключения остаются: на них ссылаются, их проверяют, они
могут понадобиться через годы. Поэтому удаление пользователя с анализами
запрещено, а не выполняется каскадом, и API отвечает 409 с указанием, что
делать вместо этого.

Служебные записи — уведомления и история входов — принадлежат самой учётной
записи и уходят вместе с ней.
"""
from datetime import datetime

import pytest

from app.services.user_service import UserHasAnalyses, delete_user


class _Query:
    def __init__(self, store, model):
        self._store = store
        self._model = model

    def filter(self, *_):
        return self

    def count(self):
        return len(self._store.get(self._model, []))

    def delete(self, synchronize_session=False):
        removed = len(self._store.get(self._model, []))
        self._store[self._model] = []
        return removed


class _Session:
    """Минимальная замена сессии: важно, что удалено, а не как."""

    def __init__(self, analyses=0, notifications=0, logins=0):
        from app.models.analysis import Analysis
        from app.models.login_history import LoginHistory
        from app.models.notification import Notification

        self.store = {
            Analysis: [object()] * analyses,
            Notification: [object()] * notifications,
            LoginHistory: [object()] * logins,
        }
        self.deleted = []
        self.committed = False

    def query(self, model):
        return _Query(self.store, model)

    def delete(self, obj):
        self.deleted.append(obj)

    def commit(self):
        self.committed = True


class _User:
    id = 7
    email = "analyst@example.com"


@pytest.fixture(autouse=True)
def _stub_lookup(monkeypatch):
    monkeypatch.setattr(
        "app.services.user_service.get_user_by_id",
        lambda db, user_id: _User() if user_id == 7 else None,
    )


def test_analyst_with_analyses_is_not_deleted():
    """Заключения переживают сотрудника — это правило домена, а не БД."""
    db = _Session(analyses=3)

    with pytest.raises(UserHasAnalyses) as exc:
        delete_user(db, 7)

    assert exc.value.count == 3
    assert db.deleted == []
    assert db.committed is False


def test_analyst_without_analyses_is_deleted_with_service_records():
    """Уведомления и история входов принадлежат учётной записи."""
    from app.models.login_history import LoginHistory
    from app.models.notification import Notification

    db = _Session(analyses=0, notifications=5, logins=9)

    assert delete_user(db, 7) is True
    assert db.store[Notification] == []
    assert db.store[LoginHistory] == []
    assert db.committed is True


def test_missing_user_reports_not_found_rather_than_raising():
    db = _Session()

    assert delete_user(db, 999) is False
