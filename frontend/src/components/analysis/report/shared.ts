/**
 * Общее для секций отчёта.
 *
 * Отчёт раньше был одним файлом на 1774 строки, и на вопрос «где рисуется
 * антифрод-вкладка» приходилось листать весь файл. Теперь каждая вкладка —
 * отдельный компонент в этой папке, а то, что им нужно вместе, лежит здесь.
 */
import { KaspiAnalysisResult } from '../../../services/api';

export type SectionId = 'overview' | 'financial' | 'antifraud' | 'details' | 'conclusions';
export type TxSortField = 'date' | 'details' | 'category' | 'amount';

/** Отчёт целиком — то, что собрал reportBuilder из сохранённого анализа. */
export type Report = KaspiAnalysisResult;
/** Результат антифрод-движка. Может отсутствовать у старых анализов. */
export type FraudReport = KaspiAnalysisResult['fraud_report'];

/** Код языка i18n → локаль для Intl. */
export function intlLocale(lang: string): string {
  if (lang === 'kk') return 'kk-KZ';
  if (lang === 'en') return 'en-US';
  return 'ru-RU';
}

export const CHART_COLORS = [
  '#1a73e8', '#4285f4', '#f9ab00', '#ea4335',
  '#0891b2', '#5f6368', '#8ab4f8', '#1557b0',
];

/** Число из поля, которое может быть массивом, числом или пустым. */
export function safeLen(val: any): number {
  if (Array.isArray(val)) return val.length;
  if (typeof val === 'number') return val;
  return 0;
}

/** Форматирование суммы в тенге — прокидывается в секции из родителя. */
export type FormatCurrency = (value: number) => string;
