/** Вкладка «Выводы»: заключение LLM, диалог со следователем, схемы и нормы. */
import { motion } from 'framer-motion';
import { useTranslation } from 'react-i18next';
import { Shield, CheckCircle, AlertTriangle, Target, Fingerprint, Sparkles } from 'lucide-react';
import { RiskScoreGauge } from '../RiskScoreGauge';
import { CaseConclusion } from '../CaseConclusion';
import { InvestigatorChat } from '../InvestigatorChat';
import { Report, FraudReport, intlLocale, safeLen } from './shared';

interface Props {
  result: Report;
  fraud: FraudReport;
}

export function ConclusionsSection({ result, fraud }: Props) {
  const { t, i18n } = useTranslation();
  const locale = intlLocale(i18n.language);
  // Описание этапа собирается из переведённых фрагментов: пустые отбрасываем,
  // непустые склеиваем пробелом — как раньше делали конкатенацией строк, но
  // теперь каждый фрагмент приходит из локали, а не зашит по-русски.
  const j = (...parts: string[]) => parts.filter(Boolean).join(' ');
  const sd = (key: string, vars?: Record<string, unknown>) =>
    t(`analyses.report.conclusions.stageDesc.${key}`, vars || {});
  const sn = (key: string) => t(`analyses.report.conclusions.stageNames.${key}`);
  return (
              <motion.div
                key="conclusions"
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}
                className="space-y-8"
              >
                {/* Заключение и диалог со следователем — то, ради чего в
                    проекте есть языковая модель. Стоят первыми в разделе
                    выводов: остальное здесь — числа, а вывод делается тут. */}
                <CaseConclusion analysisId={result.meta?.analysis_id} />
                <InvestigatorChat analysisId={result.meta?.analysis_id} />

                {fraud ? (
                  <>
                    {/* Final verdict */}
                    <div
                      className="p-8 bg-gradient-to-br from-slate-50 to-gray-100 dark:from-gray-800/50 dark:to-gray-900/50 rounded-2xl border border-gray-200/50 dark:border-gray-700/40 text-center"
                    >
                      <div className="flex justify-center mb-4">
                        <RiskScoreGauge score={fraud.composite_score} riskLevel={fraud.risk_level} size={180} />
                      </div>
                      <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
                        {t('analyses.report.conclusions.title')}
                      </h3>
                      <p className="text-sm text-gray-600 dark:text-gray-300 max-w-2xl mx-auto">
                        {t('analyses.report.conclusions.summary', {
                          count: result.summary.total_transactions,
                          period: `${result.account.period?.from ? t('analyses.report.conclusions.periodFrom', { from: result.account.period.from }) : ''}${result.account.period?.to ? t('analyses.report.conclusions.periodTo', { to: result.account.period.to }) : ''}`,
                        })} <span className="font-bold">
                          {t(`analyses.report.conclusions.riskLevels.${fraud.risk_level}`)}
                        </span> ({fraud.composite_score.toFixed(1)}/100).
                      </p>
                    </div>

                    {/* Analysis summary - what was found step by step */}
                    <div className="p-6 bg-white dark:bg-gray-800/50 rounded-2xl border border-gray-200/50 dark:border-gray-700/40">
                      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                        <Fingerprint className="w-5 h-5 text-blue-500" />
                        {t('analyses.report.conclusions.stages')}
                      </h3>
                      <div className="space-y-3">
                        {[
                          {
                            step: 1, name: sn('velocity'), score: fraud.velocity.risk_score,
                            desc: (fraud.velocity.burst_alerts.length > 0 || fraud.velocity.daily_spikes.length > 0)
                              ? j(
                                  sd('velocityFound', { bursts: fraud.velocity.burst_alerts.length, spikes: fraud.velocity.daily_spikes.length }),
                                  fraud.velocity.amount_acceleration?.length > 0 ? sd('velocityAccel', { count: fraud.velocity.amount_acceleration.length }) : '',
                                  fraud.velocity.counterparty_churn?.high_churn_days > 0 ? sd('velocityChurn', { count: fraud.velocity.counterparty_churn.high_churn_days }) : ''
                                )
                              : sd('velocityEmpty')
                          },
                          {
                            step: 2, name: sn('graph'), score: fraud.graph.risk_score,
                            desc: fraud.graph.node_count > 0
                              ? j(
                                  sd('graphBuilt', { nodes: fraud.graph.node_count, edges: fraud.graph.edge_count }),
                                  fraud.graph.cycles.length > 0 ? sd('graphCycles', { count: fraud.graph.cycles.length }) : sd('graphNoCycles'),
                                  fraud.graph.hub_nodes?.length > 0 ? sd('graphHubs', { hubs: fraud.graph.hub_nodes.slice(0, 3).map((h: any) => h.name).join(', ') }) : ''
                                )
                              : sd('graphEmpty')
                          },
                          {
                            step: 3, name: sn('structuring'), score: fraud.structuring.risk_score,
                            desc: (fraud.structuring.just_under_threshold.length > 0 || fraud.structuring.split_groups.length > 0 || fraud.structuring.smurfing_patterns.length > 0)
                              ? j(
                                  fraud.structuring.just_under_threshold.length > 0 ? sd('structThreshold', { count: fraud.structuring.just_under_threshold.length }) : '',
                                  fraud.structuring.split_groups.length > 0 ? sd('structSplit', { count: fraud.structuring.split_groups.length }) : '',
                                  fraud.structuring.smurfing_patterns.length > 0 ? sd('structSmurf', { count: fraud.structuring.smurfing_patterns.length }) : ''
                                )
                              : sd('structEmpty')
                          },
                          {
                            step: 4, name: sn('crossRef'), score: fraud.cross_reference.risk_score,
                            desc: j(
                                  sd('crossRatio', { ratio: fraud.cross_reference.income_expense_ratio?.toFixed(2) || 'N/A' }),
                                  fraud.cross_reference.rapid_pass_through.length > 0 ? sd('crossPass', { count: fraud.cross_reference.rapid_pass_through.length }) : sd('crossNoPass')
                                )
                          },
                          {
                            step: 5, name: sn('merchant'), score: fraud.merchant_risk.risk_score,
                            desc: (fraud.merchant_risk.high_risk_merchants.length > 0 || fraud.merchant_risk.medium_risk_merchants?.length > 0)
                              ? j(
                                  fraud.merchant_risk.high_risk_merchants.length > 0 ? sd('merchantHigh', { list: fraud.merchant_risk.high_risk_merchants.map((m: any) => `${m.name} (${m.category})`).join(', '), pct: fraud.merchant_risk.total_high_risk_pct.toFixed(1) }) : '',
                                  fraud.merchant_risk.medium_risk_merchants?.length > 0 ? sd('merchantMedium', { list: fraud.merchant_risk.medium_risk_merchants.slice(0, 3).map((m: any) => `${m.name} (${m.category})`).join(', ') }) : ''
                                )
                              : sd('merchantEmpty')
                          },
                          ...(fraud.night_transactions ? [{
                            step: 6, name: sn('night'), score: fraud.night_transactions.risk_score,
                            desc: fraud.night_transactions.no_time_data
                              ? sd('nightNoData')
                              : fraud.night_transactions.night_count > 0
                                ? j(
                                    sd('nightFound', { count: fraud.night_transactions.night_count, ratio: (fraud.night_transactions.night_ratio * 100).toFixed(1) }),
                                    fraud.night_transactions.large_night_transfers?.length > 0 ? sd('nightLarge', { count: fraud.night_transactions.large_night_transfers.length }) : '',
                                    fraud.night_transactions.night_clusters?.length > 0 ? sd('nightClusters', { count: fraud.night_transactions.night_clusters.length }) : ''
                                  )
                                : sd('nightEmpty')
                          }] : []),
                          ...(fraud.duplicate_payments ? [{
                            step: 7, name: sn('duplicate'), score: fraud.duplicate_payments.risk_score,
                            desc: fraud.duplicate_payments.total_duplicates > 0
                              ? j(
                                  sd('dupFound', { count: fraud.duplicate_payments.total_duplicates, groups: safeLen(fraud.duplicate_payments.duplicate_groups) }),
                                  fraud.duplicate_payments.total_duplicate_amount > 0 ? sd('dupAmount', { amount: Math.round(fraud.duplicate_payments.total_duplicate_amount).toLocaleString(locale) }) : '',
                                  fraud.duplicate_payments.same_amount_diff_recipient?.length > 0 ? sd('dupFan', { count: fraud.duplicate_payments.same_amount_diff_recipient.length }) : ''
                                )
                              : sd('dupEmpty')
                          }] : []),
                          ...(fraud.round_amounts ? [{
                            step: 8, name: sn('round'), score: fraud.round_amounts.risk_score,
                            desc: fraud.round_amounts.round_count > 0
                              ? j(
                                  sd('roundFound', { count: fraud.round_amounts.round_count, ratio: (fraud.round_amounts.round_ratio * 100).toFixed(1) }),
                                  fraud.round_amounts.consecutive_round?.length > 0 ? sd('roundConsecutive', { count: fraud.round_amounts.consecutive_round.length }) : '',
                                  fraud.round_amounts.round_total_amount > 0 ? sd('roundAmount', { amount: Math.round(fraud.round_amounts.round_total_amount).toLocaleString(locale) }) : ''
                                )
                              : sd('roundEmpty')
                          }] : []),
                          ...(fraud.profile_mismatch ? [{
                            step: 9, name: sn('profile'), score: fraud.profile_mismatch.risk_score,
                            desc: (safeLen(fraud.profile_mismatch.mismatches) > 0)
                              ? sd('profileFound', { over: safeLen(fraud.profile_mismatch.oversized_transactions), unexpected: safeLen(fraud.profile_mismatch.unexpected_activity), anomalies: safeLen(fraud.profile_mismatch.income_anomalies) })
                              : sd('profileEmpty')
                          }] : []),
                        ].map((item, i, arr) => {
                          const scoreColor = item.score >= 50 ? 'text-red-500 bg-red-50 dark:bg-red-900/20' : item.score >= 25 ? 'text-yellow-500 bg-yellow-50 dark:bg-yellow-900/20' : 'text-green-500 bg-green-50 dark:bg-green-900/20';
                          const lineColor = item.score >= 50 ? 'bg-red-400' : item.score >= 25 ? 'bg-yellow-400' : 'bg-green-400';
                          return (
                            <div
                              key={item.step}
                              className="flex items-start gap-4"
                            >
                              {/* Step number with connecting line */}
                              <div className="flex flex-col items-center">
                                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${scoreColor}`}>
                                  {item.step}
                                </div>
                                {i < arr.length - 1 && <div className={`w-0.5 h-8 ${lineColor} opacity-30`} />}
                              </div>
                              <div className="flex-1 pb-2">
                                <div className="flex items-center justify-between">
                                  <h4 className="text-sm font-semibold text-gray-900 dark:text-white">{item.name}</h4>
                                  <span className={`text-xs font-bold ${item.score >= 50 ? 'text-red-500' : item.score >= 25 ? 'text-yellow-500' : 'text-green-500'}`}>
                                    {item.score.toFixed(0)}/100
                                  </span>
                                </div>
                                <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{item.desc}</p>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>

                    {/* Red Flags */}
                    {fraud.red_flags && fraud.red_flags.length > 0 && (
                      <div
                        className="p-6 bg-red-50 dark:bg-red-900/20 rounded-2xl border border-red-200/50 dark:border-red-800/40"
                      >
                        <h3 className="text-lg font-semibold text-red-700 dark:text-red-400 mb-4 flex items-center gap-2">
                          <AlertTriangle className="w-5 h-5" />
                          {t('analyses.report.conclusions.redFlags', { count: fraud.red_flags.length })}
                        </h3>
                        <div className="space-y-2">
                          {fraud.red_flags.map((flag, i) => (
                            <div
                              key={i}
                              className="flex items-start gap-3 p-3 bg-white/80 dark:bg-gray-800/50 rounded-xl border border-red-200/30 dark:border-red-800/20"
                            >
                              <div className="w-6 h-6 rounded-full bg-red-100 dark:bg-red-900/40 flex items-center justify-center flex-shrink-0">
                                <span className="text-xs font-bold text-red-600 dark:text-red-400">{i + 1}</span>
                              </div>
                              <span className="text-sm text-gray-700 dark:text-gray-300">{flag}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Recommendations */}
                    {fraud.recommendations && fraud.recommendations.length > 0 && (
                      <div
                        className="p-6 bg-blue-50 dark:bg-blue-900/20 rounded-2xl border border-blue-200/50 dark:border-blue-800/40"
                      >
                        <h3 className="text-lg font-semibold text-blue-700 dark:text-blue-400 mb-4 flex items-center gap-2">
                          <Sparkles className="w-5 h-5" />
                          {t('analyses.report.conclusions.recommendations', { count: fraud.recommendations.length })}
                        </h3>
                        <div className="space-y-2">
                          {fraud.recommendations.map((rec, i) => (
                            <div
                              key={i}
                              className="flex items-start gap-3 p-3 bg-white/80 dark:bg-gray-800/50 rounded-xl border border-blue-200/30 dark:border-blue-800/20"
                            >
                              <div className="w-6 h-6 rounded-full bg-blue-100 dark:bg-blue-900/40 flex items-center justify-center flex-shrink-0">
                                <CheckCircle className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400" />
                              </div>
                              <span className="text-sm text-gray-700 dark:text-gray-300">{rec}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* ntFAST Footer */}
                    <div
                      className="text-center py-6 border-t border-gray-200/50 dark:border-gray-700/30"
                    >
                      <div className="flex items-center justify-center gap-2 text-sm text-gray-400 dark:text-gray-500">
                        <Shield className="w-4 h-4" />
                        <span>{t('analyses.report.conclusions.reportGenerated')} <span className="font-semibold text-blue-500">ntFAST AI v2.0</span></span>
                      </div>
                      <p className="text-xs text-gray-400 dark:text-gray-600 mt-1">
                        {t('analyses.report.subtitle')} &bull; {new Date().toLocaleString(locale)}
                      </p>
                    </div>
                  </>
                ) : (
                  <div className="text-center py-16">
                    <Target className="w-16 h-16 text-gray-300 dark:text-gray-700 mx-auto mb-4" />
                    <p className="text-gray-500 dark:text-gray-400">{t('analyses.report.conclusions.noConclusions')}</p>
                  </div>
                )}
              </motion.div>
  );
}
