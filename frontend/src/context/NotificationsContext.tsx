/**
 * NotificationsContext — global notification inbox state.
 *
 * Responsibilities:
 *  - Fetch initial list from /api/notifications on mount (when authenticated)
 *  - Re-fetch periodically (30s) as a reliability fallback if WS push misses
 *  - Listen to "notification_new" messages on the existing /ws/activity socket
 *    by piggy-backing on the WebSocket already opened by useActivityMonitor
 *    (we just open a second WS — cheap, isolated, doesn't touch existing code)
 *  - Expose markAsRead / markAllRead / delete / deleteAll handlers
 *
 * Strategy chosen because:
 *  - The existing /ws/activity broadcaster sends notifications via manager.broadcast
 *    which fans out to all connected clients; each client filters by user_id.
 *  - Polling guarantees correctness even if WS reconnects miss events.
 */
import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';
import { notificationsAPI, NotificationItem, WS_BASE_URL } from '../services/api';
import { useAuth } from './AuthContext';

interface NotificationsContextValue {
  items: NotificationItem[];
  unread: number;
  total: number;
  loading: boolean;
  refresh: () => Promise<void>;
  markAsRead: (id: number) => Promise<void>;
  markAllRead: () => Promise<void>;
  remove: (id: number) => Promise<void>;
  clear: () => Promise<void>;
}

const NotificationsContext = createContext<NotificationsContextValue | null>(null);

const POLL_INTERVAL_MS = 30_000;  // backup poll every 30 seconds
const MAX_VISIBLE = 50;            // cap inbox shown in dropdown

export function NotificationsProvider({ children }: { children: React.ReactNode }) {
  const { user, isAuthenticated } = useAuth();
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [unread, setUnread] = useState(0);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);

  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const refresh = useCallback(async () => {
    if (!isAuthenticated) return;
    try {
      const data = await notificationsAPI.list({ limit: MAX_VISIBLE });
      setItems(data.items);
      setUnread(data.unread);
      setTotal(data.total);
    } catch (err) {
      // Silent — we don't want to spam toast errors on every 30s refresh.
      console.debug('Notification refresh failed:', err);
    }
  }, [isAuthenticated]);

  // Initial load + polling
  useEffect(() => {
    if (!isAuthenticated) {
      setItems([]);
      setUnread(0);
      setTotal(0);
      return;
    }
    setLoading(true);
    void refresh().finally(() => setLoading(false));

    pollIntervalRef.current = setInterval(() => {
      void refresh();
    }, POLL_INTERVAL_MS);

    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, [isAuthenticated, refresh]);

  // WebSocket subscriber for real-time push (notification_new events)
  useEffect(() => {
    if (!isAuthenticated || !user) return;

    const connect = () => {
      const token = localStorage.getItem('access_token') || '';
      if (!token) return;
      const url = `${WS_BASE_URL}/ws/activity?token=${encodeURIComponent(token)}`;
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg?.type === 'notification_new' && msg.user_id === user.id && msg.notification) {
            // Prepend the new item, bump unread counter
            setItems(prev => {
              const exists = prev.some(p => p.id === msg.notification.id);
              if (exists) return prev;
              return [msg.notification as NotificationItem, ...prev].slice(0, MAX_VISIBLE);
            });
            setUnread(u => u + 1);
            setTotal(t => t + 1);
          }
        } catch {
          // ignore non-JSON frames
        }
      };

      ws.onclose = () => {
        wsRef.current = null;
        // Reconnect after 5s if still authenticated
        reconnectTimeoutRef.current = setTimeout(() => {
          if (isAuthenticated) connect();
        }, 5000);
      };

      ws.onerror = () => {
        // Errors usually followed by onclose — let onclose handle reconnect
      };
    };

    connect();

    return () => {
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      const ws = wsRef.current;
      if (ws) {
        ws.onclose = null;  // suppress reconnect on cleanup
        try { ws.close(); } catch { /* ignore */ }
        wsRef.current = null;
      }
    };
  }, [isAuthenticated, user]);

  const markAsRead = useCallback(async (id: number) => {
    // Optimistic update first, server call second — UI feels instant
    setItems(prev => prev.map(n => n.id === id ? { ...n, is_read: true } : n));
    setUnread(u => Math.max(0, u - 1));
    try {
      await notificationsAPI.markAsRead(id);
    } catch (err) {
      console.debug('markAsRead failed, refreshing:', err);
      void refresh();  // rollback via refetch
    }
  }, [refresh]);

  const markAllRead = useCallback(async () => {
    setItems(prev => prev.map(n => ({ ...n, is_read: true })));
    setUnread(0);
    try {
      await notificationsAPI.markAllRead();
    } catch (err) {
      console.debug('markAllRead failed, refreshing:', err);
      void refresh();
    }
  }, [refresh]);

  const remove = useCallback(async (id: number) => {
    const target = items.find(n => n.id === id);
    setItems(prev => prev.filter(n => n.id !== id));
    setTotal(t => Math.max(0, t - 1));
    if (target && !target.is_read) setUnread(u => Math.max(0, u - 1));
    try {
      await notificationsAPI.delete(id);
    } catch (err) {
      console.debug('delete failed, refreshing:', err);
      void refresh();
    }
  }, [items, refresh]);

  const clear = useCallback(async () => {
    setItems([]);
    setUnread(0);
    setTotal(0);
    try {
      await notificationsAPI.deleteAll();
    } catch (err) {
      console.debug('deleteAll failed, refreshing:', err);
      void refresh();
    }
  }, [refresh]);

  const value: NotificationsContextValue = {
    items,
    unread,
    total,
    loading,
    refresh,
    markAsRead,
    markAllRead,
    remove,
    clear,
  };

  return <NotificationsContext.Provider value={value}>{children}</NotificationsContext.Provider>;
}

export function useNotifications() {
  const ctx = useContext(NotificationsContext);
  if (!ctx) throw new Error('useNotifications must be used inside NotificationsProvider');
  return ctx;
}
