import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../../../api/client';
import InfrastructureResultsPanel from '../components/InfrastructureResultsPanel';

const GridBg = () => (
  <div
    className="absolute inset-0 z-0 opacity-[0.05] pointer-events-none"
    style={{
      backgroundImage: `linear-gradient(#0A0A0A 1px, transparent 1px), linear-gradient(90deg, #0A0A0A 1px, transparent 1px)`,
      backgroundSize: '24px 24px'
    }}
  />
);

export default function InfrastructureDashboard() {
  const { repoId } = useParams();
  const navigate = useNavigate();

  const [runDetails, setRunDetails] = useState<any>(null);
  const [infraResults, setInfraResults] = useState<any>(null);
  const [infraFindings, setInfraFindings] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [error, setError] = useState('');

  const fetchResults = useCallback(async () => {
    if (!repoId) return;
    try {
      setIsLoading(true);
      setError('');
      const runRes = await api.get(`/api/v1/runs?repoId=${repoId}&limit=1`);
      const latestRun = runRes.data[0];

      if (!latestRun) {
        setIsLoading(false);
        return;
      }

      setRunDetails(latestRun);

      const [infraRes, findingsRes] = await Promise.all([
        api.get(`/api/v1/infrastructure/analyses/${latestRun.id}`),
        api.get(`/api/v1/infrastructure/analyses/${latestRun.id}/findings`),
      ]);
      setInfraResults(infraRes.data);
      setInfraFindings(Array.isArray(findingsRes.data) ? findingsRes.data : []);
    } catch (err: any) {
      setError(err?.message || 'Failed to load results.');
    } finally {
      setIsLoading(false);
    }
  }, [repoId]);

  useEffect(() => {
    fetchResults();
  }, [fetchResults]);

  const handleGenerateRecommendations = async () => {
    if (!repoId || isAnalyzing) return;
    try {
      setIsAnalyzing(true);
      setError('');
      await api.post('/api/v1/infrastructure/analyze', { repositoryId: repoId });
      // Poll for results every 5 seconds for up to 3 minutes
      let attempts = 0;
      const poll = setInterval(async () => {
        attempts++;
        if (attempts > 36) {
          clearInterval(poll);
          setIsAnalyzing(false);
          setError('Analysis timed out. Please try again.');
          return;
        }
        try {
          const runRes = await api.get(`/api/v1/runs?repoId=${repoId}&limit=1`);
          const latestRun = runRes.data[0];
          if (latestRun) {
            const infraRes = await api.get(`/api/v1/infrastructure/analyses/${latestRun.id}`);
            const recs = infraRes.data?.recommendations?.recommendations || [];
            if (recs.length > 0) {
              clearInterval(poll);
              setIsAnalyzing(false);
              await fetchResults();
            }
          }
        } catch {
          // keep polling
        }
      }, 5000);
    } catch (err: any) {
      setIsAnalyzing(false);
      setError(err?.message || 'Failed to trigger analysis.');
    }
  };

  const handleApplyRecommendation = async (runId: string, recId: string): Promise<string> => {
    const res = await api.post(
      `/api/v1/infrastructure/analyses/${runId}/recommendations/${recId}/apply`,
      {}
    );
    return res.data?.pr_url || '';
  };

  const recommendations = infraResults?.recommendations?.recommendations || [];
  const scores = infraResults?.recommendations || {};
  const aiPowered = infraResults?.recommendations?.ai_powered || false;

  return (
    <div className="relative min-h-screen bg-paper text-ink flex flex-col font-sans">
      <GridBg />

      <header className="relative z-10 w-full px-6 md:px-12 py-6 flex items-center gap-6 border-b-4 border-ink bg-paper">
        <button
          onClick={() => navigate('/home')}
          id="infra-back-btn"
          className="w-12 h-12 flex items-center justify-center border-[3px] border-ink bg-surface shadow-[4px_4px_0px_#0A0A0A] active:translate-x-[4px] active:translate-y-[4px] active:shadow-none transition-all rounded-[8px]"
          title="Back to Dashboard"
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
            <line x1="19" y1="12" x2="5" y2="12" />
            <polyline points="12 19 5 12 12 5" />
          </svg>
        </button>

        <div className="flex-1 min-w-0">
          <span className="font-display font-bold text-3xl uppercase tracking-tight truncate block">Infrastructure</span>
          {runDetails && (
            <span className="font-mono text-sm text-muted mt-1 truncate bg-surface px-3 py-1 inline-block rounded-full border border-ink/20">
              {runDetails.repo_full_name} • {runDetails.branch} • {runDetails.commit_sha?.substring(0, 7)}
            </span>
          )}
        </div>

        {/* AI Badge */}
        {aiPowered && (
          <span className="hidden sm:flex items-center gap-2 px-4 py-2 bg-ink text-paper font-mono text-sm font-bold rounded-[8px] border-[3px] border-ink shadow-[4px_4px_0px_#0A0A0A]">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm0 18a8 8 0 1 1 8-8 8 8 0 0 1-8 8zm-1-13h2v6h-2zm0 8h2v2h-2z"/></svg>
            AI POWERED
          </span>
        )}

        {/* Generate Button */}
        <button
          id="infra-generate-btn"
          onClick={handleGenerateRecommendations}
          disabled={isAnalyzing}
          className={`shrink-0 flex items-center gap-3 px-6 py-3 font-display font-bold text-lg uppercase border-[3px] border-ink rounded-[8px] shadow-[4px_4px_0px_#0A0A0A] active:translate-x-[2px] active:translate-y-[2px] active:shadow-[2px_2px_0px_#0A0A0A] transition-all ${
            isAnalyzing
              ? 'bg-muted text-paper cursor-not-allowed'
              : 'bg-accent text-ink hover:bg-accent/80'
          }`}
        >
          {isAnalyzing ? (
            <>
              <svg className="animate-spin" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                <circle cx="12" cy="12" r="10" strokeOpacity="0.25" />
                <path d="M12 2a10 10 0 0 1 10 10" />
              </svg>
              Scanning...
            </>
          ) : (
            <>
              <span>🏗️</span>
              Scan Now
            </>
          )}
        </button>
      </header>

      {/* Main Content */}
      <main className="relative z-10 flex-1 w-full flex flex-col px-6 md:px-12 py-10 gap-10">
        {isLoading ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="font-mono text-xl animate-pulse text-muted">Loading Infrastructure results...</div>
          </div>
        ) : error ? (
          <div className="flex-1 flex flex-col items-center justify-center gap-4 p-10 bg-surface border-2 border-ink rounded-[6px] shadow-[4px_4px_0px_#0A0A0A]">
            <div className="font-mono text-xl text-danger font-bold uppercase">{error}</div>
            <button
              onClick={() => navigate('/home')}
              className="font-display font-bold uppercase border-2 border-ink px-6 py-2 shadow-[2px_2px_0px_#0A0A0A] bg-paper hover:bg-surface"
            >
              Return to Dashboard
            </button>
          </div>
        ) : infraResults ? (
          <InfrastructureResultsPanel
            runId={runDetails?.id}
            score={scores.overall_score || (infraFindings.filter((f: any) => f.severity === 'CRITICAL').length > 0 ? 60 : 101)}
            scores={scores}
            architecture={infraResults.architecture}
            discovery={infraResults.discovery}
            findings={infraFindings}
            recommendations={recommendations}
            aiPowered={aiPowered}
            onApply={handleApplyRecommendation}
          />
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center gap-6 p-10 bg-surface border-2 border-dashed border-ink rounded-[6px]">
            <div className="text-center">
              <div className="font-display font-bold text-2xl uppercase mb-2">No Analysis Yet</div>
              <div className="text-muted font-mono text-sm">Click "Scan Now" to analyze this repository's infrastructure</div>
            </div>
            <button
              id="infra-generate-empty-btn"
              onClick={handleGenerateRecommendations}
              disabled={isAnalyzing}
              className="flex items-center gap-2 px-6 py-3 font-display font-bold text-base uppercase border-[3px] border-ink rounded-[8px] shadow-[4px_4px_0px_#0A0A0A] bg-accent text-ink hover:bg-accent/80 active:translate-x-[2px] active:translate-y-[2px] active:shadow-[2px_2px_0px_#0A0A0A] transition-all"
            >
              <span>🏗️</span>
              {isAnalyzing ? 'Scanning...' : 'Run Infrastructure Scan'}
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
