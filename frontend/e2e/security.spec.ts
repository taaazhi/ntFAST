/**
 * Защита входа от перебора — проверка, которую можно сделать только живьём.
 *
 * Дефект, который она закрывает, не был виден нигде: ни в типах, ни в
 * тестах, ни при чтении кода. Ограничение частоты работало, но обходилось
 * заголовком «X-Forwarded-For» — адрес клиента подменял uvicorn ещё до
 * приложения, и каждая попытка выглядела приходящей с нового адреса.
 *
 * Тест бьёт по настоящему серверу и потому оставляет след: счётчик после
 * него исчерпан на минуту. Поэтому он один и стоит отдельно от прочих.
 */
import { expect, test } from '@playwright/test';

import { API, backendIsUp } from './fixtures';

/** Заведомо несуществующий пользователь: подбирать нечего, важен сам счёт. */
const VICTIM = 'e2e-bruteforce-probe@ntfast-test.invalid';

async function attempt(headers: Record<string, string> = {}): Promise<number> {
  const response = await fetch(`${API}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded', ...headers },
    body: new URLSearchParams({ username: VICTIM, password: 'wrong-password' }),
  });
  return response.status;
}

test.beforeAll(async () => {
  if (!(await backendIsUp())) {
    test.skip(true, 'бэкенд не отвечает');
  }
});

test('перебор паролей упирается в предел и не обходится заголовком', async () => {
  // Предел для входа — 5 попыток в минуту.
  const straight: number[] = [];
  for (let i = 0; i < 7; i += 1) {
    straight.push(await attempt());
  }

  expect(
    straight.filter((code) => code === 429).length,
    `ограничение не сработало: ${straight.join(', ')}`,
  ).toBeGreaterThan(0);

  // Та же атака с подставным адресом. Пока uvicorn доверял заголовку,
  // каждая строка ниже возвращала 401 — счётчик заводился заново на
  // выдуманный адрес, и предела не существовало вовсе.
  const spoofed: number[] = [];
  for (let i = 1; i <= 3; i += 1) {
    spoofed.push(await attempt({ 'X-Forwarded-For': `9.9.9.${i}` }));
  }

  expect(
    spoofed.every((code) => code === 429),
    `подделка адреса обошла ограничение: ${spoofed.join(', ')}. `
      + 'Запускайте бэкенд с FORWARDED_ALLOW_IPS="" либо включите '
      + 'TRUST_PROXY_HEADERS=true, если перед ним стоит обратный прокси.',
  ).toBeTruthy();
});
