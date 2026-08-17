/** Вкладка «ntFAST Антифрод»: баллы 11 модулей, обоснование, флаги. */
import { motion, AnimatePresence } from 'framer-motion';
import { useTranslation } from 'react-i18next';
import {
  Shield, CheckCircle, AlertTriangle, Activity, Network, Layers,
  ArrowLeftRight, Store, Zap, Fingerprint, Clock, Moon, Copy,
  CircleDollarSign, UserX,
} from 'lucide-react';
import {
  ResponsiveContainer, RadarChart, Radar, PolarGrid,
  PolarAngleAxis, PolarRadiusAxis,
} from 'recharts';
import { RiskScoreGauge } from '../RiskScoreGauge';
import { ModuleScoreCard } from '../ModuleScoreCard';
import { ExplainedFlags } from '../ExplainedFlags';
import { IncomeSources } from '../IncomeSources';
import { Report, FraudReport, FormatCurrency, safeLen } from './shared';
import { getModuleIcon } from './moduleIcon';

interface Props {
  result: Report;
  fraud: FraudReport;
  formatCurrency: FormatCurrency;
  expandedModule: string | null;
  setExpandedModule: (v: string | null) => void;
}

export function AntifraudSection({ result, fraud, formatCurrency, expandedModule, setExpandedModule }: Props) {
  const { t } = useTranslation();
  return (
              <motion.div
                key="antifraud"
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}
                className="space-y-8"
              >
                {fraud ? (
                  <>
                    {/* ntFAST Analysis Pipeline Header */}
                    <div className="text-center mb-2">
                      <div
                        className="inline-flex items-center gap-2 px-4 py-2 bg-blue-50 dark:bg-blue-900/20 rounded-full border border-blue-200/50 dark:border-blue-800/40 mb-3"
                      >
                        <Fingerprint className="w-4 h-4 text-blue-500" />
                        <span className="text-sm font-medium text-blue-700 dark:text-blue-300">
                          {t('analyses.report.antifraud.pipelineBadge')}
                        </span>
                      </div>
                      <p className="text-sm text-gray-500 dark:text-gray-400 max-w-2xl mx-auto">
                        {t('analyses.report.antifraud.pipelineDesc')}
                      </p>
                    </div>

                    {/* Main Risk Score */}
                    <div className="flex flex-col lg:flex-row items-center gap-8 p-8 bg-gradient-to-br from-slate-50 to-gray-100 dark:from-gray-800/50 dark:to-gray-900/50 rounded-2xl border border-gray-200/50 dark:border-gray-700/40">
                      <RiskScoreGauge score={fraud.composite_score} riskLevel={fraud.risk_level} size={220} />

                      <div className="flex-1 w-full">
                        <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
                          {t('analyses.report.antifraud.resultTitle')}
                        </h3>
                        <p className="text-sm text-gray-600 dark:text-gray-300 mb-4">
                          {t('analyses.report.antifraud.resultDesc')}
                        </p>

                        {/* Radar chart of modules */}
                        <ResponsiveContainer width="100%" height={220}>
                          <RadarChart data={[
                            { module: t('analyses.report.modules.velocity.short'), score: fraud.velocity.risk_score },
                            { module: t('analyses.report.modules.graph.short'), score: fraud.graph.risk_score },
                            { module: t('analyses.report.modules.structuring.short'), score: fraud.structuring.risk_score },
                            { module: t('analyses.report.modules.crossReference.short'), score: fraud.cross_reference.risk_score },
                            { module: t('analyses.report.modules.merchantRisk.short'), score: fraud.merchant_risk.risk_score },
                            ...(fraud.night_transactions ? [{ module: t('analyses.report.modules.nightTransactions.short'), score: fraud.night_transactions.risk_score }] : []),
                            ...(fraud.duplicate_payments ? [{ module: t('analyses.report.modules.duplicatePayments.short'), score: fraud.duplicate_payments.risk_score }] : []),
                            ...(fraud.round_amounts ? [{ module: t('analyses.report.modules.roundAmounts.short'), score: fraud.round_amounts.risk_score }] : []),
                            ...(fraud.profile_mismatch ? [{ module: t('analyses.report.modules.profileMismatch.short'), score: fraud.profile_mismatch.risk_score }] : []),
                          ]}>
                            <PolarGrid strokeDasharray="3 3" className="text-gray-300 dark:text-gray-600" />
                            <PolarAngleAxis dataKey="module" tick={{ fontSize: 11, fill: '#6b7280' }} />
                            <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fontSize: 10 }} />
                            <Radar name="Risk Score" dataKey="score" stroke="#2563eb" fill="#2563eb" fillOpacity={0.25} strokeWidth={2} />
                          </RadarChart>
                        </ResponsiveContainer>
                      </div>
                    </div>

                    {/* Module Score Cards Grid */}
                    <div>
                      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                        <Layers className="w-5 h-5 text-blue-500" />
                        {t('analyses.report.antifraud.modulesTitle')}
                        <span className="text-xs text-gray-400 font-normal ml-2">{t('analyses.report.antifraud.clickForDetails')}</span>
                      </h3>
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                        {[
                          { key: 'velocity', name: t('analyses.report.modules.velocity.name'), score: fraud.velocity.risk_score, detail: `${fraud.velocity.burst_alerts.length} / ${fraud.velocity.daily_spikes.length}` },
                          { key: 'graph', name: t('analyses.report.modules.graph.name'), score: fraud.graph.risk_score, detail: `${fraud.graph.node_count} / ${fraud.graph.cycles.length}` },
                          { key: 'structuring', name: t('analyses.report.modules.structuring.name'), score: fraud.structuring.risk_score, detail: `${fraud.structuring.just_under_threshold.length} / ${fraud.structuring.split_groups.length}` },
                          { key: 'cross_reference', name: t('analyses.report.modules.crossReference.name'), score: fraud.cross_reference.risk_score, detail: `Ratio: ${fraud.cross_reference.income_expense_ratio?.toFixed(2)} / ${fraud.cross_reference.rapid_pass_through.length}` },
                          { key: 'merchant_risk', name: t('analyses.report.modules.merchantRisk.name'), score: fraud.merchant_risk.risk_score, detail: `${fraud.merchant_risk.high_risk_merchants.length} / ${fraud.merchant_risk.medium_risk_merchants.length}` },
                          ...(fraud.night_transactions ? [{ key: 'night_transactions', name: t('analyses.report.modules.nightTransactions.name'), score: fraud.night_transactions.risk_score, detail: `${fraud.night_transactions.night_count} / ${(fraud.night_transactions.night_ratio * 100).toFixed(1)}%` }] : []),
                          ...(fraud.duplicate_payments ? [{ key: 'duplicate_payments', name: t('analyses.report.modules.duplicatePayments.name'), score: fraud.duplicate_payments.risk_score, detail: `${fraud.duplicate_payments.total_duplicates}` }] : []),
                          ...(fraud.round_amounts ? [{ key: 'round_amounts', name: t('analyses.report.modules.roundAmounts.name'), score: fraud.round_amounts.risk_score, detail: `${fraud.round_amounts.round_count} / ${(fraud.round_amounts.round_ratio * 100).toFixed(1)}%` }] : []),
                          ...(fraud.profile_mismatch ? [{ key: 'profile_mismatch', name: t('analyses.report.modules.profileMismatch.name'), score: fraud.profile_mismatch.risk_score, detail: `${safeLen(fraud.profile_mismatch.mismatches)}` }] : []),
                        ].map((mod, i) => (
                          <ModuleScoreCard
                            key={mod.key}
                            name={mod.name}
                            score={mod.score}
                            detail={mod.detail}
                            icon={getModuleIcon(mod.key)}
                            index={i}
                            onClick={() => setExpandedModule(expandedModule === mod.key ? null : mod.key)}
                            isExpanded={expandedModule === mod.key}
                          />
                        ))}
                      </div>
                    </div>

                    {/* Обоснование балла: чем он набран и что говорит против.
                        Движок считал это и раньше, но наружу не отдавал. */}
                    <ExplainedFlags
                      explainedFlags={fraud.explained_flags}
                      flaggedPatterns={fraud.flagged_patterns}
                      appliedWeights={fraud.applied_weights}
                    />

                    {/* Источник дохода задаёт тип счёта, а тип счёта — веса
                        модулей выше. Скрывать такой вход нельзя. */}
                    <IncomeSources
                      enrichment={result.enrichment}
                      formatCurrency={formatCurrency}
                    />

                    {/* Expanded Module Details */}
                    <AnimatePresence>
                      {expandedModule && (
                        <motion.div
                          key={`detail-${expandedModule}`}
                          initial={{ opacity: 0, height: 0 }}
                          animate={{ opacity: 1, height: 'auto' }}
                          exit={{ opacity: 0, height: 0 }}
                          transition={{ duration: 0.4 }}
                          className="overflow-hidden"
                        >
                          {/* Velocity */}
                          {expandedModule === 'velocity' && (
                            <div className="p-6 bg-white dark:bg-gray-800/50 rounded-2xl border border-gray-200/50 dark:border-gray-700/40 space-y-4">
                              <div>
                                <h4 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                                  <Zap className="w-5 h-5 text-amber-500" />
                                  {t('analyses.report.modules.velocity.name')}
                                </h4>
                                <p className="text-xs text-gray-500 mt-1">
                                  {t('analyses.report.modules.velocity.desc')}
                                </p>
                              </div>
                              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                {fraud.velocity.burst_alerts.length > 0 && (
                                  <div>
                                    <h5 className="text-sm font-semibold text-orange-600 dark:text-orange-400 mb-2 flex items-center gap-1.5">
                                      <Zap className="w-3.5 h-3.5" />
                                      {t('analyses.report.modules.velocity.burstAlerts', { count: fraud.velocity.burst_alerts.length })}
                                    </h5>
                                    <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
                                      {fraud.velocity.burst_alerts.map((burst, i) => (
                                        <div
                                          key={i}
                                          className="p-3 bg-orange-50 dark:bg-orange-900/20 rounded-xl text-sm border border-orange-200/50 dark:border-orange-800/30"
                                        >
                                          <div className="flex justify-between items-center">
                                            <span className="font-semibold text-orange-700 dark:text-orange-300">{burst.transaction_count} {t('analyses.report.transactionsSuffix')}</span>
                                            <span className="text-xs text-gray-500">{burst.window_hours}h</span>
                                          </div>
                                          <div className="text-gray-600 dark:text-gray-400 mt-1">
                                            Сумма: {formatCurrency(burst.total_amount)}
                                          </div>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}
                                {fraud.velocity.daily_spikes.length > 0 && (
                                  <div>
                                    <h5 className="text-sm font-semibold text-red-600 dark:text-red-400 mb-2 flex items-center gap-1.5">
                                      <Activity className="w-3.5 h-3.5" />
                                      {t('analyses.report.modules.velocity.dailySpikes', { count: fraud.velocity.daily_spikes.length })}
                                    </h5>
                                    <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
                                      {fraud.velocity.daily_spikes.map((spike, i) => (
                                        <div
                                          key={i}
                                          className="p-3 bg-red-50 dark:bg-red-900/20 rounded-xl text-sm border border-red-200/50 dark:border-red-800/30"
                                        >
                                          <div className="flex justify-between items-center">
                                            <span className="font-semibold text-red-700 dark:text-red-300">{spike.date}</span>
                                            <span className="text-xs bg-red-100 dark:bg-red-900/40 text-red-600 dark:text-red-400 px-2 py-0.5 rounded-full font-medium">
                                              Z-score: {spike.z_score.toFixed(1)}
                                            </span>
                                          </div>
                                          <div className="text-gray-600 dark:text-gray-400 mt-1">
                                            {spike.transaction_count} операций &bull; {formatCurrency(spike.total_amount)}
                                          </div>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}
                              </div>
                              {fraud.velocity.burst_alerts.length === 0 && fraud.velocity.daily_spikes.length === 0 && (
                                <div className="text-center py-8 text-gray-400">
                                  <CheckCircle className="w-8 h-8 mx-auto mb-2 text-green-400" />
                                  <p className="text-sm">{t('analyses.report.modules.velocity.noAnomalies')}</p>
                                </div>
                              )}
                            </div>
                          )}

                          {/* Graph */}
                          {expandedModule === 'graph' && (
                            <div className="p-6 bg-white dark:bg-gray-800/50 rounded-2xl border border-gray-200/50 dark:border-gray-700/40 space-y-4">
                              <div>
                                <h4 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                                  <Network className="w-5 h-5 text-blue-500" />
                                  {t('analyses.report.modules.graph.name')}
                                </h4>
                                <p className="text-xs text-gray-500 mt-1">
                                  {t('analyses.report.modules.graph.desc')}
                                </p>
                              </div>
                              <div className="grid grid-cols-3 gap-4 mb-4">
                                <div className="text-center p-3 bg-blue-50 dark:bg-blue-900/20 rounded-xl">
                                  <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">{fraud.graph.node_count}</p>
                                  <p className="text-xs text-gray-500">{t('analyses.report.modules.graph.nodes')}</p>
                                </div>
                                <div className="text-center p-3 bg-blue-50 dark:bg-blue-900/20 rounded-xl">
                                  <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">{fraud.graph.edge_count}</p>
                                  <p className="text-xs text-gray-500">{t('analyses.report.modules.graph.edges')}</p>
                                </div>
                                <div className="text-center p-3 bg-red-50 dark:bg-red-900/20 rounded-xl">
                                  <p className="text-2xl font-bold text-red-600 dark:text-red-400">{fraud.graph.cycles.length}</p>
                                  <p className="text-xs text-gray-500">{t('analyses.report.modules.graph.cycles')}</p>
                                </div>
                              </div>

                              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                                {fraud.graph.cycles.length > 0 && (
                                  <div>
                                    <h5 className="text-sm font-semibold text-red-600 dark:text-red-400 mb-2">{t('analyses.report.modules.graph.circular')}</h5>
                                    <div className="space-y-2 max-h-48 overflow-y-auto">
                                      {fraud.graph.cycles.slice(0, 10).map((cycle, i) => (
                                        <div key={i} className="p-3 bg-red-50 dark:bg-red-900/20 rounded-xl text-xs border border-red-200/50 dark:border-red-800/30">
                                          <div className="font-medium text-red-700 dark:text-red-300 truncate">
                                            {cycle.nodes.join(' \u2192 ')}
                                          </div>
                                          <div className="text-red-500 mt-1">{formatCurrency(cycle.total_flow)}</div>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}
                                {fraud.graph.hub_nodes.length > 0 && (
                                  <div>
                                    <h5 className="text-sm font-semibold text-slate-600 dark:text-slate-400 mb-2">{t('analyses.report.modules.graph.hubs')}</h5>
                                    <div className="space-y-2 max-h-48 overflow-y-auto">
                                      {fraud.graph.hub_nodes.slice(0, 10).map((hub, i) => (
                                        <div key={i} className="p-3 bg-slate-50 dark:bg-slate-900/20 rounded-xl text-xs border border-slate-200/50 dark:border-slate-800/30 flex justify-between items-center">
                                          <div>
                                            <span className="font-medium text-slate-700 dark:text-slate-300">{hub.name}</span>
                                            <span className="text-gray-400 ml-1">({t('analyses.report.modules.graph.connections', { count: hub.connections })})</span>
                                          </div>
                                          <span className="text-slate-600 font-medium">{formatCurrency(hub.total_volume)}</span>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}
                              </div>
                            </div>
                          )}

                          {/* Structuring */}
                          {expandedModule === 'structuring' && (
                            <div className="p-6 bg-white dark:bg-gray-800/50 rounded-2xl border border-gray-200/50 dark:border-gray-700/40 space-y-4">
                              <div>
                                <h4 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                                  <Layers className="w-5 h-5 text-amber-500" />
                                  {t('analyses.report.modules.structuring.name')}
                                </h4>
                                <p className="text-xs text-gray-500 mt-1">
                                  {t('analyses.report.modules.structuring.desc')}
                                </p>
                              </div>
                              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                {fraud.structuring.just_under_threshold.length > 0 && (
                                  <div>
                                    <h5 className="text-sm font-semibold text-amber-600 dark:text-amber-400 mb-2">
                                      {t('analyses.report.modules.structuring.underThreshold', { count: fraud.structuring.just_under_threshold.length })}
                                    </h5>
                                    <div className="space-y-1.5 max-h-40 overflow-y-auto">
                                      {fraud.structuring.just_under_threshold.slice(0, 8).map((item, i) => (
                                        <div key={i} className="text-xs p-2 bg-amber-50 dark:bg-amber-900/20 rounded-lg border border-amber-200/50 dark:border-amber-800/30">
                                          <span className="font-medium">{formatCurrency(item.amount)}</span>
                                          <span className="text-gray-500 ml-1">({t('analyses.report.modules.structuring.ofThreshold', { pct: item.pct_of_threshold })})</span>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}
                                {fraud.structuring.split_groups.length > 0 && (
                                  <div>
                                    <h5 className="text-sm font-semibold text-red-600 dark:text-red-400 mb-2">
                                      {t('analyses.report.modules.structuring.splitting', { count: fraud.structuring.split_groups.length })}
                                    </h5>
                                    <div className="space-y-1.5 max-h-40 overflow-y-auto">
                                      {fraud.structuring.split_groups.map((group, i) => (
                                        <div key={i} className="text-xs p-2 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200/50 dark:border-red-800/30">
                                          <div className="font-medium text-red-700 dark:text-red-300 truncate">{group.counterparty}</div>
                                          <div className="text-gray-500">{group.transaction_count} op = {formatCurrency(group.total_amount)}</div>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}
                                {fraud.structuring.smurfing_patterns.length > 0 && (
                                  <div>
                                    <h5 className="text-sm font-semibold text-slate-600 dark:text-slate-400 mb-2">
                                      {t('analyses.report.modules.structuring.smurfing', { count: fraud.structuring.smurfing_patterns.length })}
                                    </h5>
                                    <div className="space-y-1.5 max-h-40 overflow-y-auto">
                                      {fraud.structuring.smurfing_patterns.map((p, i) => (
                                        <div key={i} className="text-xs p-2 bg-slate-50 dark:bg-slate-900/20 rounded-lg border border-slate-200/50 dark:border-slate-800/30">
                                          <div className="font-medium">{formatCurrency(p.amount)} x{p.occurrence_count}</div>
                                          <div className="text-gray-500">{t('analyses.report.modules.structuring.recipients', { count: p.unique_counterparties })}</div>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}
                              </div>
                              {fraud.structuring.just_under_threshold.length === 0 && fraud.structuring.split_groups.length === 0 && fraud.structuring.smurfing_patterns.length === 0 && (
                                <div className="text-center py-8 text-gray-400">
                                  <CheckCircle className="w-8 h-8 mx-auto mb-2 text-green-400" />
                                  <p className="text-sm">{t('analyses.report.modules.structuring.noPatterns')}</p>
                                </div>
                              )}
                            </div>
                          )}

                          {/* Cross Reference */}
                          {expandedModule === 'cross_reference' && (
                            <div className="p-6 bg-white dark:bg-gray-800/50 rounded-2xl border border-gray-200/50 dark:border-gray-700/40 space-y-4">
                              <div>
                                <h4 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                                  <ArrowLeftRight className="w-5 h-5 text-blue-500" />
                                  {t('analyses.report.modules.crossReference.name')}
                                </h4>
                                <p className="text-xs text-gray-500 mt-1">
                                  {t('analyses.report.modules.crossReference.desc')}
                                </p>
                              </div>
                              <div className="p-3 bg-blue-50 dark:bg-blue-900/20 rounded-xl mb-4">
                                <p className="text-sm text-gray-600 dark:text-gray-300">
                                  {t('analyses.report.modules.crossReference.ratio')}: <span className="font-bold text-blue-600 dark:text-blue-400">{fraud.cross_reference.income_expense_ratio?.toFixed(2)}</span>
                                </p>
                              </div>
                              {fraud.cross_reference.rapid_pass_through.length > 0 && (
                                <div>
                                  <h5 className="text-sm font-semibold text-orange-600 dark:text-orange-400 mb-2">
                                    {t('analyses.report.modules.crossReference.rapidPassThrough', { count: fraud.cross_reference.rapid_pass_through.length })}
                                  </h5>
                                  <div className="space-y-2 max-h-60 overflow-y-auto">
                                    {fraud.cross_reference.rapid_pass_through.map((pt, i) => (
                                      <div
                                        key={i}
                                        className="p-3 bg-orange-50 dark:bg-orange-900/20 rounded-xl text-sm border border-orange-200/50 dark:border-orange-800/30"
                                      >
                                        <div className="flex items-center justify-between">
                                          <span className="text-green-600 font-semibold">+{formatCurrency(pt.income_amount)}</span>
                                          <div className="flex items-center gap-1 text-gray-400 text-xs">
                                            <Clock className="w-3 h-3" />
                                            {pt.time_gap_hours}h
                                          </div>
                                          <span className="text-red-600 font-semibold">-{formatCurrency(pt.expense_amount)}</span>
                                        </div>
                                        <div className="text-xs text-gray-500 mt-1 truncate">
                                          {pt.income_source} \u2192 {pt.expense_dest}
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}
                              {fraud.cross_reference.rapid_pass_through.length === 0 && (
                                <div className="text-center py-8 text-gray-400">
                                  <CheckCircle className="w-8 h-8 mx-auto mb-2 text-green-400" />
                                  <p className="text-sm">{t('analyses.report.modules.crossReference.noTransits')}</p>
                                </div>
                              )}
                            </div>
                          )}

                          {/* Merchant Risk */}
                          {expandedModule === 'merchant_risk' && (
                            <div className="p-6 bg-white dark:bg-gray-800/50 rounded-2xl border border-gray-200/50 dark:border-gray-700/40 space-y-4">
                              <div>
                                <h4 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                                  <Store className="w-5 h-5 text-red-500" />
                                  {t('analyses.report.modules.merchantRisk.name')}
                                </h4>
                                <p className="text-xs text-gray-500 mt-1">
                                  {t('analyses.report.modules.merchantRisk.desc')}
                                </p>
                              </div>
                              <div className="p-3 bg-gray-50 dark:bg-gray-700/30 rounded-xl mb-2">
                                <p className="text-sm text-gray-600 dark:text-gray-300">
                                  {t('analyses.report.modules.merchantRisk.highRiskShare', { pct: fraud.merchant_risk.total_high_risk_pct.toFixed(1), amount: formatCurrency(fraud.merchant_risk.total_high_risk_amount) })}
                                </p>
                              </div>
                              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                {fraud.merchant_risk.high_risk_merchants.length > 0 && (
                                  <div>
                                    <h5 className="text-xs font-bold text-red-500 uppercase mb-2">{t('analyses.report.modules.merchantRisk.highRisk')}</h5>
                                    <div className="space-y-2">
                                      {fraud.merchant_risk.high_risk_merchants.map((m, i) => (
                                        <div key={i} className="flex justify-between p-2 bg-red-50 dark:bg-red-900/20 rounded-lg text-xs border border-red-200/50 dark:border-red-800/30">
                                          <div>
                                            <span className="font-medium text-red-700 dark:text-red-300">{m.name}</span>
                                            <span className="text-gray-400 ml-1">({m.category})</span>
                                          </div>
                                          <div className="text-right">
                                            <span className="font-medium">{formatCurrency(m.amount)}</span>
                                            <span className="text-gray-400 ml-1">x{m.count}</span>
                                          </div>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}
                                {fraud.merchant_risk.medium_risk_merchants.length > 0 && (
                                  <div>
                                    <h5 className="text-xs font-bold text-yellow-500 uppercase mb-2">{t('analyses.report.modules.merchantRisk.mediumRisk')}</h5>
                                    <div className="space-y-2">
                                      {fraud.merchant_risk.medium_risk_merchants.map((m, i) => (
                                        <div key={i} className="flex justify-between p-2 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg text-xs border border-yellow-200/50 dark:border-yellow-800/30">
                                          <div>
                                            <span className="font-medium text-yellow-700 dark:text-yellow-300">{m.name}</span>
                                            <span className="text-gray-400 ml-1">({m.category})</span>
                                          </div>
                                          <div className="text-right">
                                            <span className="font-medium">{formatCurrency(m.amount)}</span>
                                            <span className="text-gray-400 ml-1">x{m.count}</span>
                                          </div>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}
                              </div>
                              {/* Shell companies — generic legal-entity names.
                                  These already moved the score; without this
                                  block the analyst saw the number but not why. */}
                              {(fraud.merchant_risk.shell_companies?.length ?? 0) > 0 && (
                                <div>
                                  <h5 className="text-xs font-bold text-red-500 uppercase mb-2">
                                    {t('analyses.report.modules.merchantRisk.shellCompanies')}
                                  </h5>
                                  <div className="space-y-2">
                                    {fraud.merchant_risk.shell_companies!.map((m, i) => (
                                      <div key={i} className="flex justify-between p-2 bg-red-50 dark:bg-red-900/20 rounded-lg text-xs border border-red-200/50 dark:border-red-800/30">
                                        <span className="font-medium text-red-700 dark:text-red-300 truncate max-w-[60%]">{m.name}</span>
                                        <div className="text-right flex-shrink-0">
                                          <span className="font-medium">{formatCurrency(m.amount)}</span>
                                          <span className="text-gray-400 ml-1">x{m.count}</span>
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}
                              {fraud.merchant_risk.high_risk_merchants.length === 0 && fraud.merchant_risk.medium_risk_merchants.length === 0 && (fraud.merchant_risk.shell_companies?.length ?? 0) === 0 && (
                                <div className="text-center py-8 text-gray-400">
                                  <CheckCircle className="w-8 h-8 mx-auto mb-2 text-green-400" />
                                  <p className="text-sm">{t('analyses.report.modules.merchantRisk.noRisky')}</p>
                                </div>
                              )}
                            </div>
                          )}

                          {/* Night Transactions */}
                          {expandedModule === 'night_transactions' && fraud.night_transactions && (
                            <div className="p-6 bg-white dark:bg-gray-800/50 rounded-2xl border border-gray-200/50 dark:border-gray-700/40 space-y-4">
                              <div>
                                <h4 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                                  <Moon className="w-5 h-5 text-blue-500" />
                                  {t('analyses.report.modules.nightTransactions.name')}
                                </h4>
                                <p className="text-xs text-gray-500 mt-1">
                                  {t('analyses.report.modules.nightTransactions.desc')}
                                </p>
                              </div>
                              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                                <div className="text-center p-3 bg-blue-50 dark:bg-blue-900/20 rounded-xl">
                                  <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">{fraud.night_transactions.night_count}</p>
                                  <p className="text-xs text-gray-500">{t('analyses.report.modules.nightTransactions.nightCount')}</p>
                                </div>
                                <div className="text-center p-3 bg-blue-50 dark:bg-blue-900/20 rounded-xl">
                                  <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">{(fraud.night_transactions.night_ratio * 100).toFixed(1)}%</p>
                                  <p className="text-xs text-gray-500">{t('analyses.report.modules.nightTransactions.nightRatio')}</p>
                                </div>
                                <div className="text-center p-3 bg-blue-50 dark:bg-blue-900/20 rounded-xl">
                                  <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">{formatCurrency(fraud.night_transactions.night_total_amount)}</p>
                                  <p className="text-xs text-gray-500">{t('analyses.report.modules.nightTransactions.nightAmount')}</p>
                                </div>
                                <div className="text-center p-3 bg-red-50 dark:bg-red-900/20 rounded-xl">
                                  <p className="text-2xl font-bold text-red-600 dark:text-red-400">{safeLen(fraud.night_transactions.large_night_transfers)}</p>
                                  <p className="text-xs text-gray-500">{t('analyses.report.modules.nightTransactions.largeNight')}</p>
                                </div>
                              </div>
                              {safeLen(fraud.night_transactions.night_clusters) > 0 && (
                                <div className="p-3 bg-amber-50 dark:bg-amber-900/20 rounded-xl">
                                  <p className="text-sm text-amber-700 dark:text-amber-300">
                                    <AlertTriangle className="w-4 h-4 inline mr-1" />
                                    {t('analyses.report.modules.nightTransactions.clustersWarn', { count: safeLen(fraud.night_transactions.night_clusters) })}
                                  </p>
                                </div>
                              )}
                              {fraud.night_transactions.night_count === 0 && (
                                <div className="text-center py-8 text-gray-400">
                                  <CheckCircle className="w-8 h-8 mx-auto mb-2 text-green-400" />
                                  <p className="text-sm">{t('analyses.report.modules.nightTransactions.noNight')}</p>
                                </div>
                              )}
                            </div>
                          )}

                          {/* Duplicate Payments */}
                          {expandedModule === 'duplicate_payments' && fraud.duplicate_payments && (
                            <div className="p-6 bg-white dark:bg-gray-800/50 rounded-2xl border border-gray-200/50 dark:border-gray-700/40 space-y-4">
                              <div>
                                <h4 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                                  <Copy className="w-5 h-5 text-orange-500" />
                                  {t('analyses.report.modules.duplicatePayments.name')}
                                </h4>
                                <p className="text-xs text-gray-500 mt-1">
                                  {t('analyses.report.modules.duplicatePayments.desc')}
                                </p>
                              </div>
                              <div className="grid grid-cols-3 gap-4 mb-4">
                                <div className="text-center p-3 bg-orange-50 dark:bg-orange-900/20 rounded-xl">
                                  <p className="text-2xl font-bold text-orange-600 dark:text-orange-400">{fraud.duplicate_payments.total_duplicates}</p>
                                  <p className="text-xs text-gray-500">{t('analyses.report.modules.duplicatePayments.totalDuplicates')}</p>
                                </div>
                                <div className="text-center p-3 bg-orange-50 dark:bg-orange-900/20 rounded-xl">
                                  <p className="text-2xl font-bold text-orange-600 dark:text-orange-400">{safeLen(fraud.duplicate_payments.duplicate_groups)}</p>
                                  <p className="text-xs text-gray-500">{t('analyses.report.modules.duplicatePayments.groups')}</p>
                                </div>
                                <div className="text-center p-3 bg-red-50 dark:bg-red-900/20 rounded-xl">
                                  <p className="text-2xl font-bold text-red-600 dark:text-red-400">{safeLen(fraud.duplicate_payments.same_amount_diff_recipient)}</p>
                                  <p className="text-xs text-gray-500">{t('analyses.report.modules.duplicatePayments.fanOut')}</p>
                                </div>
                              </div>
                              {fraud.duplicate_payments.total_duplicate_amount > 0 && (
                                <div className="p-3 bg-gray-50 dark:bg-gray-700/30 rounded-xl">
                                  <p className="text-sm text-gray-600 dark:text-gray-300">
                                    {t('analyses.report.modules.duplicatePayments.totalAmount')}: <span className="font-bold text-orange-600 dark:text-orange-400">{formatCurrency(fraud.duplicate_payments.total_duplicate_amount)}</span>
                                  </p>
                                </div>
                              )}
                              {fraud.duplicate_payments.total_duplicates === 0 && (
                                <div className="text-center py-8 text-gray-400">
                                  <CheckCircle className="w-8 h-8 mx-auto mb-2 text-green-400" />
                                  <p className="text-sm">{t('analyses.report.modules.duplicatePayments.noDuplicates')}</p>
                                </div>
                              )}
                            </div>
                          )}

                          {/* Round Amounts */}
                          {expandedModule === 'round_amounts' && fraud.round_amounts && (
                            <div className="p-6 bg-white dark:bg-gray-800/50 rounded-2xl border border-gray-200/50 dark:border-gray-700/40 space-y-4">
                              <div>
                                <h4 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                                  <CircleDollarSign className="w-5 h-5 text-emerald-500" />
                                  {t('analyses.report.modules.roundAmounts.name')}
                                </h4>
                                <p className="text-xs text-gray-500 mt-1">
                                  {t('analyses.report.modules.roundAmounts.desc')}
                                </p>
                              </div>
                              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                                <div className="text-center p-3 bg-emerald-50 dark:bg-emerald-900/20 rounded-xl">
                                  <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">{fraud.round_amounts.round_count}</p>
                                  <p className="text-xs text-gray-500">{t('analyses.report.modules.roundAmounts.roundCount')}</p>
                                </div>
                                <div className="text-center p-3 bg-emerald-50 dark:bg-emerald-900/20 rounded-xl">
                                  <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">{(fraud.round_amounts.round_ratio * 100).toFixed(1)}%</p>
                                  <p className="text-xs text-gray-500">{t('analyses.report.modules.roundAmounts.roundRatio')}</p>
                                </div>
                                <div className="text-center p-3 bg-emerald-50 dark:bg-emerald-900/20 rounded-xl">
                                  <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">{formatCurrency(fraud.round_amounts.round_total_amount)}</p>
                                  <p className="text-xs text-gray-500">{t('analyses.report.modules.roundAmounts.roundAmount')}</p>
                                </div>
                                <div className="text-center p-3 bg-red-50 dark:bg-red-900/20 rounded-xl">
                                  <p className="text-2xl font-bold text-red-600 dark:text-red-400">{safeLen(fraud.round_amounts.consecutive_round)}</p>
                                  <p className="text-xs text-gray-500">{t('analyses.report.modules.roundAmounts.consecutive')}</p>
                                </div>
                              </div>
                              {fraud.round_amounts.round_count === 0 && (
                                <div className="text-center py-8 text-gray-400">
                                  <CheckCircle className="w-8 h-8 mx-auto mb-2 text-green-400" />
                                  <p className="text-sm">{t('analyses.report.modules.roundAmounts.noRound')}</p>
                                </div>
                              )}
                            </div>
                          )}

                          {/* Profile Mismatch */}
                          {expandedModule === 'profile_mismatch' && fraud.profile_mismatch && (
                            <div className="p-6 bg-white dark:bg-gray-800/50 rounded-2xl border border-gray-200/50 dark:border-gray-700/40 space-y-4">
                              <div>
                                <h4 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                                  <UserX className="w-5 h-5 text-red-500" />
                                  {t('analyses.report.modules.profileMismatch.name')}
                                </h4>
                                <p className="text-xs text-gray-500 mt-1">
                                  {t('analyses.report.modules.profileMismatch.desc')}
                                </p>
                              </div>
                              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                                <div className="text-center p-3 bg-red-50 dark:bg-red-900/20 rounded-xl">
                                  <p className="text-2xl font-bold text-red-600 dark:text-red-400">{safeLen(fraud.profile_mismatch.mismatches)}</p>
                                  <p className="text-xs text-gray-500">{t('analyses.report.modules.profileMismatch.mismatches')}</p>
                                </div>
                                <div className="text-center p-3 bg-red-50 dark:bg-red-900/20 rounded-xl">
                                  <p className="text-2xl font-bold text-red-600 dark:text-red-400">{safeLen(fraud.profile_mismatch.oversized_transactions)}</p>
                                  <p className="text-xs text-gray-500">{t('analyses.report.modules.profileMismatch.oversized')}</p>
                                </div>
                                <div className="text-center p-3 bg-red-50 dark:bg-red-900/20 rounded-xl">
                                  <p className="text-2xl font-bold text-red-600 dark:text-red-400">{safeLen(fraud.profile_mismatch.unexpected_activity)}</p>
                                  <p className="text-xs text-gray-500">{t('analyses.report.modules.profileMismatch.unexpected')}</p>
                                </div>
                                <div className="text-center p-3 bg-red-50 dark:bg-red-900/20 rounded-xl">
                                  <p className="text-2xl font-bold text-red-600 dark:text-red-400">{safeLen(fraud.profile_mismatch.income_anomalies)}</p>
                                  <p className="text-xs text-gray-500">{t('analyses.report.modules.profileMismatch.incomeAnomalies')}</p>
                                </div>
                              </div>
                              {safeLen(fraud.profile_mismatch.mismatches) === 0 && (
                                <div className="text-center py-8 text-gray-400">
                                  <CheckCircle className="w-8 h-8 mx-auto mb-2 text-green-400" />
                                  <p className="text-sm">{t('analyses.report.modules.profileMismatch.noMismatches')}</p>
                                </div>
                              )}
                            </div>
                          )}
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </>
                ) : (
                  <div className="text-center py-16">
                    <Shield className="w-16 h-16 text-gray-300 dark:text-gray-700 mx-auto mb-4" />
                    <p className="text-gray-500 dark:text-gray-400 text-lg">{t('analyses.report.antifraud.noData')}</p>
                    <p className="text-gray-400 dark:text-gray-500 text-sm mt-1">
                      {t('analyses.report.antifraud.noDataDesc')}
                    </p>
                  </div>
                )}
              </motion.div>
  );
}
