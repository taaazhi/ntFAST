/** Вкладка «Финансы»: месячные обороты, категории, топ-мерчанты. */
import { motion } from 'framer-motion';
import { useTranslation } from 'react-i18next';
import { Calendar, TrendingUp, Store, PieChart as PieChartIcon } from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  AreaChart, Area, PieChart, Pie, Cell,
} from 'recharts';
import { Report, FormatCurrency, CHART_COLORS } from './shared';

interface Props {
  result: Report;
  formatCurrency: FormatCurrency;
}

export function FinancialSection({ result, formatCurrency }: Props) {
  const { t } = useTranslation();
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
