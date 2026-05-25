"""
WebSocket endpoints для ntFAST

Endpoints:
  /ws/activity?token=JWT    — мониторинг пользователей (требует аутентификации)
  /ws/analysis/{session_id} — прогресс анализа файлов

CRITICAL FIXES:
  - НЕ используем Depends(get_db) — SessionLocal() напрямую для каждой DB-операции
  - Auto-offline задача запускается при старте приложения (не при первом WS-подключении)
  - reset_all_online_statuses() вызывается при старте (чистый slate после рестарта)
"""
import logging
import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Dict, Set, Optional
from app.core.database import SessionLocal
from app.core.security import decode_access_token
from app.services.user_service import (
    update_online_status, update_last_activity
)
from app.models.user import User as UserModel
from app.services.websocket_manager import analysis_progress

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Тайм-ауты ───────────────────────────────
HEARTBEAT_INTERVAL = 30        # Клиент шлёт heartbeat каждые 30 сек
SERVER_PING_TIMEOUT = 40       # Сервер ждёт сообщение 40 сек, потом пингует
INACTIVITY_TIMEOUT = 5 * 60   # 5 минут без heartbeat → offline


class ConnectionManager:
    """Менеджер WebSocket-подключений с трекингом пользователей."""

    def __init__(self):
        # user_id → Set[WebSocket]
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        # websocket → user_id (обратный индекс для быстрого поиска при disconnect)
        self._ws_to_user: Dict[WebSocket, int] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)
        self._ws_to_user[websocket] = user_id

    def disconnect(self, websocket: WebSocket, user_id: int = None):
        if user_id is None:
            user_id = self._ws_to_user.get(websocket)
        if user_id is not None and user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        self._ws_to_user.pop(websocket, None)

    def get_user_id(self, websocket: WebSocket) -> Optional[int]:
        return self._ws_to_user.get(websocket)

    def user_has_connections(self, user_id: int) -> bool:
        """Есть ли у пользователя хотя бы одно активное соединение."""
        return bool(self.active_connections.get(user_id))

    async def send_personal_message(self, message: dict, user_id: int):
        if user_id in self.active_connections:
            disconnected = set()
            for conn in self.active_connections[user_id]:
                try:
                    await conn.send_json(message)
                except Exception:
                    disconnected.add(conn)
            for conn in disconnected:
                self.disconnect(conn, user_id)

    async def broadcast(self, message: dict):
        """Отправить сообщение всем подключённым клиентам."""
        disconnected = []
        for user_id, connections in list(self.active_connections.items()):
            for conn in list(connections):
                try:
                    await conn.send_json(message)
                except Exception:
                    disconnected.append((user_id, conn))
        for uid, conn in disconnected:
            self.disconnect(conn, uid)

    def get_online_user_ids(self) -> Set[int]:
        """Список всех user_id с активными соединениями."""
        return set(self.active_connections.keys())


manager = ConnectionManager()


# ═══════════════════════════════════════════════
# Auto-offline background task
# ═══════════════════════════════════════════════
_cleanup_task: Optional[asyncio.Task] = None


async def _auto_offline_loop():
    """
    Периодически проверяет last_activity всех online-пользователей.
    Если > INACTIVITY_TIMEOUT и нет WS-соединений → ставит offline.

    Запускается при старте приложения через start_cleanup_task().
    """
    while True:
        await asyncio.sleep(60)  # Проверяем каждые 60 секунд
        try:
            db = SessionLocal()
            try:
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                online_users = db.query(UserModel).filter(
                    UserModel.is_online == True
                ).all()

                for user in online_users:
                    if user.last_activity:
                        inactive_sec = (now - user.last_activity).total_seconds()
                        if inactive_sec > INACTIVITY_TIMEOUT:
                            if not manager.user_has_connections(user.id):
                                logger.info(
                                    f"Auto-offline: user {user.id} ({user.email}), "
                                    f"inactive {inactive_sec:.0f}s"
                                )
                                update_online_status(db, user.id, False)
                                await manager.broadcast({
                                    "type": "user_offline",
                                    "user_id": user.id,
                                    "timestamp": now.isoformat() + "Z"
                                })
                    else:
                        # Нет last_activity но is_online=True — аномалия
                        if not manager.user_has_connections(user.id):
                            logger.info(
                                f"Auto-offline (no activity): user {user.id} ({user.email})"
                            )
                            update_online_status(db, user.id, False)
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Auto-offline check error: {e}")


def start_cleanup_task():
    """
    Запускает фоновую задачу auto-offline.
    Вызывается из main.py при старте приложения.
    """
    global _cleanup_task
    try:
        loop = asyncio.get_running_loop()
        if _cleanup_task is None or _cleanup_task.done():
            _cleanup_task = loop.create_task(_auto_offline_loop())
            logger.info("Auto-offline background task started")
    except RuntimeError:
        logger.warning("Cannot start auto-offline task: no running event loop")


def reset_all_online_statuses():
    """
    Сбрасывает is_online = False для всех пользователей.
    Вызывается при старте приложения — чистый slate после рестарта.
    """
    try:
        db = SessionLocal()
        try:
            count = db.query(UserModel).filter(
                UserModel.is_online == True
            ).update({"is_online": False})
            db.commit()
            if count > 0:
                logger.info(f"Startup: reset {count} user(s) to offline")
            else:
                logger.info("Startup: all users already offline")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Failed to reset online statuses on startup: {e}")


# ── Утилита: извлечение user_id из JWT ───────
def _extract_user_id_from_token(token: str) -> Optional[int]:
    """Декодирует JWT и возвращает user_id (или None)."""
    try:
        payload = decode_access_token(token)
        if payload and "sub" in payload:
            return int(payload["sub"])
    except Exception:
        pass
    return None


