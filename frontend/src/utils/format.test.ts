/**
 * Проверки форматирования — там, где уже ломалось.
 *
 * Бэкенд отдаёт доли (0..1) и знаковые суммы, фронтенд превращает их в
 * текст. На этой границе случились самые заметные ошибки проекта: норма
 * сбережений умножалась на сто дважды и 20% показывались как 2000%, а
 * чистый поток печатался по модулю, из-за чего убыток выглядел прибылью.
 *
 * Ни одна из них не роняет сборку и не видна в типах — только глазами на
 * готовом экране. Поэтому здесь.
 */
import { describe, expect, it } from 'vitest';

import { formatCurrency, formatDate, formatDateTime, formatNumber, intlLocale, truncate } from './format';

/** В разных средах Intl ставит разные пробелы-разделители. */
const digits = (text: string) => text.replace(/[^\d,.-]/g, '');

describe('formatCurrency', () => {
  it('ставит символ тенге', () => {
    expect(formatCurrency(1000, 'ru')).toContain('₸');
  });

  it('разделяет разряды', () => {
    expect(digits(formatCurrency(5540137, 'ru'))).toBe('5540137');
  });

  it('округляет до целых тенге', () => {
    expect(digits(formatCurrency(1234.56, 'ru'))).toBe('1235');
  });

  it('сохраняет знак отрицательной суммы', () => {
    // Убыток, напечатанный по модулю, читается как прибыль. Именно так
    // «чистый поток −18 530 ₸» показывался положительным.
    expect(formatCurrency(-18530, 'ru')).toMatch(/^-|−/);
  });

  it('не падает на null, undefined и NaN', () => {
    // Данных может не быть — но пустой экран хуже нуля.
    for (const value of [null, undefined, NaN, Infinity]) {
      expect(formatCurrency(value as number, 'ru')).toContain('₸');
    }
  });
});

describe('intlLocale', () => {
  it('переводит коды языков в локали Intl', () => {
    expect(intlLocale('kk')).toBe('kk-KZ');
    expect(intlLocale('en')).toBe('en-US');
    expect(intlLocale('ru')).toBe('ru-RU');
  });

  it('неизвестный язык не ломает форматирование', () => {
    expect(intlLocale(undefined)).toBe('ru-RU');
    expect(() => formatCurrency(100, 'tr')).not.toThrow();
  });
});

describe('formatNumber', () => {
  it('не приписывает валюту', () => {
    expect(formatNumber(1320, 'ru')).not.toContain('₸');
    expect(digits(formatNumber(1320, 'ru'))).toBe('1320');
  });

  it('сохраняет дробную часть', () => {
    expect(digits(formatNumber(12.4, 'ru'))).toBe('12,4');
  });
});

describe('formatDateTime', () => {
  it('пустое значение показывает прочерком, а не датой начала эпохи', () => {
    expect(formatDateTime(null, 'ru')).toBe('—');
    expect(formatDateTime('', 'ru')).toBe('—');
  });

  it('нечитаемая дата не превращается в «Invalid Date»', () => {
    expect(formatDateTime('позавчера', 'ru')).toBe('—');
  });

  it('дату без часового пояса читает как UTC', () => {
    // Бэкенд отдаёт naive-время. Без явного UTC браузер трактует его как
    // местное, и отметка уезжает на часы — в журнале действий это заметно.
    const withZ = formatDateTime('2026-08-16T20:42:00Z', 'ru');
    const without = formatDateTime('2026-08-16T20:42:00', 'ru');
    expect(without).toBe(withZ);
  });
});

describe('formatDate', () => {
  it('обрабатывает пустое значение', () => {
    expect(formatDate(undefined, 'ru')).toBe('—');
  });
});

describe('truncate', () => {
  it('короткую строку оставляет как есть', () => {
    expect(truncate('Magnum', 30)).toBe('Magnum');
  });

  it('длинную обрезает с многоточием', () => {
    const long = 'ТОО КАЗАХСТАНСКАЯ ТОРГОВО-ПРОМЫШЛЕННАЯ КОМПАНИЯ';
    const short = truncate(long, 20);
    expect(short).toHaveLength(20);
    expect(short.endsWith('…')).toBe(true);
  });

  it('пустое значение не роняет вывод', () => {
    expect(truncate(null)).toBe('');
    expect(truncate(undefined)).toBe('');
  });
});
