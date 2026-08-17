/** Вкладка «Финансы»: месячные обороты, категории, топ-мерчанты. */
import { motion } from 'framer-motion';
import { useTranslation } from 'react-i18next';
import { Calendar, TrendingUp, Store, PieChart as PieChartIcon, Users, Repeat, Globe, Activity } from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  AreaChart, Area, PieChart, Pie, Cell,
} from 'recharts';
import { Report, FormatCurrency, CHART_COLORS, intlLocale } from './shared';

interface Props {
  result: Report;
  formatCurrency: FormatCurrency;
}

export function FinancialSection({ result, formatCurrency }: Props) {
  const { t, i18n } = useTranslation();
  const locale = intlLocale(i18n.language);
  // Периодичность приходит кодом ("monthly"/"bi-weekly"/…); переводим ключом,
  // а не литералом — иначе казахская и английская версии показали бы англ. код.
  const freqKey = (f: string) =>
    (({ monthly: 'freqMonthly', weekly: 'freqWeekly', 'bi-weekly': 'freqBiWeekly', frequent: 'freqFrequent' } as Record<string, string>)[f]) || 'freqUnknown';
  const shortDate = (iso: string) => {
    const d = new Date(iso);
    return isNaN(d.getTime()) ? iso : d.toLocaleDateString(locale, { day: '2-digit', month: 'short' });
  };
  return (
              <motion.div
                key="financial"
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}
                className="space-y-8"
              >
                {/* Financial summary KPIs (always shown) */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {[
                    { label: t('analyses.report.kpi.totalIncome'), value: result.summary?.total_income || 0, color: 'green', prefix: '+' },
                    { label: t('analyses.report.kpi.totalExpense'), value: result.summary?.total_expense || 0, color: 'red', prefix: '-' },
                    // Знак обязателен: значение печатается по модулю, и без
                    // префикса отрицательный поток читался как положительный.
                    { label: t('analyses.report.kpi.netFlow'), value: result.summary?.net_flow || 0, color: (result.summary?.net_flow || 0) >= 0 ? 'blue' : 'red', prefix: (result.summary?.net_flow || 0) >= 0 ? '+' : '−' },
                    { label: t('analyses.report.kpi.avgDailyExpenseShort'), value: result.summary?.avg_daily_expense || 0, color: 'slate', prefix: '' },
                  ].map((kpi) => {
                    const colors: Record<string, string> = {
                      green: 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300 border-green-200/50 dark:border-green-800/40',
                      red: 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 border-red-200/50 dark:border-red-800/40',
                      blue: 'bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300 border-blue-200/50 dark:border-blue-800/40',
                      slate: 'bg-slate-50 dark:bg-slate-900/20 text-slate-700 dark:text-slate-300 border-slate-200/50 dark:border-slate-800/40',
                    };
                    return (
                      <div key={kpi.label} className={`p-4 rounded-xl border ${colors[kpi.color]}`}>
                        <p className="text-xs font-medium opacity-70 mb-1">{kpi.label}</p>
                        <p className="text-xl font-bold">{kpi.prefix}{formatCurrency(Math.abs(kpi.value))}</p>
                      </div>
                    );
                  })}
                </div>

                {/* Monthly breakdown chart */}
                {result.analytics?.monthly_breakdown && result.analytics.monthly_breakdown.length > 0 && (
                  <div className="p-6 bg-white dark:bg-gray-800/50 rounded-2xl border border-gray-200/50 dark:border-gray-700/40">
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                      <TrendingUp className="w-5 h-5 text-blue-500" />
                      {t('analyses.report.charts.monthlyDynamics')}
                    </h3>
                    <ResponsiveContainer width="100%" height={300}>
                      <AreaChart data={result.analytics.monthly_breakdown}>
                        <defs>
                          <linearGradient id="colorIncome" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#34a853" stopOpacity={0.3}/>
                            <stop offset="95%" stopColor="#34a853" stopOpacity={0}/>
                          </linearGradient>
                          <linearGradient id="colorExpense" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#ea4335" stopOpacity={0.3}/>
                            <stop offset="95%" stopColor="#ea4335" stopOpacity={0}/>
                          </linearGradient>
                        </defs>
                        <XAxis dataKey="month_name" tick={{ fontSize: 12 }} />
                        <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => `${(v / 1000).toFixed(0)}K`} />
                        <Tooltip
                          contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 20px rgba(0,0,0,0.15)', background: 'rgba(255,255,255,0.95)' }}
                          formatter={(value: number, name: string) => [formatCurrency(value), name === 'income' ? t('analyses.report.charts.income') : t('analyses.report.charts.expense')]}
                        />
                        <Area type="monotone" dataKey="income" stroke="#34a853" fill="url(#colorIncome)" strokeWidth={2.5} name="income" />
                        <Area type="monotone" dataKey="expense" stroke="#ea4335" fill="url(#colorExpense)" strokeWidth={2.5} name="expense" />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                )}

                {/* Category breakdown */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {/* Expense categories */}
                  {result.analytics?.category_breakdown?.expense && result.analytics.category_breakdown.expense.length > 0 && (
                    <div className="p-6 bg-white dark:bg-gray-800/50 rounded-2xl border border-gray-200/50 dark:border-gray-700/40">
                      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                        <PieChartIcon className="w-5 h-5 text-red-500" />
                        {t('analyses.report.charts.expenseCategories')}
                      </h3>
                      <ResponsiveContainer width="100%" height={250}>
                        <PieChart>
                          <Pie
                            data={result.analytics.category_breakdown.expense.slice(0, 8)}
                            cx="50%"
                            cy="50%"
                            outerRadius={90}
                            innerRadius={50}
                            paddingAngle={2}
                            dataKey="amount"
                            nameKey="category"
                          >
                            {result.analytics.category_breakdown.expense.slice(0, 8).map((_, i) => (
                              <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                            ))}
                          </Pie>
                          <Tooltip
                            contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.15)' }}
                            formatter={(value: number) => [formatCurrency(value)]}
                          />
                        </PieChart>
                      </ResponsiveContainer>
                      <div className="space-y-2 mt-2">
                        {result.analytics.category_breakdown.expense.slice(0, 6).map((cat, i) => (
                          <div key={cat.category} className="flex items-center justify-between text-sm">
                            <div className="flex items-center gap-2">
                              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: CHART_COLORS[i % CHART_COLORS.length] }} />
                              <span className="text-gray-600 dark:text-gray-400">{cat.category}</span>
                            </div>
                            <span className="font-medium text-gray-900 dark:text-white">{formatCurrency(cat.amount)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Income categories */}
                  {result.analytics?.category_breakdown?.income && result.analytics.category_breakdown.income.length > 0 && (
                    <div className="p-6 bg-white dark:bg-gray-800/50 rounded-2xl border border-gray-200/50 dark:border-gray-700/40">
                      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                        <PieChartIcon className="w-5 h-5 text-green-500" />
                        {t('analyses.report.charts.incomeCategories')}
                      </h3>
                      <ResponsiveContainer width="100%" height={250}>
                        <PieChart>
                          <Pie
                            data={result.analytics.category_breakdown.income.slice(0, 8)}
                            cx="50%"
                            cy="50%"
                            outerRadius={90}
                            innerRadius={50}
                            paddingAngle={2}
                            dataKey="amount"
                            nameKey="category"
                          >
                            {result.analytics.category_breakdown.income.slice(0, 8).map((_, i) => (
                              <Cell key={i} fill={CHART_COLORS[(i + 3) % CHART_COLORS.length]} />
                            ))}
                          </Pie>
                          <Tooltip
                            contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.15)' }}
                            formatter={(value: number) => [formatCurrency(value)]}
                          />
                        </PieChart>
                      </ResponsiveContainer>
                      <div className="space-y-2 mt-2">
                        {result.analytics.category_breakdown.income.slice(0, 6).map((cat, i) => (
                          <div key={cat.category} className="flex items-center justify-between text-sm">
                            <div className="flex items-center gap-2">
                              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: CHART_COLORS[(i + 3) % CHART_COLORS.length] }} />
                              <span className="text-gray-600 dark:text-gray-400">{cat.category}</span>
                            </div>
                            <span className="font-medium text-gray-900 dark:text-white">{formatCurrency(cat.amount)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* Top merchants */}
                {result.analytics?.top_merchants && result.analytics.top_merchants.length > 0 && (
                  <div className="p-6 bg-white dark:bg-gray-800/50 rounded-2xl border border-gray-200/50 dark:border-gray-700/40">
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                      <Store className="w-5 h-5 text-slate-500" />
                      {t('analyses.report.charts.topMerchants')}
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                      {result.analytics.top_merchants.slice(0, 9).map((merchant, i) => (
                        <div
                          key={merchant.merchant}
                          className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/30 rounded-xl"
                        >
                          <div className="flex items-center gap-3 min-w-0">
                            <div className="w-8 h-8 rounded-lg bg-slate-100 dark:bg-slate-900/30 flex items-center justify-center flex-shrink-0">
                              <span className="text-sm font-bold text-slate-600 dark:text-slate-400">
                                {i + 1}
                              </span>
                            </div>
                            <div className="min-w-0">
                              <p className="text-sm font-medium text-gray-900 dark:text-white truncate">{merchant.merchant}</p>
                              <p className="text-xs text-gray-500">{t('analyses.report.charts.operationsCount', { count: merchant.count })}</p>
                            </div>
                          </div>
                          <span className="text-sm font-semibold text-gray-900 dark:text-white ml-2 flex-shrink-0">
                            {formatCurrency(merchant.amount)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Weekday analysis */}
                {result.analytics?.weekday_analysis && result.analytics.weekday_analysis.length > 0 && (
                  <div className="p-6 bg-white dark:bg-gray-800/50 rounded-2xl border border-gray-200/50 dark:border-gray-700/40">
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                      <Calendar className="w-5 h-5 text-blue-500" />
                      {t('analyses.report.charts.weekdayActivity')}
                    </h3>
                    <ResponsiveContainer width="100%" height={220}>
                      <BarChart data={result.analytics.weekday_analysis}>
                        <XAxis dataKey="day" tick={{ fontSize: 12 }} />
                        <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => `${(v / 1000).toFixed(0)}K`} />
                        <Tooltip
                          contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.15)' }}
                          formatter={(value: number) => [formatCurrency(value), t('analyses.report.charts.turnover')]}
                        />
                        <Bar dataKey="amount" fill="#2563eb" radius={[6, 6, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}

                {/* Top counterparties — who sent/received how much */}
                {result.analytics?.top_contacts && result.analytics.top_contacts.length > 0 && (
                  <div className="p-6 bg-white dark:bg-gray-800/50 rounded-2xl border border-gray-200/50 dark:border-gray-700/40">
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                      <Users className="w-5 h-5 text-indigo-500" />
                      {t('analyses.report.charts.topContacts')}
                    </h3>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="text-left text-gray-500 dark:text-gray-400 border-b border-gray-200/50 dark:border-gray-700/40">
                            <th className="py-2 pr-3 font-medium w-8">#</th>
                            <th className="py-2 pr-3 font-medium"></th>
                            <th className="py-2 px-3 font-medium text-right">{t('analyses.report.charts.contactSent')}</th>
                            <th className="py-2 px-3 font-medium text-right">{t('analyses.report.charts.contactReceived')}</th>
                            <th className="py-2 pl-3 font-medium text-right">{t('analyses.report.charts.contactBalance')}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {result.analytics.top_contacts.slice(0, 10).map((c, i) => (
                            <tr key={c.name} className="border-b border-gray-100/60 dark:border-gray-700/20 last:border-0">
                              <td className="py-2 pr-3 text-gray-400">{i + 1}</td>
                              <td className="py-2 pr-3">
                                <p className="font-medium text-gray-900 dark:text-white truncate max-w-[16rem]">{c.name}</p>
                                <p className="text-xs text-gray-500">{t('analyses.report.charts.operationsCount', { count: c.count })}</p>
                              </td>
                              <td className="py-2 px-3 text-right text-red-600 dark:text-red-400 whitespace-nowrap">{c.sent > 0 ? `−${formatCurrency(c.sent)}` : '—'}</td>
                              <td className="py-2 px-3 text-right text-green-600 dark:text-green-400 whitespace-nowrap">{c.received > 0 ? `+${formatCurrency(c.received)}` : '—'}</td>
                              <td className={`py-2 pl-3 text-right font-semibold whitespace-nowrap ${c.balance >= 0 ? 'text-green-700 dark:text-green-300' : 'text-red-700 dark:text-red-300'}`}>
                                {c.balance >= 0 ? '+' : '−'}{formatCurrency(Math.abs(c.balance))}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* Recurring payments — subscriptions and regular transfers */}
                {result.analytics?.recurring_payments && result.analytics.recurring_payments.length > 0 && (
                  <div className="p-6 bg-white dark:bg-gray-800/50 rounded-2xl border border-gray-200/50 dark:border-gray-700/40">
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                      <Repeat className="w-5 h-5 text-purple-500" />
                      {t('analyses.report.charts.recurringPayments')}
                    </h3>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="text-left text-gray-500 dark:text-gray-400 border-b border-gray-200/50 dark:border-gray-700/40">
                            <th className="py-2 pr-3 font-medium"></th>
                            <th className="py-2 px-3 font-medium">{t('analyses.report.charts.recurringEvery')}</th>
                            <th className="py-2 px-3 font-medium text-right">{t('analyses.report.charts.recurringAvg')}</th>
                            <th className="py-2 px-3 font-medium text-right">{t('analyses.report.charts.foreignTotal')}</th>
                            <th className="py-2 pl-3 font-medium text-right">{t('analyses.report.charts.recurringLast')}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {result.analytics.recurring_payments.slice(0, 12).map((p) => (
                            <tr key={p.name} className="border-b border-gray-100/60 dark:border-gray-700/20 last:border-0">
                              <td className="py-2 pr-3">
                                <p className="font-medium text-gray-900 dark:text-white truncate max-w-[18rem]">{p.name}</p>
                                <p className="text-xs text-gray-500">{t('analyses.report.charts.operationsCount', { count: p.count })}</p>
                              </td>
                              <td className="py-2 px-3">
                                <span className="inline-block px-2 py-0.5 rounded-full text-xs bg-purple-50 dark:bg-purple-900/20 text-purple-700 dark:text-purple-300">
                                  {t(`analyses.report.charts.${freqKey(p.frequency)}`)}
                                </span>
                              </td>
                              <td className="py-2 px-3 text-right text-gray-900 dark:text-white whitespace-nowrap">{formatCurrency(p.avg_amount)}</td>
                              <td className="py-2 px-3 text-right font-semibold text-gray-900 dark:text-white whitespace-nowrap">{formatCurrency(p.total_amount)}</td>
                              <td className="py-2 pl-3 text-right text-gray-500 whitespace-nowrap">{shortDate(p.last_payment)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* Foreign-currency operations */}
                {result.analytics?.foreign_currency?.transactions && result.analytics.foreign_currency.transactions.length > 0 && (
                  <div className="p-6 bg-white dark:bg-gray-800/50 rounded-2xl border border-gray-200/50 dark:border-gray-700/40">
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                      <Globe className="w-5 h-5 text-cyan-500" />
                      {t('analyses.report.charts.foreignCurrency')}
                    </h3>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="text-left text-gray-500 dark:text-gray-400 border-b border-gray-200/50 dark:border-gray-700/40">
                            <th className="py-2 pr-3 font-medium">{t('analyses.report.charts.foreignCurrencyCol')}</th>
                            <th className="py-2 px-3 font-medium text-right">{t('analyses.report.charts.foreignInKzt')}</th>
                            <th className="py-2 pl-3 font-medium text-right">{t('analyses.report.charts.foreignAvgRate')}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {result.analytics.foreign_currency.transactions.map((fx) => (
                            <tr key={fx.currency} className="border-b border-gray-100/60 dark:border-gray-700/20 last:border-0">
                              <td className="py-2 pr-3">
                                <span className="font-medium text-gray-900 dark:text-white">{fx.currency}</span>
                                <span className="text-xs text-gray-500 ml-2">{fx.total_original.toLocaleString(locale, { maximumFractionDigits: 2 })} {fx.currency}</span>
                                <p className="text-xs text-gray-500">{t('analyses.report.charts.operationsCount', { count: fx.transaction_count })}</p>
                              </td>
                              <td className="py-2 px-3 text-right font-semibold text-gray-900 dark:text-white whitespace-nowrap">{formatCurrency(fx.total_kzt)}</td>
                              <td className="py-2 pl-3 text-right text-gray-500 whitespace-nowrap">{fx.avg_exchange_rate.toLocaleString(locale, { maximumFractionDigits: 2 })}</td>
                            </tr>
                          ))}
                        </tbody>
                        <tfoot>
                          <tr className="border-t border-gray-200/60 dark:border-gray-700/40">
                            <td className="py-2 pr-3 font-medium text-gray-700 dark:text-gray-300">{t('analyses.report.charts.foreignTotal')}</td>
                            <td className="py-2 px-3 text-right font-bold text-gray-900 dark:text-white whitespace-nowrap">{formatCurrency(result.analytics.foreign_currency.total_foreign_kzt)}</td>
                            <td></td>
                          </tr>
                        </tfoot>
                      </table>
                    </div>
                  </div>
                )}

                {/* Daily balance dynamics */}
                {result.analytics?.daily_patterns && result.analytics.daily_patterns.length > 1 && (
                  <div className="p-6 bg-white dark:bg-gray-800/50 rounded-2xl border border-gray-200/50 dark:border-gray-700/40">
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                      <Activity className="w-5 h-5 text-emerald-500" />
                      {t('analyses.report.charts.dailyDynamics')}
                    </h3>
                    <ResponsiveContainer width="100%" height={260}>
                      <AreaChart data={result.analytics.daily_patterns}>
                        <defs>
                          <linearGradient id="colorBalance" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
                            <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                          </linearGradient>
                        </defs>
                        <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={shortDate} minTickGap={24} />
                        <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => `${(v / 1000).toFixed(0)}K`} />
                        <Tooltip
                          contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 20px rgba(0,0,0,0.15)', background: 'rgba(255,255,255,0.95)' }}
                          labelFormatter={(label: string) => shortDate(label)}
                          formatter={(value: number) => [formatCurrency(value), t('analyses.report.charts.balanceLabel')]}
                        />
                        <Area type="monotone" dataKey="balance" stroke="#10b981" fill="url(#colorBalance)" strokeWidth={2.5} name="balance" />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                )}

                {/* Fallback when no charts/analytics data */}
                {(!result.analytics?.monthly_breakdown || result.analytics.monthly_breakdown.length === 0) &&
                 (!result.analytics?.category_breakdown?.expense || result.analytics.category_breakdown.expense.length === 0) &&
                 (!result.analytics?.top_merchants || result.analytics.top_merchants.length === 0) && (
                  <div className="text-center py-12">
                    <TrendingUp className="w-12 h-12 text-gray-300 dark:text-gray-700 mx-auto mb-3" />
                    <p className="text-gray-500 dark:text-gray-400">{t('analyses.report.charts.noAnalyticsData')}</p>
                  </div>
                )}
              </motion.div>
  );
}