# ═══════════════════════════════════════════════
# Endpoint: /ws/activity — мониторинг пользователей
# ═══════════════════════════════════════════════

@router.websocket("/ws/activity")
async def websocket_activity_endpoint(
    websocket: WebSocket,
    token: str = Query(default=None),
):
    """
    WebSocket для реал-тайм мониторинга активности пользователей.

    CRITICAL: НЕ используем Depends(get_db) — SessionLocal() напрямую!
    Depends(get_db) — генератор, может молча убить долгоживущее WS-соединение.

    Подключение: ws://.../ws/activity?token=JWT_TOKEN

    Аутентификация:
      - JWT передаётся через query parameter `token`
      - Если токен валиден → user_id берётся из токена (доверенный)
      - Если токена нет → подключение как наблюдатель (user_id=0)
    """
    # Аутентификация через JWT
    user_id = 0
    if token:
        extracted = _extract_user_id_from_token(token)
        if extracted:
            user_id = extracted
            logger.info(f"WS activity: user {user_id} authenticated via JWT")
        else:
            logger.warning("WS activity: invalid/expired token, rejecting")
            await websocket.close(code=4001, reason="Invalid token")
            return
    else:
        logger.info("WS activity: observer connection (no token)")

    # Accept connection
    await manager.connect(websocket, user_id)
    logger.info(f"WS activity: connected (user_id={user_id})")

    # Если аутентифицированный пользователь — ставим online
    if user_id > 0:
        try:
            db = SessionLocal()
            try:
                update_online_status(db, user_id, True)
                update_last_activity(db, user_id)
            finally:
                db.close()
        except Exception as e:
            logger.error(f"WS: failed to set user {user_id} online: {e}")

        now_ts = datetime.now(timezone.utc).replace(tzinfo=None)
        await manager.broadcast({
            "type": "user_online",
            "user_id": user_id,
            "timestamp": now_ts.isoformat() + "Z",
            "last_activity": now_ts.isoformat() + "Z"
        })

    try:
        # Отправляем полный список пользователей
        users_data = []
        try:
            db = SessionLocal()
            try:
                users = db.query(UserModel).all()
                for u in users:
                    users_data.append({
                        "id": u.id,
                        "full_name": u.full_name,
                        "email": u.email,
                        "role": u.role,
                        "is_online": u.is_online,
                        "last_login": u.last_login.isoformat() + "Z" if u.last_login else None,
                        "last_activity": u.last_activity.isoformat() + "Z" if u.last_activity else None,
                        "previous_login": u.previous_login.isoformat() + "Z" if u.previous_login else None,
                        "session_start": u.session_start.isoformat() + "Z" if u.session_start else None,
                        "total_online_time": u.total_online_time or 0,
                        "created_at": u.created_at.isoformat() + "Z" if u.created_at else None
                    })
            finally:
                db.close()
        except Exception as e:
            logger.error(f"WS: failed to fetch initial users: {e}")

        await websocket.send_json({
            "type": "initial_users",
            "users": users_data
        })

        # Основной цикл
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=SERVER_PING_TIMEOUT
                )

                if data.get("type") == "heartbeat":
                    if user_id > 0:
                        try:
                            db = SessionLocal()
                            try:
                                updated_ts = update_last_activity(db, user_id)
                            finally:
                                db.close()

                            await manager.broadcast({
                                "type": "status_update",
                                "user_id": user_id,
                                "is_online": True,
                                "last_activity": updated_ts.isoformat() + "Z"
                            })
                        except Exception as e:
                            logger.warning(f"WS heartbeat DB error: {e}")

                elif data.get("type") == "pong":
                    pass  # Клиент жив

            except asyncio.TimeoutError:
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.warning(f"WS activity error: {e}")
                break

    except Exception as e:
        logger.warning(f"WS activity connection error: {e}")
    finally:
        manager.disconnect(websocket, user_id)
        logger.info(f"WS activity: disconnected (user_id={user_id})")

        if user_id > 0 and not manager.user_has_connections(user_id):
            try:
                db = SessionLocal()
                try:
                    update_online_status(db, user_id, False)
                finally:
                    db.close()
            except Exception:
                pass

            await manager.broadcast({
                "type": "user_offline",
                "user_id": user_id,
                "timestamp": datetime.now(timezone.utc).isoformat() + "Z"
            })


# ═══════════════════════════════════════════════
# Endpoint: /ws/analysis/{session_id} — прогресс анализа
# ═══════════════════════════════════════════════

@router.websocket("/ws/analysis/{session_id}")
async def websocket_analysis_progress(
    websocket: WebSocket,
    session_id: str,
    token: Optional[str] = Query(None),
):
    """
    WebSocket для реал-тайм прогресса анализа файлов.

    SECURITY: требует JWT-токен в query (?token=...). Без валидного токена
    соединение закрывается до начала обмена данными — это предотвращает
    подбор session_id и перехват прогресса чужих анализов.
    """
    # SECURITY: validate JWT before accepting the connection
    if not token:
        # 1008 = Policy Violation (RFC 6455). close() works without prior accept.
        await websocket.close(code=1008, reason="Missing authentication token")
        return

    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        await websocket.close(code=1008, reason="Invalid or expired token")
        return

    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        await websocket.close(code=1008, reason="Malformed token claims")
        return

    logger.debug(f"WS analysis: authenticated user_id={user_id} for session={session_id}")

    await analysis_progress.connect(websocket, session_id)

    try:
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_json(), timeout=300.0
                )
                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})

            except asyncio.TimeoutError:
                break
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.debug(f"WS analysis error: {e}")
                break

    except Exception as e:
        logger.warning(f"WS analysis connection error: {e}")
    finally:
        analysis_progress.disconnect(websocket, session_id)
