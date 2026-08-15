/**
 * Источник регулярного дохода и на чём он определён.
 *
 * Показывать это обязательно, а не желательно. Признак зарплаты задаёт тип
 * счёта, а тип счёта меняет веса всех детекторов: на замере один этот признак
 * двигает композитный балл с 17.4 LOW до 63.0 HIGH. Скрытый вход, меняющий
 * вывод, — это ровно та непрозрачность, из-за которой отчёту нельзя доверять.
 *
 * Выписка слова «зарплата» обычно не содержит: приходит «Пополнение» от ТОО.
 * Вывод сделан по регулярности, поэтому рядом с источником печатается
 * основание — сколько выплат, за сколько месяцев, какого числа, — чтобы
 * следователь мог его проверить или отвергнуть.
 */
import { useTranslation } from 'react-i18next';
import { Wallet, ShieldCheck } from 'lucide-react';
import { EnrichmentInfo } from '../../services/api';

interface Props {
  enrichment?: EnrichmentInfo | null;
  formatCurrency: (value: number) => string;
}

export function IncomeSources({ enrichment, formatCurrency }: Props) {
  const { t } = useTranslation();
  const sources = enrichment?.salary_sources ?? [];

  if (sources.length === 0) return null;

  return (
    <section>
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2 flex items-center gap-2">
        <Wallet className="w-5 h-5 text-emerald-500" />
        {t('analyses.report.income.title')}
      </h3>
      <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
        {t('analyses.report.income.desc')}
      </p>

      <div className="space-y-3">
        {sources.map((source, index) => (
          <div
            key={`${source.counterparty}-${index}`}
            className="p-4 rounded-xl border border-emerald-200 bg-emerald-50/60 dark:border-emerald-800/40 dark:bg-emerald-900/15"
          >
            <div className="flex flex-wrap items-center justify-between gap-2 mb-1">
              <span className="font-medium text-gray-900 dark:text-white break-all">
                {source.counterparty}
              </span>
              <span className="text-sm font-semibold tabular-nums text-emerald-700 dark:text-emerald-300">
                {formatCurrency(source.median_amount)}
              </span>
            </div>

            <p className="text-xs text-gray-600 dark:text-gray-400">{source.reason}</p>
          </div>
        ))}
      </div>

      {/* Данные покидали периметр только если модель действительно вызывалась. */}
      <div className="mt-4 flex items-start gap-2 text-xs text-gray-500 dark:text-gray-400">
        <ShieldCheck className="w-4 h-4 mt-0.5 text-gray-400 shrink-0" />
        <span>
          {enrichment?.privacy
            ? t('analyses.report.income.privacyMasked')
            : t('analyses.report.income.privacyLocal')}
        </span>
      </div>
    </section>
  );
}
