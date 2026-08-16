/**
 * Закрыть сокет, не ругаясь в консоль.
 *
 * `close()` на сокете в состоянии CONNECTING заставляет браузер напечатать
 * «WebSocket is closed before the connection is established» — предупреждение,
 * а не ошибка, но в StrictMode эффект монтируется дважды, и оно появлялось
 * при каждой загрузке страницы. Хуже другое: рукопожатие всё равно доходит до
 * конца, и сервер какое-то время держит соединение, которое никто не читает.
 *
 * Поэтому недооткрытый сокет закрываем после `open`, а не вместо него.
 */
export function closeSocket(ws: WebSocket | null, code?: number, reason?: string): void {
  if (!ws) return;
  const shut = () => {
    try {
      ws.close(code, reason);
    } catch {
      /* сокет уже закрыт — нечего делать */
    }
  };
  if (ws.readyState === WebSocket.CONNECTING) {
    ws.addEventListener('open', shut, { once: true });
    return;
  }
  if (ws.readyState !== WebSocket.CLOSED) shut();
}
