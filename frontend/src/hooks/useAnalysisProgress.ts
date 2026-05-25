/**
 * useAnalysisProgress — WebSocket hook для реал-тайм прогресса анализа.
 *
 * Подключается к ws://.../ws/analysis/{sessionId} и получает обновления:
 *   { type: "progress", step, percent, message, detail, timestamp }
 *   { type: "completed", percent: 100 }
 *   { type: "error", message }
 */
import { useState, useCallback, useRef, useEffect } from 'react';
import { WS_BASE_URL } from '../services/api';

export interface AnalysisStep {
  step: string;
  percent: number;
  message: string;
  detail: string;
  timestamp: string;
}

export interface AnalysisProgressState {
  /** Текущий процент 0-100 */
  percent: number;
  /** Текущий шаг (step id) */
  step: string;
  /** Сообщение для пользователя */
  message: string;
  /** Детали шага */
  detail: string;
  /** История всех шагов */
  steps: AnalysisStep[];
  /** WebSocket подключён */
  isConnected: boolean;
  /** Анализ завершён */
  isCompleted: boolean;
  /** Ошибка */
  error: string | null;
}

const initialState: AnalysisProgressState = {
  percent: 0,
  step: '',
  message: '',
  detail: '',
  steps: [],
  isConnected: false,
  isCompleted: false,
  error: null,
};

export function useAnalysisProgress() {
  const [state, setState] = useState<AnalysisProgressState>(initialState);
  const wsRef = useRef<WebSocket | null>(null);
  const sessionIdRef = useRef<string>('');
  const pingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  /**
   * Генерирует уникальный session ID
   */
  const generateSessionId = useCallback((): string => {
    const id = `analysis_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    sessionIdRef.current = id;
    return id;
  }, []);

  /**
   * Подключается к WebSocket для прослушивания прогресса.
   * Вызвать ПЕРЕД отправкой HTTP-запроса анализа.
   */
  const connect = useCallback((sessionId: string) => {
    // Сброс состояния
    setState({ ...initialState });
    sessionIdRef.current = sessionId;

    // Закрыть предыдущее соединение
    if (wsRef.current) {
      wsRef.current.close();
    }

    let retryCount = 0;
    const maxRetries = 5;

    const attemptConnect = () => {
      // SECURITY: пробрасываем JWT-токен через query-параметр — backend валидирует
      // его перед accept(), без токена соединение закрывается с кодом 1008.
      const token = localStorage.getItem('access_token') || '';
      const wsUrl = `${WS_BASE_URL}/ws/analysis/${encodeURIComponent(sessionId)}?token=${encodeURIComponent(token)}`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        retryCount = 0; // Сброс счётчика при успехе
        setState(prev => ({ ...prev, isConnected: true }));

        // Keepalive ping каждые 25 секунд
        pingIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }));
          }
        }, 25000);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          if (data.type === 'progress') {
            const newStep: AnalysisStep = {
              step: data.step,
              percent: data.percent,
              message: data.message,
              detail: data.detail || '',
              timestamp: data.timestamp,
            };

            setState(prev => ({
              ...prev,
              percent: data.percent,
              step: data.step,
              message: data.message,
              detail: data.detail || '',
              steps: [...prev.steps, newStep],
              error: null,
            }));
          } else if (data.type === 'completed') {
            setState(prev => ({
              ...prev,
              percent: 100,
              message: data.message || 'Анализ завершён',
              isCompleted: true,
            }));
          } else if (data.type === 'error') {
            setState(prev => ({
              ...prev,
              error: data.message,
            }));
          }
          // pong — игнорируем
        } catch {
          // Невалидное сообщение — игнорируем
        }
      };

      ws.onclose = (event) => {
        setState(prev => ({ ...prev, isConnected: false }));
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
          pingIntervalRef.current = null;
        }
        // Retry с exponential backoff если не закрыто намеренно
        if (event.code !== 1000 && retryCount < maxRetries) {
          retryCount++;
          const delay = Math.min(1000 * Math.pow(2, retryCount - 1), 8000);
          retryTimerRef.current = setTimeout(attemptConnect, delay);
        }
      };

      ws.onerror = () => {
        // Ошибки WebSocket не критичны — анализ всё равно идёт через HTTP
        setState(prev => ({ ...prev, isConnected: false }));
      };
    };

    attemptConnect();
  }, []);

  /**
   * Отключиться от WebSocket.
   */
  const disconnect = useCallback(() => {
    if (retryTimerRef.current) {
      clearTimeout(retryTimerRef.current);
      retryTimerRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }
  }, []);

  /**
   * Сбросить состояние прогресса.
   */
  const reset = useCallback(() => {
    disconnect();
    setState({ ...initialState });
    sessionIdRef.current = '';
  }, [disconnect]);

  // Cleanup при размонтировании
  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  return {
    ...state,
    sessionId: sessionIdRef.current,
    generateSessionId,
    connect,
    disconnect,
    reset,
  };
}
