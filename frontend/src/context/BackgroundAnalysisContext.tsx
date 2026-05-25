/**
 * BackgroundAnalysisContext — Global context for running bank statement analysis
 * in the background. Users can navigate between pages while analysis is running.
 *
 * Shows a progress indicator in the Sidebar and delivers toast notifications
 * when the analysis completes or fails.
 */
import React, { createContext, useContext, useState, useCallback, useRef } from 'react';
import { toast } from 'sonner';
import { bankAnalysisAPI, KaspiAnalysisResult } from '../services/api';
import { useAnalysisProgress, AnalysisProgressState } from '../hooks/useAnalysisProgress';

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

    // Run analysis in background (non-blocking)
    bankAnalysisAPI
      .analyze(file, setUploadProgress, sessionId)
      .then((analysisResult) => {
        setResult(analysisResult);
        setIsAnalyzing(false);
        setTimeout(() => analysisProgress.disconnect(), 2000);

        // Callback to reload data on the Analyses page
        if (onCompleteRef.current) {
          onCompleteRef.current();
          onCompleteRef.current = null;
        }
      })
      .catch((err) => {
        console.error('Background analysis failed:', err);
        setError(err?.response?.data?.detail || err?.message || 'Analysis failed');
        setIsAnalyzing(false);
        analysisProgress.disconnect();

        if (onCompleteRef.current) {
          onCompleteRef.current();
          onCompleteRef.current = null;
        }
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
