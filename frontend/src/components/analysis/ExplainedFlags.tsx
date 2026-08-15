/**
 * Обоснование оценки риска: почему балл именно такой.
 *
 * Движок это считал и раньше — `explained_flags`, `flagged_patterns` и
 * `applied_weights` лежали в отчёте и никуда не выводились. Следователь видел
 * число и уровень риска, но не мог проверить, из чего они сложились. Для
 * документа, который ложится в материалы дела, это и есть «результат анализа
 * реализован не полностью».
 *
 * Вместе с доводом «за» показывается контраргумент: обстоятельство, при
 * котором тот же признак законен. Пять мелких покупок в валюте за два часа —
 * это и тестирование украденных карт, и турист в поездке. Скрыть вторую
 * трактовку значит выдать подозрение за вывод.
 */
import { motion } from 'framer-motion';
import { useTranslation } from 'react-i18next';
import { AlertTriangle, Scale, ShieldCheck, Info } from 'lucide-react';
import { ExplainedFlag, FlaggedPattern } from '../../services/api';

interface Props {
  explainedFlags?: ExplainedFlag[];
  flaggedPatterns?: FlaggedPattern[];
  appliedWeights?: Record<string, number>;
}

/** Доля 0..1 в проценты. Бэкенд отдаёт доли, форматирует фронтенд. */
const pct = (value: number): string => `${Math.round((value || 0) * 100)}%`;

/**
 * Движок называет модули в snake_case, ключи локалей — в camelCase.
 * Без сопоставления вместо «Круглые суммы» в отчёте следователя оказалось бы
 * сырое `round_amounts`.
 */
const MODULE_KEYS: Record<string, string> = {
  cross_reference: 'crossReference',
  merchant_risk: 'merchantRisk',
  night_transactions: 'nightTransactions',
  duplicate_payments: 'duplicatePayments',
  round_amounts: 'roundAmounts',
  profile_mismatch: 'profileMismatch',
  pattern_detector: 'patternDetector',
};

const moduleKey = (module: string): string => MODULE_KEYS[module] ?? module;

const severityStyles: Record<string, string> = {
  critical: 'border-red-300 bg-red-50 dark:border-red-800/50 dark:bg-red-900/20',
  warning: 'border-amber-300 bg-amber-50 dark:border-amber-800/50 dark:bg-amber-900/20',
  info: 'border-blue-300 bg-blue-50 dark:border-blue-800/50 dark:bg-blue-900/20',
};

