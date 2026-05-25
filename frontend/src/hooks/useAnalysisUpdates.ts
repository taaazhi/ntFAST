import { useEffect, useState, useCallback, useRef } from 'react';
import { analysesAPI } from '../services/api';

interface AnalysisUpdate {
  type: 'analysis_update';
  analysis_id: number;
  status: string;
  timestamp: string;
  [key: string]: any;
}

/**
 * Hook to get real-time analysis updates via polling.
 *
 * `onUpdate` is intentionally read via a ref to keep `pollAnalyses` identity
 * stable across renders — this prevents the polling interval from being
 * recreated every time the parent re-renders with a fresh callback.
 */
export function useAnalysisUpdates(onUpdate?: (update: AnalysisUpdate) => void) {
  const [latestUpdate, setLatestUpdate] = useState<AnalysisUpdate | null>(null);
  const [analyses, setAnalyses] = useState<any[]>([]);
  const [isPolling, setIsPolling] = useState(false);

  // Always-latest reference to the caller's callback — avoids stale closure
  // without forcing pollAnalyses to be re-created.
  const onUpdateRef = useRef(onUpdate);
  useEffect(() => {
    onUpdateRef.current = onUpdate;
  }, [onUpdate]);

  const pollAnalyses = useCallback(async () => {
    try {
      const data = await analysesAPI.getAll();
      setAnalyses(data);

      // Check for status changes and trigger updates
      if (data.length > 0) {
        const latestAnalysis = data[0];
        const update: AnalysisUpdate = {
          type: 'analysis_update',
          analysis_id: latestAnalysis.id,
          status: latestAnalysis.status,
          timestamp: latestAnalysis.updated_at || new Date().toISOString(),
        };

        setLatestUpdate(update);
        onUpdateRef.current?.(update);
      }
    } catch (error) {
      console.error('Failed to poll analyses:', error);
    }
  }, []);

  const startPolling = useCallback(() => {
    setIsPolling(true);
  }, []);

  const stopPolling = useCallback(() => {
    setIsPolling(false);
  }, []);

  useEffect(() => {
    if (!isPolling) return;

    // Poll immediately on start
    pollAnalyses();

    // Then poll every 5 seconds
    const interval = setInterval(pollAnalyses, 5000);

    return () => {
      clearInterval(interval);
    };
  }, [isPolling, pollAnalyses]);

  return {
    latestUpdate,
    analyses,
    isPolling,
    startPolling,
    stopPolling,
    refresh: pollAnalyses,
  };
}
