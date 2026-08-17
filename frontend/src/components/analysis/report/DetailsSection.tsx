/** Вкладка «Детали»: таблица транзакций с поиском, фильтром и сортировкой. */
import { motion } from 'framer-motion';
import { useTranslation } from 'react-i18next';
import { AlertTriangle, ChevronDown, Fingerprint, FileText, ArrowUpDown } from 'lucide-react';
import { Report, FraudReport, FormatCurrency, TxSortField, intlLocale } from './shared';

interface Props {
  result: Report;
  fraud: FraudReport;
  formatCurrency: FormatCurrency;
  showAllTransactions: boolean;
  setShowAllTransactions: (v: boolean) => void;
  txSearch: string;
  setTxSearch: (v: string) => void;
  txTypeFilter: 'all' | 'income' | 'expense';
  setTxTypeFilter: (v: 'all' | 'income' | 'expense') => void;
  txSort: { field: TxSortField; dir: 'asc' | 'desc' };
  toggleTxSort: (field: TxSortField) => void;
}

export function DetailsSection({
  result, fraud, formatCurrency,
  showAllTransactions, setShowAllTransactions,
  txSearch, setTxSearch, txTypeFilter, setTxTypeFilter, txSort, toggleTxSort,
}: Props) {
  const { t, i18n } = useTranslation();
  const locale = intlLocale(i18n.language);
  return (
              <motion.div
                key="details"
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}
                className="space-y-6"
              >
                {/* Account profile info (from fraud engine) */}
                {fraud?.account_profile && (
                  <div className="p-5 bg-gradient-to-br from-blue-50 to-blue-50 dark:from-blue-900/20 dark:to-blue-900/20 rounded-2xl border border-blue-200/50 dark:border-blue-800/40">
                    <h3 className="text-sm font-semibold text-blue-700 dark:text-blue-300 mb-3 flex items-center gap-2">
                      <Fingerprint className="w-4 h-4" />
                      {t('analyses.report.accountProfile.title')}
                    </h3>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                      <div>
                        <span className="text-gray-500 dark:text-gray-400">{t('analyses.report.accountProfile.type')}:</span>
                        <span className="ml-1 font-medium text-gray-900 dark:text-white capitalize">
                          {fraud.account_profile.account_type?.replace('_', ' ') || t('analyses.report.accountProfile.unknown')}
                        </span>
                      </div>
                      <div>
                        <span className="text-gray-500 dark:text-gray-400">{t('analyses.report.accountProfile.avgIncome')}:</span>
                        <span className="ml-1 font-medium text-gray-900 dark:text-white">
                          {formatCurrency(fraud.account_profile.avg_monthly_income || 0)}
                        </span>
                      </div>
                      <div>
                        <span className="text-gray-500 dark:text-gray-400">{t('analyses.report.accountProfile.avgExpense')}:</span>
                        <span className="ml-1 font-medium text-gray-900 dark:text-white">
                          {formatCurrency(fraud.account_profile.avg_monthly_expense || 0)}
                        </span>
                      </div>
                      <div>
                        <span className="text-gray-500 dark:text-gray-400">{t('analyses.report.accountProfile.regularity')}:</span>
                        <span className="ml-1 font-medium text-gray-900 dark:text-white">
                          {((fraud.account_profile.income_regularity_score || 0) * 100).toFixed(0)}%
                        </span>
                      </div>
                    </div>
                  </div>
                )}

                <div className="flex items-center justify-between flex-wrap gap-3">
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                    <FileText className="w-5 h-5 text-blue-500" />
                    {t('analyses.report.transactions.all', { count: result.transactions?.length || 0 })}
                  </h3>
                  {/* Search + type filter */}
                  <div className="flex items-center gap-2 flex-wrap">
                    <input
                      type="text"
                      value={txSearch}
                      onChange={(e) => setTxSearch(e.target.value)}
                      placeholder={t('analyses.report.transactions.searchPlaceholder') || 'Search by description / category…'}
                      aria-label={t('analyses.report.transactions.searchPlaceholder') || 'Search transactions'}
                      className="px-3 py-1.5 text-sm rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-400"
                      style={{ minWidth: 220 }}
                    />
                    <select
                      value={txTypeFilter}
                      onChange={(e) => setTxTypeFilter(e.target.value as 'all' | 'income' | 'expense')}
                      aria-label={t('analyses.report.transactions.typeFilter') || 'Type filter'}
                      className="px-3 py-1.5 text-sm rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                    >
                      <option value="all">{t('analyses.report.transactions.typeAll') || 'All'}</option>
                      <option value="income">{t('analyses.report.charts.income') || 'Income'}</option>
                      <option value="expense">{t('analyses.report.charts.expense') || 'Expense'}</option>
                    </select>
                    {(txSearch || txTypeFilter !== 'all') && (
                      <button
                        onClick={() => { setTxSearch(''); setTxTypeFilter('all'); }}
                        className="text-xs text-blue-600 dark:text-blue-400 hover:underline px-2"
                      >
                        {t('common.reset') || 'Reset'}
                      </button>
                    )}
                  </div>
                </div>

                {result.transactions && result.transactions.length > 0 ? (() => {
                  // Apply search + type filter
                  const needle = txSearch.trim().toLowerCase();
                  const filtered = result.transactions.filter((tx: any) => {
                    if (txTypeFilter === 'income' && tx.amount < 0) return false;
                    if (txTypeFilter === 'expense' && tx.amount >= 0) return false;
                    if (!needle) return true;
                    const desc = String(tx.details || '').toLowerCase();
                    const cat = String(tx.category || '').toLowerCase();
                    return desc.includes(needle) || cat.includes(needle);
                  });

                  // Sort the whole filtered set BEFORE slicing, so "sort by
                  // amount" surfaces the largest transaction in the statement,
                  // not merely the largest among the first 50 rows.
                  const dir = txSort.dir === 'asc' ? 1 : -1;
                  const sorted = [...filtered].sort((a: any, b: any) => {
                    switch (txSort.field) {
                      case 'amount':
                        return ((a.amount ?? 0) - (b.amount ?? 0)) * dir;
                      case 'details':
                        return String(a.details || '').localeCompare(String(b.details || ''), locale) * dir;
                      case 'category':
                        return String(a.category || '').localeCompare(String(b.category || ''), locale) * dir;
                      case 'date':
                      default: {
                        const ta = new Date(a.date).getTime() || 0;
                        const tb = new Date(b.date).getTime() || 0;
                        return (ta - tb) * dir;
                      }
                    }
                  });
                  const visibleSlice = showAllTransactions ? sorted : sorted.slice(0, 50);
                  return (
                <div className="overflow-hidden rounded-2xl border border-gray-200/50 dark:border-gray-700/40">
                  {/* Result count + Show all toggle */}
                  <div className="flex items-center justify-between px-4 py-2 bg-gray-50 dark:bg-gray-800/60 border-b border-gray-200/50 dark:border-gray-700/40 text-xs text-gray-500 dark:text-gray-400">
                    <span>
                      {filtered.length === result.transactions.length
                        ? `${filtered.length}`
                        : `${filtered.length} / ${result.transactions.length}`}
                    </span>
                    {filtered.length > 50 && (
                      <button
                        onClick={() => setShowAllTransactions(!showAllTransactions)}
                        className="text-blue-600 dark:text-blue-400 font-medium hover:text-blue-700 flex items-center gap-1"
                      >
                        {showAllTransactions ? t('analyses.report.transactions.showFirst50') : t('analyses.report.transactions.showAll')}
                        <ChevronDown className={`w-3.5 h-3.5 transition-transform ${showAllTransactions ? 'rotate-180' : ''}`} />
                      </button>
                    )}
                  </div>
                  <div className="max-h-[600px] overflow-y-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-50 dark:bg-gray-800/80 sticky top-0 z-10">
                        <tr>
                          <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase">#</th>
                          {([
                            { field: 'date' as const, label: t('analyses.report.transactions.dateCol'), align: 'left' },
                            { field: 'details' as const, label: t('analyses.report.transactions.descriptionCol'), align: 'left' },
                            { field: 'category' as const, label: t('analyses.report.transactions.categoryCol'), align: 'left' },
                            { field: 'amount' as const, label: t('analyses.report.transactions.amountCol'), align: 'right' },
                          ]).map(col => {
                            const active = txSort.field === col.field;
                            return (
                              <th
                                key={col.field}
                                scope="col"
                                aria-sort={active ? (txSort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}
                                className={`px-4 py-3 text-${col.align} text-xs font-semibold uppercase select-none cursor-pointer transition-colors ${
                                  active
                                    ? 'text-blue-600 dark:text-blue-400'
                                    : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                                }`}
                                onClick={() => toggleTxSort(col.field)}
                              >
                                <button
                                  type="button"
                                  className={`inline-flex items-center gap-1 uppercase ${col.align === 'right' ? 'flex-row-reverse' : ''}`}
                                  aria-label={`${col.label} — ${t('analyses.report.transactions.sortBy') || 'sort'}`}
                                >
                                  {col.label}
                                  <ArrowUpDown
                                    className={`w-3 h-3 transition-transform ${
                                      active ? 'opacity-100' : 'opacity-30'
                                    } ${active && txSort.dir === 'asc' ? 'rotate-180' : ''}`}
                                  />
                                </button>
                              </th>
                            );
                          })}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100 dark:divide-gray-800/50">
                        {visibleSlice.map((tx: any, i: number) => (
                          <tr
                            key={i}
                            className="hover:bg-gray-50/80 dark:hover:bg-gray-800/30 transition-colors"
                          >
                            <td className="px-4 py-3 text-gray-400 text-xs">{i + 1}</td>
                            <td className="px-4 py-3 text-gray-600 dark:text-gray-400 whitespace-nowrap">
                              {new Date(tx.date).toLocaleDateString(locale)}
                            </td>
                            <td className="px-4 py-3 text-gray-900 dark:text-white max-w-xs truncate">
                              {tx.details}
                            </td>
                            <td className="px-4 py-3">
                              <span className="px-2 py-0.5 rounded-full text-xs bg-gray-100 dark:bg-gray-700/50 text-gray-600 dark:text-gray-400">
                                {tx.category}
                              </span>
                            </td>
                            <td className={`px-4 py-3 text-right font-semibold whitespace-nowrap ${
                              tx.amount >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
                            }`}>
                              {tx.amount >= 0 ? '+' : ''}{formatCurrency(tx.amount)}
                            </td>
                          </tr>
                        ))}
                        {visibleSlice.length === 0 && (
                          <tr>
                            <td colSpan={5} className="px-4 py-8 text-center text-sm text-gray-500 dark:text-gray-400">
                              {t('analyses.report.transactions.noMatch') || 'No transactions match the filter'}
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
                  );
                })() : (
                  <div className="text-center py-12 bg-gray-50 dark:bg-gray-800/30 rounded-2xl border border-gray-200/50 dark:border-gray-700/40">
                    <FileText className="w-12 h-12 text-gray-300 dark:text-gray-700 mx-auto mb-3" />
                    <p className="text-gray-500 dark:text-gray-400">{t('analyses.report.transactions.noTransactions')}</p>
                    <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">{t('analyses.report.transactions.infoInAntifraud')}</p>
                  </div>
                )}

                {/* Anomalies */}
                {result.analytics?.anomalies && result.analytics.anomalies.length > 0 && (
                  <div className="p-6 bg-yellow-50 dark:bg-yellow-900/20 rounded-2xl border border-yellow-200/50 dark:border-yellow-800/40">
                    <h3 className="text-lg font-semibold text-yellow-700 dark:text-yellow-400 mb-3 flex items-center gap-2">
                      <AlertTriangle className="w-5 h-5" />
                      {t('analyses.report.transactions.anomalies', { count: result.analytics.anomalies.length })}
                    </h3>
                    <div className="space-y-2">
                      {result.analytics.anomalies.map((anomaly, i) => (
                        <div key={i} className="p-3 bg-white/80 dark:bg-gray-800/50 rounded-xl text-sm flex items-start gap-3 border border-yellow-200/50 dark:border-yellow-800/30">
                          <AlertTriangle className="w-4 h-4 text-yellow-500 flex-shrink-0 mt-0.5" />
                          <div>
                            <span className="font-medium text-gray-900 dark:text-white">{anomaly.type}</span>
                            {anomaly.date && <span className="text-gray-500 ml-2">{anomaly.date}</span>}
                            {anomaly.amount && <span className="text-gray-500 ml-2">{formatCurrency(anomaly.amount)}</span>}
                            {anomaly.details && <p className="text-xs text-gray-500 mt-0.5">{anomaly.details}</p>}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </motion.div>
  );
}