export function ExplainedFlags({ explainedFlags, flaggedPatterns, appliedWeights }: Props) {
  const { t } = useTranslation();

  const flags = explainedFlags ?? [];
  const patterns = flaggedPatterns ?? [];
  const weights = Object.entries(appliedWeights ?? {})
    .filter(([, w]) => w > 0)
    .sort(([, a], [, b]) => b - a);

  if (flags.length === 0 && patterns.length === 0 && weights.length === 0) {
    return (
      <div className="flex items-center gap-3 p-6 rounded-xl border border-green-200 bg-green-50 dark:border-green-800/40 dark:bg-green-900/20">
        <ShieldCheck className="w-5 h-5 text-green-600 dark:text-green-400 shrink-0" />
        <p className="text-sm text-green-800 dark:text-green-200">
          {t('analyses.report.explained.none')}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* ── Распознанные схемы: то, что квалифицируется по норме права ── */}
      {patterns.length > 0 && (
        <section>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
            <Scale className="w-5 h-5 text-purple-500" />
            {t('analyses.report.explained.patternsTitle')}
          </h3>

          <div className="space-y-4">
            {patterns.map((pattern, index) => (
              <motion.div
                key={pattern.pattern_name ?? index}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2, delay: index * 0.05 }}
                className="p-5 rounded-xl border border-purple-200 bg-purple-50/60 dark:border-purple-800/40 dark:bg-purple-900/15"
              >
                <div className="flex flex-wrap items-start justify-between gap-3 mb-2">
                  <h4 className="font-semibold text-gray-900 dark:text-white">
                    {pattern.display_name || pattern.pattern_name}
                  </h4>
                  <div className="flex items-center gap-2 text-xs">
                    <span className="px-2 py-1 rounded-md bg-purple-100 text-purple-700 dark:bg-purple-800/40 dark:text-purple-200">
                      {t('analyses.report.explained.confidence')}: {pct(pattern.confidence)}
                    </span>
                    <span className="px-2 py-1 rounded-md bg-gray-100 text-gray-700 dark:bg-gray-700/50 dark:text-gray-200">
                      +{(pattern.risk_contribution ?? 0).toFixed(1)} {t('analyses.report.explained.points')}
                    </span>
                  </div>
                </div>

                <p className="text-sm text-gray-700 dark:text-gray-300 mb-3">{pattern.reason}</p>

                {/* Разобранные нормы: каждая ведёт на официальный текст.
                    Если корпус НПА не собран, список пуст — тогда показываем
                    исходную строку, как было. */}
                {pattern.legal_articles && pattern.legal_articles.length > 0 ? (
                  <ul className="mb-3 space-y-1.5">
                    {pattern.legal_articles.map((article) => (
                      <li key={article.citation} className="flex items-start gap-2 text-sm">
                        <Scale className="w-4 h-4 mt-0.5 text-purple-500 shrink-0" />
                        <span>
                          {/* Ссылка только когда есть куда вести. У выдуманной
                              статьи URL пуст, и href="" отправил бы следователя
                              на перезагрузку страницы вместо текста закона. */}
                          {article.url ? (
                            <a
                              href={article.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="font-medium text-purple-800 dark:text-purple-200 underline decoration-purple-300 underline-offset-2 hover:decoration-purple-600"
                            >
                              {article.citation}
                            </a>
                          ) : (
                            <span className="font-medium text-gray-700 dark:text-gray-300">
                              {article.citation}
                            </span>
                          )}
                          {article.title && (
                            <span className="text-gray-600 dark:text-gray-400">
                              {' — '}{article.title}
                            </span>
                          )}
                          {article.verified ? (
                            <span
                              className="ml-2 inline-flex items-center gap-1 text-xs text-green-700 dark:text-green-400"
                              title={t('analyses.report.explained.verifiedHint')}
                            >
                              <ShieldCheck className="w-3.5 h-3.5" />
                              {t('analyses.report.explained.verified')}
                            </span>
                          ) : (
                            <span
                              className="ml-2 text-xs text-amber-700 dark:text-amber-400"
                              title={article.detail}
                            >
                              {t('analyses.report.explained.unverified')}
                            </span>
                          )}
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : pattern.regulatory_reference ? (
                  <div className="flex items-start gap-2 mb-3 text-sm">
                    <Scale className="w-4 h-4 mt-0.5 text-purple-500 shrink-0" />
                    <span className="text-purple-800 dark:text-purple-200 font-medium">
                      {pattern.regulatory_reference}
                    </span>
                  </div>
                ) : null}

                {pattern.counter_evidence && (
                  <div className="flex items-start gap-2 p-3 rounded-lg bg-white/70 dark:bg-gray-800/40 text-sm">
                    <Info className="w-4 h-4 mt-0.5 text-blue-500 shrink-0" />
                    <div>
                      <span className="font-medium text-gray-800 dark:text-gray-200">
                        {t('analyses.report.explained.counterEvidence')}:{' '}
                      </span>
                      <span className="text-gray-600 dark:text-gray-400">{pattern.counter_evidence}</span>
                    </div>
                  </div>
                )}
              </motion.div>
            ))}
          </div>
        </section>
      )}

      {/* ── Отдельные признаки и их вклад в балл ── */}
      {flags.length > 0 && (
        <section>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-amber-500" />
            {t('analyses.report.explained.flagsTitle')}
          </h3>

          <div className="space-y-3">
            {flags.map((flag, index) => (
              <div
                key={`${flag.module}-${index}`}
                className={`p-4 rounded-xl border ${severityStyles[flag.severity] ?? severityStyles.info}`}
              >
                <div className="flex flex-wrap items-center justify-between gap-2 mb-1">
                  <span className="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
                    {t(`analyses.report.modules.${moduleKey(flag.module)}.short`, { defaultValue: flag.module })}
                  </span>
                  <div className="flex items-center gap-2 text-xs text-gray-600 dark:text-gray-300">
                    <span>{t('analyses.report.explained.confidence')}: {pct(flag.confidence)}</span>
                    <span className="font-medium">
                      +{(flag.score_contribution ?? 0).toFixed(2)} {t('analyses.report.explained.points')}
                    </span>
                  </div>
                </div>

                <p className="text-sm text-gray-800 dark:text-gray-200">{flag.reason}</p>

                {flag.counter_evidence && (
                  <p className="mt-2 text-xs text-gray-600 dark:text-gray-400">
                    <span className="font-medium">{t('analyses.report.explained.counterEvidence')}: </span>
                    {flag.counter_evidence}
                  </p>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ── Веса модулей: они зависят от типа счёта, и это надо показать ── */}
      {weights.length > 0 && (
        <section>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2 flex items-center gap-2">
            <Info className="w-5 h-5 text-blue-500" />
            {t('analyses.report.explained.weightsTitle')}
          </h3>
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
            {t('analyses.report.explained.weightsDesc')}
          </p>

          <div className="space-y-2">
            {weights.map(([module, weight]) => (
              <div key={module} className="flex items-center gap-3">
                <span className="w-44 shrink-0 text-sm text-gray-700 dark:text-gray-300 truncate">
                  {t(`analyses.report.modules.${moduleKey(module)}.short`, { defaultValue: module })}
                </span>
                <div className="flex-1 h-2 rounded-full bg-gray-200 dark:bg-gray-700 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-blue-500"
                    style={{ width: `${Math.min(100, weight * 100 * 4)}%` }}
                  />
                </div>
                <span className="w-12 text-right text-sm tabular-nums text-gray-600 dark:text-gray-400">
                  {pct(weight)}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
