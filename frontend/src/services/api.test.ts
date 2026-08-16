/**
 * Разбор потока заключения.
 *
 * Заключение приходит кадрами SSE, и сеть режет поток где придётся: кадр
 * может прийти половиной, две половины — в разных чтениях, несколько кадров —
 * одним куском. Ошибка здесь не роняет страницу, а тихо теряет часть текста
 * заключения — того самого, что ложится в дело.
 */
import { describe, expect, it } from 'vitest';

import { parseStreamFrames } from './api';

const frame = (payload: object) => `data: ${JSON.stringify(payload)}\n\n`;

describe('parseStreamFrames', () => {
  it('разбирает один целый кадр', () => {
    const { events, rest } = parseStreamFrames(frame({ type: 'chunk', text: 'За период' }));
    expect(events).toEqual([{ type: 'chunk', text: 'За период' }]);
    expect(rest).toBe('');
  });

  it('разбирает несколько кадров, пришедших вместе', () => {
    const buffer = frame({ type: 'chunk', text: 'А' }) + frame({ type: 'chunk', text: 'Б' });
    const { events, rest } = parseStreamFrames(buffer);
    expect(events.map((e) => e.text)).toEqual(['А', 'Б']);
    expect(rest).toBe('');
  });

  it('придерживает неполный кадр до следующего чтения', () => {
    // Так это и приходит: «data: {"type":"chunk","te» — и всё, дальше пусто.
    const partial = 'data: {"type":"chunk","te';
    const { events, rest } = parseStreamFrames(partial);
    expect(events).toEqual([]);
    expect(rest).toBe(partial);
  });

  it('склеивает кадр, разорванный между чтениями', () => {
    const whole = frame({ type: 'chunk', text: 'Признаки' });
    const cut = Math.floor(whole.length / 2);

    const first = parseStreamFrames(whole.slice(0, cut));
    expect(first.events).toEqual([]);

    const second = parseStreamFrames(first.rest + whole.slice(cut));
    expect(second.events).toEqual([{ type: 'chunk', text: 'Признаки' }]);
    expect(second.rest).toBe('');
  });

  it('целый кадр отдаёт сразу, даже если за ним начался следующий', () => {
    const buffer = frame({ type: 'chunk', text: 'Первый' }) + 'data: {"type":"chun';
    const { events, rest } = parseStreamFrames(buffer);
    expect(events).toEqual([{ type: 'chunk', text: 'Первый' }]);
    expect(rest).toBe('data: {"type":"chun');
  });

  it('битый кадр не уносит с собой соседние', () => {
    // Текст заключения дороже одного кадра: потерять абзац из-за сбойного
    // байта хуже, чем показать заключение с пропуском.
    const buffer = 'data: {не json}\n\n' + frame({ type: 'chunk', text: 'Целый' });
    const { events } = parseStreamFrames(buffer);
    expect(events).toEqual([{ type: 'chunk', text: 'Целый' }]);
  });

  it('строки без «data:» пропускаются', () => {
    // Сервер шлёт комментарии-пинги вида «: keep-alive».
    const buffer = ': keep-alive\n\n' + frame({ type: 'chunk', text: 'Текст' });
    const { events } = parseStreamFrames(buffer);
    expect(events).toHaveLength(1);
  });

  it('итоговый кадр разбирается вместе с признаком достоверности', () => {
    const done = {
      type: 'done', text: 'Заключение', is_trustworthy: false,
      invented_numbers: ['158'], truncated: false, citations: [],
    };
    const { events } = parseStreamFrames(frame(done));
    expect(events[0].is_trustworthy).toBe(false);
    expect(events[0].invented_numbers).toEqual(['158']);
  });

  it('пустой буфер не даёт событий', () => {
    expect(parseStreamFrames('')).toEqual({ events: [], rest: '' });
  });
});
