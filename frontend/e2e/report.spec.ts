/**
 * Отчёт: то, что ломалось на стыке фронтенда и бэкенда.
 *
 * Каждый тест здесь написан под конкретный случившийся дефект, а не «на
 * всякий случай». Сквозные тесты дороги, и набор из них должен окупаться.
 */
import { expect, test } from '@playwright/test';

import { backendIsUp, firstCompletedAnalysisId, signIn } from './fixtures';

let analysisId: number | null = null;

test.beforeAll(async () => {
  if (!(await backendIsUp())) {
    test.skip(true, 'бэкенд не отвечает — сквозные тесты пропущены');
  }
});

test.beforeEach(async ({ page }) => {
  const token = await signIn(page);
  if (analysisId === null) {
    analysisId = await firstCompletedAnalysisId(token);
  }
  test.skip(analysisId === null, 'нет ни одного завершённого анализа');
});

test('отчёт открывается по ссылке', async ({ page }) => {
  // Тот самый дефект: эффект в StrictMode монтировался дважды, отменял сам
  // себя, и отчёт не появлялся — при том что запрос к серверу проходил
  // успешно. Ни типы, ни сборка, ни консоль этого не показывали.
  await page.goto(`/analyses?view=${analysisId}`);

  await expect(page.getByText('ntFAST Risk Score')).toBeVisible({ timeout: 60_000 });
  expect(page.url()).toContain(`view=${analysisId}`);
});

test('закрытие отчёта убирает его из адреса', async ({ page }) => {
  // Иначе ссылка «на список» открывала бы отчёт, и вернуться к списку было
  // бы нельзя без правки адреса руками.
  await page.goto(`/analyses?view=${analysisId}`);
  await expect(page.getByText('ntFAST Risk Score')).toBeVisible({ timeout: 60_000 });

  await page.getByRole('button', { name: 'Закрыть' }).click();

  await expect(page.getByText('ntFAST Risk Score')).toBeHidden();
  await expect(page).toHaveURL(/\/analyses(?!.*view=)/, { timeout: 15_000 });
});

test('в отчёте нет непереведённых ключей', async ({ page }) => {
  // Забытый ключ показывается как «analyses.report.conclusion.title» и
  // виден только тому, кто открыл отчёт на этом языке. Модульный тест
  // сверяет наборы ключей, этот — что до экрана дошёл текст.
  await page.goto(`/analyses?view=${analysisId}`);
  await expect(page.getByText('ntFAST Risk Score')).toBeVisible({ timeout: 60_000 });

  const raw = await page.evaluate(
    () => (document.body.innerText.match(/\b[a-z]+(\.[a-zA-Z0-9_]+){2,}\b/g) || [])
      .filter((s) => !s.includes('.pdf') && !s.includes('.csv') && !s.includes('.xlsx')),
  );
  expect(raw, `на экране остались ключи: ${raw.slice(0, 5).join(', ')}`).toEqual([]);
});

test('заключение и вопросы агента есть в разделе выводов', async ({ page }) => {
  await page.goto(`/analyses?view=${analysisId}`);
  await expect(page.getByText('ntFAST Risk Score')).toBeVisible({ timeout: 60_000 });

  await page.getByRole('button', { name: 'Выводы' }).click();

  await expect(page.getByText('Заключение по делу')).toBeVisible();
  await expect(page.getByText('Спросить по выписке')).toBeVisible();
});

test('чистый поток показан со знаком', async ({ page }) => {
  // Убыток, напечатанный по модулю, читается как прибыль — так и было,
  // пока formatCurrency вызывали с Math.abs и пустым префиксом.
  await page.goto(`/analyses?view=${analysisId}`);
  await expect(page.getByText('ntFAST Risk Score')).toBeVisible({ timeout: 60_000 });

  const netFlow = await page.evaluate(() => {
    const text = document.body.innerText;
    const match = text.match(/Чистый поток\s*\n\s*([^\n]+)/);
    return match ? match[1].trim() : null;
  });

  expect(netFlow, 'блок «Чистый поток» не найден').not.toBeNull();
  expect(netFlow, `знак потерян: «${netFlow}»`).toMatch(/^[+\-−]/);
});
