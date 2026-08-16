/**
 * Общая подготовка сквозных тестов.
 *
 * Вход выполняется запросом к API, а не через форму. Причин две: форма
 * входа ограничена по частоте, и десяток тестов исчерпал бы предел, проверяя
 * вовсе не его; а сам вход проверяется отдельным тестом, где ему и место.
 */
import { expect, Page } from '@playwright/test';

export const API = process.env.E2E_API_URL || 'http://localhost:8000';
export const EMAIL = process.env.E2E_EMAIL || 'ui-check@ntfast-test.com';
export const PASSWORD = process.env.E2E_PASSWORD || 'UiCheck!2026';

/** Отвечает ли бэкенд. Без него сквозные тесты бессмысленны. */
export async function backendIsUp(): Promise<boolean> {
  try {
    const response = await fetch(`${API}/health`, { signal: AbortSignal.timeout(3000) });
    return response.ok;
  } catch {
    return false;
  }
}

/**
 * Токен на весь прогон.
 *
 * Вход тоже ограничен по частоте — пять попыток в минуту. Пока каждый тест
 * входил заново, набор исчерпывал предел сам на себе: проверка перебора
 * съедала счётчик, и следующие тесты не могли войти. Один вход на прогон
 * снимает вопрос и заодно ускоряет набор.
 */
let cachedToken: string | null = null;

export async function login(): Promise<string> {
  if (cachedToken) return cachedToken;
  const body = new URLSearchParams({ username: EMAIL, password: PASSWORD });
  const response = await fetch(`${API}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body,
  });
  expect(response.ok, `вход под ${EMAIL} не удался — подготовьте пользователя`).toBeTruthy();
  cachedToken = (await response.json()).access_token;
  return cachedToken as string;
}

/** Положить токен в браузер до первой отрисовки. */
export async function signIn(page: Page): Promise<string> {
  const token = await login();
  await page.addInitScript((value) => {
    localStorage.setItem('access_token', value);
  }, token);
  return token;
}

/** Первый завершённый анализ — тесты не должны зависеть от конкретного id. */
export async function firstCompletedAnalysisId(token: string): Promise<number | null> {
  const response = await fetch(`${API}/api/analyses/?limit=50`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) return null;

  const payload = await response.json();
  const items = Array.isArray(payload) ? payload : payload.items || [];
  const done = items.find((item: any) => item.status === 'completed');
  return done ? done.id : null;
}
