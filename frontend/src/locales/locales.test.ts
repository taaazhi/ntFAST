/**
 * Три локали обязаны совпадать по составу ключей.
 *
 * Правило проекта — «правь все три сразу» — до сих пор держалось только на
 * внимательности. Забытый ключ не роняет сборку и не виден в интерфейсе на
 * том языке, которым пользуешься при разработке: вместо текста показывается
 * сам ключ, и увидит это тот, кто откроет отчёт по-казахски.
 *
 * Для системы, которая обязана одинаково работать на государственном языке,
 * это не косметика. Здесь правило становится проверкой.
 */
import { describe, expect, it } from 'vitest';

import en from './en.json';
import kk from './kk.json';
import ru from './ru.json';

type Tree = Record<string, unknown>;

/** Все пути до листьев: `analyses.report.conclusion.title`. */
function leafPaths(node: Tree, prefix = ''): string[] {
  return Object.entries(node).flatMap(([key, value]) => {
    const path = prefix ? `${prefix}.${key}` : key;
    return value && typeof value === 'object' && !Array.isArray(value)
      ? leafPaths(value as Tree, path)
      : [path];
  });
}

function valueAt(node: Tree, path: string): unknown {
  return path.split('.').reduce<any>((current, key) => current?.[key], node);
}

const LOCALES: Record<string, Tree> = { ru, kk, en };

describe('локали', () => {
  const russian = leafPaths(ru).sort();

  it('русская локаль не пуста', () => {
    expect(russian.length).toBeGreaterThan(100);
  });

  for (const [name, locale] of Object.entries(LOCALES)) {
    if (name === 'ru') continue;

    it(`${name}: тот же набор ключей, что и в русской`, () => {
      const other = leafPaths(locale).sort();

      const missing = russian.filter((path) => !other.includes(path));
      const extra = other.filter((path) => !russian.includes(path));

      expect(
        missing,
        `в ${name}.json не хватает ключей: ${missing.slice(0, 10).join(', ')}`,
      ).toEqual([]);
      expect(
        extra,
        `в ${name}.json есть лишние ключи: ${extra.slice(0, 10).join(', ')}`,
      ).toEqual([]);
    });
  }

  for (const [name, locale] of Object.entries(LOCALES)) {
    it(`${name}: нет пустых строк`, () => {
      const blank = leafPaths(locale).filter((path) => {
        const value = valueAt(locale, path);
        return typeof value === 'string' && value.trim() === '';
      });
      expect(blank, `пустые значения: ${blank.slice(0, 10).join(', ')}`).toEqual([]);
    });
  }

  it('казахская локаль действительно переведена, а не скопирована', () => {
    // Полное совпадение с русским текстом по большинству ключей означало бы,
    // что перевода нет. Отдельные совпадения законны: «ntFAST», «PDF», «IBAN»
    // одинаковы на всех языках.
    const paths = leafPaths(ru);
    const identical = paths.filter((path) => {
      const source = valueAt(ru, path);
      return typeof source === 'string' && source.length > 12
        && valueAt(kk, path) === source;
    });

    expect(identical.length / paths.length).toBeLessThan(0.2);
  });
});
