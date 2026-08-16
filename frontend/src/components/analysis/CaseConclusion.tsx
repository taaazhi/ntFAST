/**
 * Заключение по делу — связный вывод, составленный языковой моделью.
 *
 * Единственное место, где модель делает работу, которую нечем заменить:
 * собирает факты одиннадцати модулей, графа связей и корпуса норм в текст,
 * который читает следователь. Всё остальное в отчёте — числа и флаги; здесь
 * из них получается картина.
 *
 * Заключение не составляется само при открытии отчёта. Это решение
 * следователя: генерация занимает около полуминуты и обращается к модели,
 * а отчёт должен открываться сразу.
 *
 * Показывается вместе с признаком достоверности. Заключение, где нашлось
 * число, которого нет в фактах, или неподтверждённая норма, выводится с
 * оговоркой — но выводится. Скрыть его значило бы решить за следователя,
 * что ему видеть.
 */
import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { useTranslation } from 'react-i18next';
import { FileText, Loader2, ShieldCheck, AlertTriangle, Scale, RefreshCw } from 'lucide-react';
import { analysesAPI, AnalysisConclusion } from '../../services/api';

interface Props {
  analysisId?: number;
}

export function CaseConclusion({ analysisId }: Props) {
  const { t } = useTranslation();
  const [conclusion, setConclusion] = useState<AnalysisConclusion | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Показываем уже составленное, если оно есть. Модель при этом не трогаем.
  useEffect(() => {
    if (!analysisId) return;
    let cancelled = false;

    analysesAPI
      .getConclusion(analysisId)
      .then((saved) => {
        if (!cancelled && saved.exists) setConclusion(saved);
      })
      .catch(() => {
        /* Нет сохранённого — обычное состояние, не ошибка. */
      });

    return () => {
      cancelled = true;
    };
  }, [analysisId]);

  const build = async () => {
    if (!analysisId) return;
    setLoading(true);
    setError(null);
    try {
      setConclusion(await analysesAPI.buildConclusion(analysisId));
    } catch (e: any) {
      // Отсутствие модели — не сбой системы, а её состояние: сообщение с
      // бэкенда объясняет, что включить.
      setError(e?.response?.data?.detail || t('analyses.report.conclusion.failed'));
    } finally {
      setLoading(false);
    }
  };

  if (!analysisId) return null;

  return (
    <section className="p-5 rounded-2xl border border-indigo-200 bg-indigo-50/50 dark:border-indigo-800/40 dark:bg-indigo-900/15">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
          <FileText className="w-5 h-5 text-indigo-500" />
          {t('analyses.report.conclusion.title')}
        </h3>

        <button
          onClick={build}
          disabled={loading}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-60"
        >
          {loading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              {t('analyses.report.conclusion.building')}
            </>
          ) : (
            <>
              {conclusion ? <RefreshCw className="w-4 h-4" /> : <FileText className="w-4 h-4" />}
              {conclusion
                ? t('analyses.report.conclusion.rebuild')
                : t('analyses.report.conclusion.build')}
            </>
          )}
        </button>
      </div>

      <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
        {t('analyses.report.conclusion.desc')}
      </p>

      {error && (
        <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-sm text-amber-800 dark:bg-amber-900/20 dark:border-amber-800/40 dark:text-amber-200">
          {error}
        </div>
      )}

      {conclusion?.text && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.2 }}>
          {/* Оговорка идёт до текста: сначала «чему верить», потом сам текст. */}
          {conclusion.is_trustworthy ? (
            <div className="flex items-center gap-2 mb-3 text-xs text-green-700 dark:text-green-400">
              <ShieldCheck className="w-4 h-4" />
              {t('analyses.report.conclusion.verified')}
              {conclusion.provider && (
                <span className="text-gray-400">· {conclusion.provider}</span>
              )}
            </div>
          ) : (
            <div className="flex items-start gap-2 mb-3 p-3 rounded-xl bg-amber-50 border border-amber-200 dark:bg-amber-900/20 dark:border-amber-800/40">
              <AlertTriangle className="w-4 h-4 mt-0.5 text-amber-600 shrink-0" />
              <div className="text-xs text-amber-800 dark:text-amber-200">
                <p className="font-medium">{t('analyses.report.conclusion.unverified')}</p>
                {conclusion.invented_numbers?.length > 0 && (
                  <p className="mt-1">
                    {t('analyses.report.conclusion.unknownNumbers')}:{' '}
                    {conclusion.invented_numbers.slice(0, 5).join(', ')}
                  </p>
                )}
              </div>
            </div>
          )}

          <div className="whitespace-pre-wrap text-sm leading-relaxed text-gray-800 dark:text-gray-200">
            {conclusion.text}
          </div>

          {conclusion.citations?.length > 0 && (
            <ul className="mt-4 space-y-1.5">
              {conclusion.citations.map((article) => (
                <li key={article.citation} className="flex items-start gap-2 text-sm">
                  <Scale className="w-4 h-4 mt-0.5 text-indigo-500 shrink-0" />
                  <span>
                    {article.url ? (
                      <a
                        href={article.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-medium text-indigo-800 dark:text-indigo-200 underline decoration-indigo-300 underline-offset-2"
                      >
                        {article.citation}
                      </a>
                    ) : (
                      <span className="font-medium text-gray-700 dark:text-gray-300">
                        {article.citation}
                      </span>
                    )}
                    {article.title && (
                      <span className="text-gray-600 dark:text-gray-400"> — {article.title}</span>
                    )}
                    {!article.verified && (
                      <span className="ml-2 text-xs text-amber-700 dark:text-amber-400">
                        {t('analyses.report.explained.unverified')}
                      </span>
                    )}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </motion.div>
      )}
    </section>
  );
}
