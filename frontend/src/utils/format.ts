/**
 * Centralized formatting utilities for ntFAST.
 *
 * Keeps currency, date and number formatting consistent across components,
 * locale-aware via i18n language code (kk/ru/en).
 */

/** Map i18n language code → BCP47 locale used by Intl APIs. */
export function intlLocale(lang: string | undefined): string {
  if (lang === 'kk') return 'kk-KZ';
  if (lang === 'en') return 'en-US';
  return 'ru-RU';
}

/** Format a number as KZT currency with locale-aware grouping + ₸ suffix. */
export function formatCurrency(value: number | null | undefined, lang: string | undefined): string {
  const safe = typeof value === 'number' && Number.isFinite(value) ? value : 0;
  const locale = intlLocale(lang);
  return new Intl.NumberFormat(locale).format(Math.round(safe)) + ' ₸';
}

/** Format a number with locale-aware grouping (no currency symbol). */
export function formatNumber(value: number | null | undefined, lang: string | undefined): string {
  const safe = typeof value === 'number' && Number.isFinite(value) ? value : 0;
  return new Intl.NumberFormat(intlLocale(lang)).format(safe);
}

/** Format an ISO 8601 datetime as DD.MM.YYYY HH:mm (ru/kk) or M/D/YYYY h:mm (en). */
export function formatDateTime(iso: string | null | undefined, lang: string | undefined): string {
  if (!iso) return '—';
  // Ensure trailing 'Z' for UTC interpretation in the browser
  const safeIso = iso.endsWith('Z') || /[+-]\d{2}:?\d{2}$/.test(iso) ? iso : `${iso}Z`;
  const d = new Date(safeIso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString(intlLocale(lang), {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/** Format an ISO date (without time component). */
export function formatDate(iso: string | null | undefined, lang: string | undefined): string {
  if (!iso) return '—';
  const safeIso = iso.endsWith('Z') || /[+-]\d{2}:?\d{2}$/.test(iso) ? iso : `${iso}Z`;
  const d = new Date(safeIso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleDateString(intlLocale(lang));
}

/** Truncate a string to maxLen, adding ellipsis. */
export function truncate(text: string | null | undefined, maxLen: number = 30): string {
  if (!text) return '';
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen - 1) + '…';
}
