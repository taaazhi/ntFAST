/**
 * useActivityMonitor — WebSocket hook для мониторинга активности пользователей.
 *
 * Подключается к ws://.../ws/activity?token=JWT и получает обновления:
 *   { type: "initial_users", users: [...] }
 *   { type: "status_update", user_id, is_online, last_login?, last_activity? }
 *   { type: "user_online", user_id, timestamp, last_activity }
 *   { type: "user_offline", user_id, timestamp }
 *   { type: "new_login", user_id, login_time }
 *   { type: "ping" }
 *
 * Heartbeat:
 *   Отправляет { type: "heartbeat" } каждые 30 секунд.
 *   user_id берётся из JWT на сервере (безопасность!).
 *   HTTP heartbeat НЕ используется — только WebSocket.
 *
 * Reconnection:
 *   Reconnects on ANY close (clean or unclean) with exponential backoff.
 *   Max delay: 30 seconds. Max attempts: unlimited (until manual disconnect).
 *   Codes 4001 / 1008 (token rejected or missing): stops reconnecting. The
 *   endpoint serves authenticated users only — retrying without credentials
 *   would loop forever. The axios 401 interceptor handles the redirect.
 */
import { closeSocket } from '../utils/websocket';
import { useEffect, useRef, useState, useCallback } from 'react';
import { WS_BASE_URL } from '../services/api';

export interface UserStatus {
  user_id: number;
  is_online: boolean;
  last_login: string | null;
  last_activity: string | null;
}

interface UseActivityMonitorReturn {
  userStatuses: Map<number, UserStatus>;
  isConnected: boolean;
  connect: () => void;
  disconnect: () => void;
}

// Reconnection constants
const RECONNECT_BASE_DELAY = 1000;   // 1 second
const RECONNECT_MAX_DELAY = 30000;   // 30 seconds
const HEARTBEAT_INTERVAL = 30000;    // 30 seconds

