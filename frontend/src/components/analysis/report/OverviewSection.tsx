/** Вкладка «Обзор»: KPI, сводка по счёту, финансовое здоровье. */
import { motion } from 'framer-motion';
import { useTranslation } from 'react-i18next';
import {
  Shield, CreditCard, AlertTriangle, TrendingUp,
  ArrowUpRight, ArrowDownRight, Activity, ChevronRight,
} from 'lucide-react';
import { RiskScoreGauge } from '../RiskScoreGauge';
import { Report, FraudReport, FormatCurrency, SectionId } from './shared';

interface Props {
  result: Report;
  fraud: FraudReport;
  formatCurrency: FormatCurrency;
  setActiveSection: (id: SectionId) => void;
}

export function OverviewSection({ result, fraud, formatCurrency, setActiveSection }: Props) {
  const { t } = useTranslation();
  return (
              <motion.div
                key="overview"
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}
                className="space-y-8"
              >
                {/* KPI Cards */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
                  {[
                    { label: t('analyses.report.kpi.totalIncome'), value: result.summary.total_income, icon: ArrowUpRight, color: 'green', prefix: '+' },
                    { label: t('analyses.report.kpi.totalExpense'), value: result.summary.total_expense, icon: ArrowDownRight, color: 'red', prefix: '-' },
                    // Знак ставится префиксом, потому что значение ниже
                    // печатается по модулю. Для отрицательного потока префикс
                    // был пустым, и расход, превысивший доход, выглядел как
                    // прибыль: −18 530 ₸ показывалось как «18 530 ₸».
                    { label: t('analyses.report.kpi.netFlow'), value: result.summary.net_flow, icon: TrendingUp, color: result.summary.net_flow >= 0 ? 'blue' : 'red', prefix: result.summary.net_flow >= 0 ? '+' : '−' },
                    { label: t('analyses.report.kpi.avgDailyExpense'), value: result.summary.avg_daily_expense, icon: Activity, color: 'slate', prefix: '' },
                  ].map((kpi) => {
                    const Icon = kpi.icon;
                    const colorMap: Record<string, { bg: string; iconBg: string; text: string; border: string }> = {
                      green: { bg: 'from-green-50 to-emerald-50 dark:from-green-900/20 dark:to-emerald-900/20', iconBg: 'bg-green-500', text: 'text-green-700 dark:text-green-300', border: 'border-green-200/50 dark:border-green-800/40' },
                      red: { bg: 'from-red-50 to-red-50 dark:from-red-900/20 dark:to-red-900/20', iconBg: 'bg-red-500', text: 'text-red-700 dark:text-red-300', border: 'border-red-200/50 dark:border-red-800/40' },
                      blue: { bg: 'from-blue-50 to-blue-50 dark:from-blue-900/20 dark:to-blue-900/20', iconBg: 'bg-blue-500', text: 'text-blue-700 dark:text-blue-300', border: 'border-blue-200/50 dark:border-blue-800/40' },
                      slate: { bg: 'from-slate-50 to-gray-50 dark:from-slate-900/20 dark:to-gray-900/20', iconBg: 'bg-slate-500', text: 'text-slate-700 dark:text-slate-300', border: 'border-slate-200/50 dark:border-slate-800/40' },
                    };
                    const c = colorMap[kpi.color];
                    return (
                      <div
                        key={kpi.label}
                        className={`relative p-5 bg-gradient-to-br ${c.bg} rounded-2xl border ${c.border} group`}
                      >
                        <div className="flex items-center justify-between mb-3">
                          <span className="text-sm font-medium text-gray-600 dark:text-gray-400">{kpi.label}</span>
                          <div className={`p-2 ${c.iconBg} rounded-xl shadow-lg`}>
                            <Icon className="w-4 h-4 text-white" />
                          </div>
                        </div>
                        <p className={`text-2xl font-bold ${c.text}`}>
                          {kpi.prefix}{formatCurrency(Math.abs(kpi.value))}
                        </p>
                      </div>
                    );
                  })}
                </div>

                {/* Account Summary Card */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {/* Balance info */}
                  <div
                    className="p-6 bg-gradient-to-br from-slate-50 to-gray-100 dark:from-gray-800/50 dark:to-gray-900/50 rounded-2xl border border-gray-200/50 dark:border-gray-700/40"
                  >
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                      <CreditCard className="w-5 h-5 text-blue-500" />
                      {t('analyses.report.account.title')}
                    </h3>
                    <div className="space-y-3">
                      {[
                        { label: t('analyses.report.account.owner'), value: result.account.owner },
                        { label: t('analyses.report.account.card'), value: result.account.card },
                        { label: t('analyses.report.account.accountNumber'), value: result.account.account_number || '---' },
                        { label: t('analyses.report.account.balanceStart'), value: formatCurrency(result.account.balance_start || 0) },
                        { label: t('analyses.report.account.balanceEnd'), value: formatCurrency(result.account.balance_end || 0) },
                        { label: t('analyses.report.account.currency'), value: result.account.currency || 'KZT' },
                      ].map((row) => (
                        <div key={row.label} className="flex justify-between items-center py-1.5 border-b border-gray-200/50 dark:border-gray-700/30 last:border-0">
                          <span className="text-sm text-gray-500 dark:text-gray-400">{row.label}</span>
                          <span className="text-sm font-medium text-gray-900 dark:text-white">{row.value}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Quick risk summary */}
                  {fraud && (
                    <div
                      className="p-6 bg-gradient-to-br from-blue-50 to-blue-100 dark:from-blue-900/20 dark:to-blue-900/30 rounded-2xl border border-blue-200/50 dark:border-blue-800/40"
                    >
                      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                        <Shield className="w-5 h-5 text-blue-500" />
                        {t('analyses.report.risk.title')}
                      </h3>
                      <div className="flex items-center gap-6">
                        <RiskScoreGauge score={fraud.composite_score} riskLevel={fraud.risk_level} size={160} />
                        <div className="flex-1 space-y-2">
                          <p
                            className="text-sm text-gray-600 dark:text-gray-300"
                            dangerouslySetInnerHTML={{ __html: t('analyses.report.risk.description', { count: result.summary.total_transactions }) }}
                          />
                          {fraud.red_flags && fraud.red_flags.length > 0 && (
                            <div className="flex items-center gap-2 mt-3">
                              <AlertTriangle className="w-4 h-4 text-red-500 flex-shrink-0" />
                              <span className="text-sm text-red-600 dark:text-red-400 font-medium">
                                {t('analyses.report.risk.redFlagsDetected', { count: fraud.red_flags.length })}
                              </span>
                            </div>
                          )}
                          <button
                            onClick={() => setActiveSection('antifraud')}
                            className="mt-3 text-sm font-medium text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 flex items-center gap-1 transition-colors"
                          >
                            {t('analyses.report.risk.viewDetails')} <ChevronRight className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {/* Financial Health */}
                {result.analytics?.financial_health && (
                  <div
                    className="p-6 bg-white dark:bg-gray-800/50 rounded-2xl border border-gray-200/50 dark:border-gray-700/40"
                  >
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                      <Activity className="w-5 h-5 text-emerald-500" />
                      {t('analyses.report.health.title')}
                    </h3>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      {[
                        { label: t('analyses.report.health.savingsRate'), value: `${(result.analytics.financial_health.savings_rate * 100).toFixed(1)}%`, color: result.analytics.financial_health.savings_rate > 0.1 ? 'text-green-600' : 'text-red-600' },
                        { label: t('analyses.report.health.balanceTrend'), value: result.analytics.financial_health.balance_trend === 'growing' ? t('analyses.report.health.growing') : result.analytics.financial_health.balance_trend === 'declining' ? t('analyses.report.health.declining') : t('analyses.report.health.stable'), color: result.analytics.financial_health.balance_trend === 'growing' ? 'text-green-600' : result.analytics.financial_health.balance_trend === 'declining' ? 'text-red-600' : 'text-blue-600' },
                        { label: t('analyses.report.health.financialBuffer'), value: `${result.analytics.financial_health.financial_buffer_days.toFixed(1)} ${t('analyses.report.health.days')}`, color: result.analytics.financial_health.financial_buffer_days > 30 ? 'text-green-600' : 'text-yellow-600' },
                        { label: t('analyses.report.health.essentialRatio'), value: `${(result.analytics.financial_health.essential_ratio * 100).toFixed(0)}%`, color: 'text-gray-700 dark:text-gray-300' },
                      ].map((item) => (
                        <div key={item.label} className="text-center p-3 bg-gray-50 dark:bg-gray-700/30 rounded-xl">
                          <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">{item.label}</p>
                          <p className={`text-lg font-bold ${item.color}`}>{item.value}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </motion.div>
  );
}
