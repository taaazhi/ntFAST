/**
 * Вопросы следователя по конкретной выписке.
 *
 * Отчёт отвечает на вопросы, заданные заранее — те, под которые написаны
 * модули. Настоящее расследование состоит из других: «кому уходили крупные
 * суммы», «что было в марте», «какая норма про обналичивание». Здесь их
 * можно задать словами.
 *
 * Модель не читает выписку — она запрашивает данные инструментами, а считает
 * система. Поэтому под ответом показано, чем именно агент пользовался: это
 * не техническая подробность, а возможность проверить вывод, не веря на
 * слово.
 *
 * Имена физических лиц в ответах обезличены метками вида [PERSON_1] — так
 * же, как они обезличены на пути к модели.
 */
import { useState } from 'react';
import { motion } from 'framer-motion';
import { useTranslation } from 'react-i18next';
import { MessageSquare, Loader2, Send, Wrench, AlertTriangle, Scale } from 'lucide-react';
import { analysesAPI, AgentAnswer } from '../../services/api';

interface Props {
  analysisId?: number;
}

interface Exchange {
  question: string;
  answer: AgentAnswer | null;
  error?: string;
}

export function InvestigatorChat({ analysisId }: Props) {
  const { t } = useTranslation();
  const [question, setQuestion] = useState('');
  const [history, setHistory] = useState<Exchange[]>([]);
  const [loading, setLoading] = useState(false);

  const suggestions = [
    t('analyses.report.agent.suggest1'),
    t('analyses.report.agent.suggest2'),
    t('analyses.report.agent.suggest3'),
  ];

  const ask = async (text: string) => {
    const asked = text.trim();
    if (!asked || !analysisId || loading) return;

    setQuestion('');
    setLoading(true);
    // Вопрос показываем сразу: ответ занимает секунды, и молчащий экран
    // выглядит как поломка.
    setHistory((prev) => [...prev, { question: asked, answer: null }]);

    try {
      const answer = await analysesAPI.ask(analysisId, asked);
      setHistory((prev) =>
        prev.map((item, i) => (i === prev.length - 1 ? { ...item, answer } : item)),
      );
    } catch (e: any) {
      const detail = e?.response?.data?.detail || t('analyses.report.agent.failed');
      setHistory((prev) =>
        prev.map((item, i) => (i === prev.length - 1 ? { ...item, error: detail } : item)),
      );
    } finally {
      setLoading(false);
    }
  };

  if (!analysisId) return null;

  return (
    <section className="p-5 rounded-2xl border border-teal-200 bg-teal-50/40 dark:border-teal-800/40 dark:bg-teal-900/15">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2 mb-2">
        <MessageSquare className="w-5 h-5 text-teal-500" />
        {t('analyses.report.agent.title')}
      </h3>
      <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
        {t('analyses.report.agent.desc')}
      </p>

      {history.length === 0 && (
        <div className="flex flex-wrap gap-2 mb-4">
          {suggestions.map((text) => (
            <button
              key={text}
              onClick={() => ask(text)}
              disabled={loading}
              className="px-3 py-1.5 text-xs rounded-full border border-teal-300 text-teal-800 hover:bg-teal-100 disabled:opacity-50 dark:border-teal-700 dark:text-teal-200 dark:hover:bg-teal-800/30"
            >
              {text}
            </button>
          ))}
        </div>
      )}

      <div className="space-y-4 mb-4">
        {history.map((item, index) => (
          <motion.div
            key={index}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2 }}
          >
            <p className="text-sm font-medium text-gray-900 dark:text-white mb-2">
              {item.question}
            </p>

            {item.error && (
              <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-sm text-amber-800 dark:bg-amber-900/20 dark:border-amber-800/40 dark:text-amber-200">
                {item.error}
              </div>
            )}

            {!item.answer && !item.error && (
              <div className="flex items-center gap-2 text-sm text-gray-500">
                <Loader2 className="w-4 h-4 animate-spin" />
                {t('analyses.report.agent.thinking')}
              </div>
            )}

            {item.answer && (
              <div className="p-4 rounded-xl bg-white/70 dark:bg-gray-800/40">
                <div className="whitespace-pre-wrap text-sm leading-relaxed text-gray-800 dark:text-gray-200">
                  {item.answer.text}
                </div>

                {item.answer.stopped_early && (
                  <p className="mt-2 flex items-center gap-1.5 text-xs text-amber-700 dark:text-amber-400">
                    <AlertTriangle className="w-3.5 h-3.5" />
                    {t('analyses.report.agent.incomplete')}
                  </p>
                )}

                {item.answer.citations?.length > 0 && (
                  <ul className="mt-3 space-y-1">
                    {item.answer.citations.map((article) => (
                      <li key={article.citation} className="flex items-start gap-2 text-xs">
                        <Scale className="w-3.5 h-3.5 mt-0.5 text-teal-600 shrink-0" />
                        <span>
                          {article.url ? (
                            <a
                              href={article.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="font-medium text-teal-800 dark:text-teal-200 underline underline-offset-2"
                            >
                              {article.citation}
                            </a>
                          ) : (
                            <span className="font-medium">{article.citation}</span>
                          )}
                          {!article.verified && (
                            <span className="ml-2 text-amber-700 dark:text-amber-400">
                              {t('analyses.report.explained.unverified')}
                            </span>
                          )}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}

                {/* Чем агент пользовался — чтобы вывод можно было проверить. */}
                {item.answer.tool_calls?.length > 0 && (
                  <p className="mt-3 flex items-center gap-1.5 text-xs text-gray-400">
                    <Wrench className="w-3.5 h-3.5" />
                    {item.answer.tool_calls.map((c) => c.tool).join(', ')}
                    {item.answer.provider && <span>· {item.answer.provider}</span>}
                  </p>
                )}
              </div>
            )}
          </motion.div>
        ))}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          ask(question);
        }}
        className="flex gap-2"
      >
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={t('analyses.report.agent.placeholder')}
          disabled={loading}
          className="flex-1 px-4 py-2 rounded-xl border border-gray-300 bg-white text-sm dark:border-gray-600 dark:bg-gray-800 dark:text-white disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={loading || !question.trim()}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-teal-600 text-white text-sm font-medium hover:bg-teal-700 disabled:opacity-50"
        >
          <Send className="w-4 h-4" />
          {t('analyses.report.agent.send')}
        </button>
      </form>
    </section>
  );
}