export const useActivityMonitor = (): UseActivityMonitorReturn => {
  const wsRef = useRef<WebSocket | null>(null);
  const heartbeatIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const shouldReconnectRef = useRef<boolean>(true);
  const isConnectingRef = useRef<boolean>(false);
  const reconnectAttemptRef = useRef<number>(0);

  const [userStatuses, setUserStatuses] = useState<Map<number, UserStatus>>(new Map());
  const [isConnected, setIsConnected] = useState(false);

  /**
   * Отправить WS heartbeat.
   * user_id берётся из JWT на сервере — НЕ передаём его в payload.
   */
  const sendHeartbeat = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      try {
        wsRef.current.send(JSON.stringify({ type: 'heartbeat' }));
      } catch (error) {
        console.error('[WS] Failed to send heartbeat:', error);
      }
    }
  }, []);

  const connect = useCallback(() => {
    // Prevent multiple simultaneous connection attempts
    if (isConnectingRef.current) return;

    // Check if already connected or connecting
    const currentState = wsRef.current?.readyState;
    if (currentState === WebSocket.OPEN || currentState === WebSocket.CONNECTING) return;

    // The endpoint no longer accepts anonymous connections, so a missing
    // token means there is nothing to connect with. Bail out instead of
    // opening a socket the server will immediately close with 1008.
    const token = localStorage.getItem('access_token');
    if (!token) {
      console.log('[WS] No access token — activity monitor stays offline');
      return;
    }

    isConnectingRef.current = true;
    shouldReconnectRef.current = true;

    try {
      // Close any existing connection first
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }

      const wsUrl = `${WS_BASE_URL}/ws/activity?token=${encodeURIComponent(token)}`;
      console.log(`[WS] Connecting to ${WS_BASE_URL}/ws/activity (attempt: ${reconnectAttemptRef.current})`);

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        isConnectingRef.current = false;
        reconnectAttemptRef.current = 0;  // Reset backoff on successful connection
        setIsConnected(true);
        console.log('[WS] Connected successfully');

        // Clear any pending reconnect attempts
        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current);
          reconnectTimeoutRef.current = null;
        }

        // Start WS heartbeat (single heartbeat mechanism — no HTTP heartbeat)
        if (heartbeatIntervalRef.current) {
          clearInterval(heartbeatIntervalRef.current);
        }
        heartbeatIntervalRef.current = setInterval(sendHeartbeat, HEARTBEAT_INTERVAL);

        // Send initial heartbeat
        sendHeartbeat();
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          switch (data.type) {
            case 'initial_users':
              {
                const newStatuses = new Map<number, UserStatus>();
                data.users.forEach((u: any) => {
                  newStatuses.set(u.id, {
                    user_id: u.id,
                    is_online: u.is_online,
                    last_login: u.last_login || null,
                    last_activity: u.last_activity || null,
                  });
                });
                setUserStatuses(newStatuses);
              }
              break;

            case 'status_update':
              // Heartbeat update (last_activity) or login update (last_login + last_activity)
              setUserStatuses(prev => {
                const newMap = new Map(prev);
                const existing = newMap.get(data.user_id);
                newMap.set(data.user_id, {
                  user_id: data.user_id,
                  is_online: data.is_online !== undefined ? data.is_online : true,
                  last_login: data.last_login || existing?.last_login || null,
                  last_activity: data.last_activity || existing?.last_activity || null,
                });
                return newMap;
              });
              break;

            case 'user_online':
              setUserStatuses(prev => {
                const newMap = new Map(prev);
                const existing = newMap.get(data.user_id);
                newMap.set(data.user_id, {
                  user_id: data.user_id,
                  is_online: true,
                  last_login: existing?.last_login || null,
                  last_activity: data.last_activity || data.timestamp || existing?.last_activity || null,
                });
                return newMap;
              });
              break;

            case 'user_offline':
              setUserStatuses(prev => {
                const newMap = new Map(prev);
                const existing = newMap.get(data.user_id);
                if (existing) {
                  newMap.set(data.user_id, {
                    ...existing,
                    is_online: false,
                  });
                }
                return newMap;
              });
              break;

            case 'new_login':
              setUserStatuses(prev => {
                const newMap = new Map(prev);
                const existing = newMap.get(data.user_id);
                if (existing) {
                  newMap.set(data.user_id, {
                    ...existing,
                    is_online: true,
                    last_login: data.login_time || existing.last_login,
                    last_activity: data.login_time || existing.last_activity,
                  });
                }
                return newMap;
              });
              break;

            case 'ping':
              if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'pong' }));
              }
              break;
          }
        } catch (error) {
          console.error('[WS] Error parsing message:', error);
        }
      };

      ws.onerror = (error) => {
        isConnectingRef.current = false;
        console.error('[WS] Connection error:', error);
      };

      ws.onclose = (event) => {
        isConnectingRef.current = false;
        setIsConnected(false);

        // Clear heartbeat
        if (heartbeatIntervalRef.current) {
          clearInterval(heartbeatIntervalRef.current);
          heartbeatIntervalRef.current = null;
        }

        console.log(`[WS] Connection closed: code=${event.code}, reason=${event.reason}, clean=${event.wasClean}`);

        // CRITICAL: Reconnect on ANY close (not just unclean)
        // Unless manually disconnected via disconnect()
        if (shouldReconnectRef.current) {
          // 4001 = token rejected, 1008 = token missing. Both mean this client
          // has no valid session, and the server no longer serves anonymous
          // observers (it used to hand them every user's email). Retrying
          // without a token would just loop against a closed door — stop and
          // let the axios 401 interceptor route the user to /login.
          if (event.code === 4001 || event.code === 1008) {
            console.warn(`[WS] Authentication rejected (${event.code}). Not reconnecting.`);
            shouldReconnectRef.current = false;
            return;
          }

          // Exponential backoff: 1s, 2s, 4s, 8s, 16s, 30s (max)
          const delay = Math.min(
            RECONNECT_BASE_DELAY * Math.pow(2, reconnectAttemptRef.current),
            RECONNECT_MAX_DELAY
          );
          reconnectAttemptRef.current++;

          console.log(`[WS] Reconnecting in ${delay}ms (attempt ${reconnectAttemptRef.current})`);

          if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current);
          }
          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, delay);
        }
      };
    } catch (error) {
      console.error('[WS] Connection exception:', error);
      isConnectingRef.current = false;
    }
  }, [sendHeartbeat]);

  const disconnect = useCallback(() => {
    // Disable auto-reconnect
    shouldReconnectRef.current = false;

    // Clear intervals and timeouts
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
      heartbeatIntervalRef.current = null;
    }

    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    // Close WebSocket connection
    closeSocket(wsRef.current, 1000, 'Client disconnecting');
    wsRef.current = null;

    isConnectingRef.current = false;
    reconnectAttemptRef.current = 0;
    setIsConnected(false);
  }, []);

  // Auto-connect when component mounts (only once)
  useEffect(() => {
    shouldReconnectRef.current = true;
    reconnectAttemptRef.current = 0;
    connect();

    return () => {
      disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return {
    userStatuses,
    isConnected,
    connect,
    disconnect
  };
};

/**
 * Format time ago in messenger-style (works universally across all timezones)
 * Backend sends UTC time with 'Z' suffix (ISO 8601 format)
 */
export const formatTimeAgo = (timestamp: string | null, t: (key: string, options?: any) => string): string => {
  if (!timestamp) return t('userManagement.neverLoggedIn');

  try {
    const utcTime = new Date(timestamp);

    if (isNaN(utcTime.getTime())) {
      return t('userManagement.neverLoggedIn');
    }

    const nowUtc = new Date();
    const diffMs = nowUtc.getTime() - utcTime.getTime();
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHours = Math.floor(diffMin / 60);
    const diffDays = Math.floor(diffHours / 24);

    // Handle future timestamps (clock skew protection)
    if (diffSec < 0) return t('userManagement.justNow');

    // Messenger-style time formatting
    if (diffSec < 5) return t('userManagement.online');
    if (diffSec < 60) return t('userManagement.justNow');
    if (diffMin === 1) return t('userManagement.minuteAgo');
    if (diffMin < 60) return t('userManagement.minutesAgo', { minutes: diffMin });
    if (diffHours === 1) return t('userManagement.hourAgo');
    if (diffHours < 24) return t('userManagement.hoursAgo', { hours: diffHours });
    if (diffDays === 1) return t('userManagement.yesterday');
    if (diffDays < 7) return t('userManagement.daysAgo', { days: diffDays });
    if (diffDays < 30) return t('userManagement.weeksAgo', { weeks: Math.floor(diffDays / 7) });
    if (diffDays < 365) return t('userManagement.monthsAgo', { months: Math.floor(diffDays / 30) });
    return t('userManagement.longTimeAgo');
  } catch {
    return t('userManagement.neverLoggedIn');
  }
};

// Helper function to format exact time (shows in local timezone)
export const formatExactTime = (timestamp: string | null): string => {
  if (!timestamp) return '—';

  const date = new Date(timestamp);

  const hours = date.getHours().toString().padStart(2, '0');
  const minutes = date.getMinutes().toString().padStart(2, '0');
  const seconds = date.getSeconds().toString().padStart(2, '0');

  return `${hours}:${minutes}:${seconds}`;
};
