/**
 * Reconstructs the analysis report from what the backend stored.
 *
 * There is exactly one way to render a finished analysis, and this is it.
 * Both entry points — finishing a fresh upload and reopening an old analysis
 * from the list — go through here, so the report a user sees right after the
 * run is byte-for-byte the report they see after a page reload. Previously
 * the fresh path used the synchronous endpoint's response while the reopen
 * path rebuilt its own shape inline, and the two disagreed.
 */
import { analysesAPI, KaspiAnalysisResult } from './api';

/** Analysis row as returned by GET /analyses/{id} (heavy JSON columns included). */
interface StoredAnalysis {
  id: number;
  file_name?: string | null;
  account_owner?: string | null;
  account_number?: string | null;
  account_currency?: string | null;
  total_transactions?: number;
  total_income?: number | null;
  total_expense?: number | null;
  created_at: string;
  completed_at?: string | null;
  fraud_report?: any;
  analytics_result?: any;
  parsed_account_info?: any;
}

/**
 * Результат шага обогащения лежит внутри `analytics_result`: собственной
 * колонки у него нет, а BankAnalyzer кладёт его рядом с аналитикой. У записей,
 * сделанных до появления этого шага, ключа просто нет — тогда секция источника
 * дохода не отрисуется, и это правильнее, чем показать пустую заглушку.
 */
function extractEnrichment(stored: any) {
  return stored?.enrichment ?? null;
}

const EMPTY_ANALYTICS: KaspiAnalysisResult['analytics'] = {
  monthly_breakdown: [],
  category_breakdown: { expense: [], income: [], total_expense: 0, total_income: 0 },
  top_merchants: [],
  top_contacts: [],
  recurring_payments: [],
  anomalies: [],
  foreign_currency: { transactions: [], total_foreign_kzt: 0 },
  financial_health: {
    savings_rate: 0,
    essential_expenses: 0,
    non_essential_expenses: 0,
    essential_ratio: 0,
    balance_trend: 'stable',
    monthly_avg_income: 0,
    monthly_avg_expense: 0,
    financial_buffer_days: 0,
  },
  weekday_analysis: [],
  daily_patterns: [],
};

/**
 * `analytics_result` is whatever BankAnalyzer returned minus the keys stored
 * in their own columns, so the analytics live one level down. Older rows kept
 * them at the top level — accept both rather than silently rendering zeros.
 */
function extractAnalytics(stored: any): KaspiAnalysisResult['analytics'] {
  const raw = stored?.analytics ?? stored ?? {};
  return { ...EMPTY_ANALYTICS, ...raw };
}

export async function buildReportFromAnalysis(analysisId: number): Promise<KaspiAnalysisResult> {
  const [analysis, txResponse] = await Promise.all([
    analysesAPI.getById(analysisId) as unknown as Promise<StoredAnalysis>,
    analysesAPI.getTransactions(analysisId).catch(() => ({ transactions: [] as any[] })),
  ]);

  const account = analysis.parsed_account_info || {};
  const storedAnalytics = analysis.analytics_result || {};
  const analytics = extractAnalytics(storedAnalytics);

  const rawTransactions: any[] = Array.isArray(txResponse?.transactions)
    ? txResponse.transactions
    : [];

  const transactions = rawTransactions.map((tx: any) => ({
    date: tx.transaction_date || tx.date || '',
    amount: Number.parseFloat(tx.amount) || 0,
    type: tx.transaction_type || tx.type || '',
    details: tx.description || tx.details || '',
    category: tx.category || '',
    subcategory: tx.subcategory || '',
    currency: tx.currency || 'KZT',
    original_amount: tx.original_amount ? Number.parseFloat(tx.original_amount) : null,
    original_currency: tx.original_currency || null,
  }));

  const totalIncome = Number(analysis.total_income) || 0;
  const totalExpense = Math.abs(Number(analysis.total_expense) || 0);

  return {
    meta: {
      generated_at: analysis.completed_at || analysis.created_at,
      pdf_file: analysis.file_name || '',
      parser_version: '3.0',
      original_filename: analysis.file_name || undefined,
      analysis_id: analysis.id,
    },
    account: {
      owner: analysis.account_owner || account.owner || '',
      card: account.card_number || account.card || '',
      account_number: analysis.account_number || account.account_number || '',
      currency: analysis.account_currency || account.currency || 'KZT',
      period: account.period || { from: null, to: null },
      balance_start: account.balance_start ?? 0,
      balance_end: account.balance_end ?? 0,
    },
    validation: storedAnalytics.validation || {
      total_transactions: analysis.total_transactions || 0,
      is_valid: true,
      balance_reconciled: null,
      expected: {},
      actual: {},
      differences: {},
      errors: [],
    },
    summary: {
      total_transactions: analysis.total_transactions || 0,
      total_income: totalIncome,
      total_expense: totalExpense,
      net_flow: totalIncome - totalExpense,
      avg_daily_expense: storedAnalytics.summary?.avg_daily_expense ?? 0,
      median_transaction: storedAnalytics.summary?.median_transaction ?? 0,
    },
    transactions,
    analytics,
    // Контакты BankAnalyzer кладёт рядом с analytics, но у старых записей
    // они могли оказаться внутри неё — принимаем оба варианта.
    contacts: storedAnalytics.contacts || (analytics as any).contacts || {},
    enrichment: extractEnrichment(storedAnalytics),
    fraud_report: analysis.fraud_report || null,
  } as KaspiAnalysisResult;
}
