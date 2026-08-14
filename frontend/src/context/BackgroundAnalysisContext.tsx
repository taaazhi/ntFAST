/**
 * BackgroundAnalysisContext — Global context for running bank statement analysis
 * in the background. Users can navigate between pages while analysis is running.
 *
 * Shows a progress indicator in the Sidebar and delivers toast notifications
 * when the analysis completes or fails.
 */
import React, { createContext, useContext, useState, useCallback, useRef } from 'react';
import { toast } from 'sonner';
import { analysesAPI, KaspiAnalysisResult } from '../services/api';
import { buildReportFromAnalysis } from '../services/reportBuilder';
import { useAnalysisProgress, AnalysisProgressState } from '../hooks/useAnalysisProgress';

/** Как часто спрашивать статус, если сокет прогресса молчит. */
const POLL_INTERVAL_MS = 2000;
/** Предохранитель: воркер мог умереть, не сообщив об этом. */
const MAX_WAIT_MS = 15 * 60 * 1000;

const TERMINAL_OK = 'completed';
const TERMINAL_BAD = new Set(['failed', 'cancelled']);

/**
 * Дождаться, пока воркер закончит анализ.
 *
 * Опрос статуса, а не только сокет: WebSocket может отвалиться, вкладка —
 * заснуть, а Redis-канал прогресса вообще необязателен для работы системы.
 * Источником истины остаётся поле `status` в БД.
 */
async function waitForAnalysis(analysisId: number): Promise<number> {
  const deadline = Date.now() + MAX_WAIT_MS;

  while (Date.now() < deadline) {
    const analysis: any = await analysesAPI.getById(analysisId);

    if (analysis?.status === TERMINAL_OK) return analysisId;
    if (TERMINAL_BAD.has(analysis?.status)) {
      throw new Error(analysis?.conclusion || `Analysis ${analysis?.status}`);
    }

    await new Promise(resolve => setTimeout(resolve, POLL_INTERVAL_MS));
  }
  throw new Error('Analysis timed out');
}

export interface BackgroundAnalysisState {
  /** Is an analysis currently running? */
  isAnalyzing: boolean;
  /** Upload progress 0-100 */
  uploadProgress: number;
  /** File name being analyzed */
  fileName: string;
  /** WebSocket progress state */
  progress: AnalysisProgressState;
  /** The result once analysis completes (stays until dismissed) */
  result: KaspiAnalysisResult | null;
  /** Error message if analysis failed */
  error: string | null;
}

interface BackgroundAnalysisContextType extends BackgroundAnalysisState {
  /** Start a background analysis with the given file */
  startAnalysis: (file: File, onComplete?: () => void) => void;
  /** Dismiss the result (close the report) */
  dismissResult: () => void;
  /** Clear error */
  clearError: () => void;
}

const BackgroundAnalysisContext = createContext<BackgroundAnalysisContextType | null>(null);

export function BackgroundAnalysisProvider({ children }: { children: React.ReactNode }) {
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [fileName, setFileName] = useState('');
  const [result, setResult] = useState<KaspiAnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const analysisProgress = useAnalysisProgress();
  const onCompleteRef = useRef<(() => void) | null>(null);
  // Mirror isAnalyzing in a ref to read inside callbacks without making the
  // callback identity flip on every state change (avoids infinite useEffect loops).
  const isAnalyzingRef = useRef(false);
  isAnalyzingRef.current = isAnalyzing;

  const startAnalysis = useCallback((file: File, onComplete?: () => void) => {
    if (isAnalyzingRef.current) {
      toast.warning('Analysis is already running');
      return;
    }

    setIsAnalyzing(true);
    setUploadProgress(0);
    setFileName(file.name);
    setResult(null);
    setError(null);
    onCompleteRef.current = onComplete || null;

    const sessionId = analysisProgress.generateSessionId();
    analysisProgress.connect(sessionId);

    const finish = () => {
      setIsAnalyzing(false);
      if (onCompleteRef.current) {
        onCompleteRef.current();
        onCompleteRef.current = null;
      }
    };

    // Queue the file and wait for the worker. The HTTP call returns as soon
    // as the analysis row is created; the report itself is read back by id
    // once the worker signals completion over the progress socket.
    analysesAPI
      .uploadFile(file, setUploadProgress, sessionId)
      .then(({ id }) => waitForAnalysis(id))
      .then(async (analysisId) => {
        setResult(await buildReportFromAnalysis(analysisId));
        finish();
        setTimeout(() => analysisProgress.disconnect(), 2000);
      })
      .catch((err) => {
        console.error('Background analysis failed:', err);
        const detail = err?.response?.data?.detail;
        setError(
          (typeof detail === 'object' ? detail?.message : detail)
            || err?.message
            || 'Analysis failed'
        );
        finish();
        analysisProgress.disconnect();
      });
    // `analysisProgress` is a stable object from useAnalysisProgress; safe to
    // include without identity churn. `isAnalyzing` is intentionally read via
    // ref above to keep startAnalysis identity stable across re-renders.
  }, [analysisProgress]);

  const dismissResult = useCallback(() => {
    setResult(null);
  }, []);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return (
    <BackgroundAnalysisContext.Provider
      value={{
        isAnalyzing,
        uploadProgress,
        fileName,
        progress: analysisProgress,
        result,
        error,
        startAnalysis,
        dismissResult,
        clearError,
      }}
    >
      {children}
    </BackgroundAnalysisContext.Provider>
  );
}

export function useBackgroundAnalysis() {
  const ctx = useContext(BackgroundAnalysisContext);
  if (!ctx) throw new Error('useBackgroundAnalysis must be used inside BackgroundAnalysisProvider');
  return ctx;
}
