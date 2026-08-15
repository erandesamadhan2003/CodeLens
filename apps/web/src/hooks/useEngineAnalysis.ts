import { useEffect, useState, useCallback, useRef } from 'react';
import { api } from '../api/client';
import { useWebSocket } from './useWebSocket';

export interface EngineResult {
  engine: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'analyzing';
  result_data: any;
  error_message: string | null;
  duration_ms: number | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface Run {
  id: string;
  status: string;
  branch: string;
  commit_sha: string;
  repo_full_name?: string;
  created_at: string;
  engineResults: EngineResult[];
}

export function useEngineAnalysis(repoId: string | undefined) {
  const [latestRun, setLatestRun] = useState<Run | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isTriggering, setIsTriggering] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'info' | 'error' } | null>(null);
  const { subscribe } = useWebSocket();
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const showToast = (message: string, type: 'success' | 'info' | 'error' = 'info') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 5000);
  };

  const fetchLatestRun = useCallback(async () => {
    if (!repoId) return;
    try {
      const runRes = await api.get(`/api/v1/runs?repoId=${repoId}&limit=1`);
      const runs = runRes.data?.data || runRes.data || [];
      const run = Array.isArray(runs) ? runs[0] : null;
      if (!run) { setIsLoading(false); return; }

      const resultsRes = await api.get(`/api/v1/results/run/${run.id}`);
      const engineResults: EngineResult[] = resultsRes.data?.data || resultsRes.data || [];

      setLatestRun({ ...run, engineResults });
    } catch (err) {
      console.error('Failed to fetch run', err);
    } finally {
      setIsLoading(false);
    }
  }, [repoId]);

  const triggerAnalysis = useCallback(async (engines?: string[]) => {
    if (!repoId || isTriggering) return;
    setIsTriggering(true);
    showToast('Analysis started — engines are processing...', 'info');
    try {
      await api.post('/api/v1/runs', { repoId, engines: engines || ['infraq', 'infilra', 'depra', 'docryx'] });
      // Start polling until run starts
      pollingRef.current = setInterval(fetchLatestRun, 3000);
      setTimeout(() => {
        if (pollingRef.current) clearInterval(pollingRef.current);
      }, 30000); // stop polling after 30s (WS takes over)
    } catch (err: any) {
      showToast(err?.message || 'Failed to trigger analysis', 'error');
    } finally {
      setIsTriggering(false);
    }
  }, [repoId, isTriggering, fetchLatestRun]);

  // WebSocket listeners
  useEffect(() => {
    const unsubs: (() => void)[] = [];

    unsubs.push(subscribe('engine:complete', (data) => {
      const engineName: Record<string, string> = {
        infraq: 'Infrastructure', infilra: 'Security',
        depra: 'Dependencies', docryx: 'Documentation'
      };
      showToast(`✅ ${engineName[data.engine] || data.engine} engine completed`, 'success');
      fetchLatestRun();
    }));

    unsubs.push(subscribe('run:complete', () => {
      showToast('🎉 All engines finished! Analysis complete.', 'success');
      fetchLatestRun();
      if (pollingRef.current) clearInterval(pollingRef.current);
    }));

    unsubs.push(subscribe('engine:failed', (data) => {
      showToast(`❌ ${data.engine} engine failed: ${data.error}`, 'error');
      fetchLatestRun();
    }));

    return () => unsubs.forEach(u => u());
  }, [subscribe, fetchLatestRun]);

  useEffect(() => {
    fetchLatestRun();
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [fetchLatestRun]);

  const getEngineResult = (engine: string): EngineResult | undefined =>
    latestRun?.engineResults?.find(er => er.engine === engine);

  return { latestRun, isLoading, isTriggering, triggerAnalysis, getEngineResult, toast };
}
