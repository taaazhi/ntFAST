/**
 * Настройки тестов фронтенда.
 *
 * Отдельно от vite.config.ts намеренно: сборка и тесты живут разной жизнью,
 * и правка одного не должна задевать другое.
 */
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    // jsdom нужен там, где код трогает браузерное окружение — разбор потока
    // опирается на TextDecoder, а форматирование чисел на Intl.
    environment: 'jsdom',
    include: ['src/**/*.test.ts', 'src/**/*.test.tsx'],
    // Тихий вывод: в CI важен факт падения и его причина, а не список
    // зелёных строк.
    reporters: 'dot',
  },
});
