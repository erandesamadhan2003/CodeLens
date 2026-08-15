import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../../../api/client';

const GridBg = () => (
  <div className="absolute inset-0 z-0 opacity-[0.05] pointer-events-none"
    style={{ backgroundImage: `linear-gradient(#0A0A0A 1px, transparent 1px), linear-gradient(90deg, #0A0A0A 1px, transparent 1px)`, backgroundSize: '24px 24px' }} />
);

function GradeRing({ score, grade }: { score: number; grade: string }) {
  const c = score >= 80 ? '#22c55e' : score >= 60 ? '#eab308' : score >= 40 ? '#f97316' : '#ef4444';
  const r = 42, circ = 2 * Math.PI * r;
  const progress = (score / 100) * circ;
  return (
    <div className="relative flex items-center justify-center">
      <svg width="110" height="110" viewBox="0 0 110 110">
        <circle cx="55" cy="55" r={r} fill="none" stroke="#e5e5e5" strokeWidth="8" />
        <circle cx="55" cy="55" r={r} fill="none" stroke={c} strokeWidth="8"
          strokeDasharray={`${progress} ${circ}`} strokeLinecap="round" transform="rotate(-90 55 55)" />
      </svg>
      <div className="absolute text-center">
        <div className="font-display font-bold text-2xl leading-none" style={{ color: c }}>{grade}</div>
        <div className="font-mono text-xs text-muted">{score}/100</div>
      </div>
    </div>
  );
}

function CheckItem({ label, value, good }: { label: string; value?: boolean | string; good?: boolean }) {
  const isGood = good !== undefined ? good : value === true;
  return (
    <div className={`flex items-center justify-between px-3 py-2 rounded-[4px] border ${isGood ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
      <span className="font-mono text-xs">{label}</span>
      <span className={`font-bold text-xs ${isGood ? 'text-green-600' : 'text-red-500'}`}>{isGood ? '✓ YES' : '✗ NO'}</span>
    </div>
  );
}

function MissingDoc({ item }: { item: any }) {
  return (
    <div className="flex items-start gap-3 px-3 py-2 bg-yellow-50 border border-yellow-200 rounded-[4px]">
      <span className="shrink-0 text-yellow-500 mt-0.5">⚠</span>
      <div className="min-w-0">
        <div className="font-mono text-xs text-muted">{item.file}:{item.line}</div>
        <div className="font-mono text-xs font-bold truncate">{item.function}()</div>
      </div>
    </div>
  );
}

export default function DocumentsDashboard() {
  const { repoId } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState<any>(null);
  const [runInfo, setRunInfo] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [tab, setTab] = useState<'overview' | 'issues' | 'missing'>('overview');

  const fetchData = useCallback(async () => {
    if (!repoId) return;
    try {
      setIsLoading(true);
      const runRes = await api.get(`/api/v1/runs?repoId=${repoId}&limit=1`);
      const run = (runRes.data?.data || runRes.data || [])[0];
      if (!run) { setIsLoading(false); return; }
      setRunInfo(run);
      const res = await api.get(`/api/v1/results/run/${run.id}/docryx`);
      setData(res.data?.data?.result_data || res.data?.result_data);
    } catch { } finally { setIsLoading(false); }
  }, [repoId]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleAnalyze = async () => {
    if (!repoId || isAnalyzing) return;
    setIsAnalyzing(true);
    try {
      await api.post('/api/v1/runs', { repoId, engines: ['docryx'] });
      let tries = 0;
      const poll = setInterval(async () => {
        tries++;
        if (tries > 40) { clearInterval(poll); setIsAnalyzing(false); return; }
        const runRes = await api.get(`/api/v1/runs?repoId=${repoId}&limit=1`);
        const run = (runRes.data?.data || runRes.data || [])[0];
        if (run) {
          const res = await api.get(`/api/v1/results/run/${run.id}/docryx`);
          const rd = res.data?.data?.result_data || res.data?.result_data;
          if (rd?.status === 'completed') { clearInterval(poll); setIsAnalyzing(false); setData(rd); setRunInfo(run); }
        }
      }, 4000);
    } catch { setIsAnalyzing(false); }
  };

  const score = data?.overallScore ?? 0;
  const grade = data?.grade ?? 'F';
  const teamScore = data?.teamReadinessScore ?? 0;
  const teamGrade = data?.teamReadinessGrade ?? 'F';
  const findings: any[] = data?.findings || [];
  const missingDocs: any[] = data?.missingDocs || [];

  return (
    <div className="relative min-h-screen bg-paper text-ink flex flex-col font-sans">
      <GridBg />
      <header className="relative z-10 w-full px-6 py-4 flex items-center gap-4 border-b-2 border-ink bg-paper">
        <button onClick={() => navigate('/home')} className="w-10 h-10 flex items-center justify-center border-2 border-ink bg-surface shadow-[2px_2px_0px_#0A0A0A] active:translate-x-[2px] active:translate-y-[2px] active:shadow-none transition-all rounded-[6px]">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" /></svg>
        </button>
        <div className="flex-1">
          <div className="font-display font-bold text-xl uppercase tracking-tight">Documentation (Docryx)</div>
          {runInfo && <div className="font-mono text-xs text-muted">{runInfo.repo_full_name} • {runInfo.branch}</div>}
        </div>
        <button id="doc-analyze-btn" onClick={handleAnalyze} disabled={isAnalyzing}
          className={`flex items-center gap-2 px-4 py-2 font-display font-bold text-sm uppercase border-2 border-ink rounded-[6px] shadow-[2px_2px_0px_#0A0A0A] transition-all ${isAnalyzing ? 'bg-muted text-paper cursor-not-allowed' : 'bg-ink text-paper hover:bg-gray-800'}`}>
          {isAnalyzing ? 'Scanning...' : '📚 Scan Now'}
        </button>
      </header>

      <main className="relative z-10 flex-1 w-full max-w-7xl mx-auto px-6 py-8 flex flex-col gap-6">
        {isLoading ? (
          <div className="flex-1 flex items-center justify-center"><div className="font-mono text-xl animate-pulse text-muted">Loading documentation results...</div></div>
        ) : !data ? (
          <div className="flex-1 flex flex-col items-center justify-center gap-6 p-10 border-2 border-dashed border-ink rounded-[6px]">
            <div className="text-center"><div className="font-display font-bold text-2xl uppercase mb-2">No Documentation Scan Yet</div><p className="text-muted font-mono text-sm">Analyses README, license, code comments, docstrings, and team readiness</p></div>
            <button onClick={handleAnalyze} className="px-6 py-3 bg-ink text-paper font-display font-bold uppercase border-2 border-ink rounded-[6px] shadow-[4px_4px_0px_#0A0A0A]">📚 Scan Documentation</button>
          </div>
        ) : (
          <>
            {/* Score overview */}
            <div className="bg-surface border-2 border-ink rounded-[6px] shadow-[4px_4px_0px_#0A0A0A] p-6 flex flex-wrap items-center gap-6">
              <GradeRing score={score} grade={grade} />
              <div className="flex-1 min-w-0">
                <h2 className="font-display font-bold text-xl uppercase">Documentation Quality</h2>
                {data.aiSummary ? (
                  <p className="mt-1 text-sm text-muted leading-relaxed max-w-2xl">{data.aiSummary}</p>
                ) : (
                  <p className="mt-1 text-sm text-muted">{data.filesAnalyzed} files analyzed • {data.missingDocsCount} functions without docstrings</p>
                )}
                <div className="flex flex-wrap gap-4 mt-3 font-mono text-xs">
                  <span>Comment ratio: <strong>{((data.codeCommentRatio || 0) * 100).toFixed(0)}%</strong></span>
                  <span>Docstring coverage: <strong>{((data.docFunctionRatio || 0) * 100).toFixed(0)}%</strong></span>
                  <span>Files: <strong>{data.filesAnalyzed || 0}</strong></span>
                </div>
              </div>
              <div className="text-center">
                <div className="text-xs font-mono font-bold text-muted uppercase">Team Readiness</div>
                <GradeRing score={teamScore} grade={teamGrade} />
              </div>
            </div>

            {/* Tabs */}
            <div className="flex gap-1 border-b-2 border-ink">
              {(['overview', 'issues', 'missing'] as const).map(t => (
                <button key={t} onClick={() => setTab(t)} className={`px-4 py-2 font-display font-bold text-sm uppercase border-2 border-b-0 rounded-t-[6px] transition-all ${tab === t ? 'bg-ink text-paper border-ink' : 'border-transparent text-muted hover:text-ink'}`}>
                  {t === 'overview' ? '📋 Overview' : t === 'issues' ? `⚠ Issues (${findings.length})` : `📝 Missing Docs (${missingDocs.length})`}
                </button>
              ))}
            </div>

            {tab === 'overview' && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <h3 className="font-display font-bold uppercase mb-3">Repository Docs</h3>
                  <div className="flex flex-col gap-2">
                    <CheckItem label="README" value={data.hasReadme} />
                    <CheckItem label="LICENSE" value={data.hasLicense} />
                    <CheckItem label="CONTRIBUTING.md" value={data.hasContributing} />
                    <CheckItem label="CHANGELOG" value={data.hasChangelog} />
                    <CheckItem label="Docs Folder" value={data.hasDocs} />
                    <CheckItem label="API Documentation" value={data.hasApiDocs} />
                    <CheckItem label=".env.example" value={data.hasEnvExample} />
                  </div>
                </div>
                <div>
                  <h3 className="font-display font-bold uppercase mb-3">Team Readiness</h3>
                  <div className="flex flex-col gap-2">
                    <CheckItem label="PR Template" value={data.hasPrTemplate} />
                    <CheckItem label="Issue Template" value={data.hasIssueTemplate} />
                    <CheckItem label="CODEOWNERS" value={data.hasCodeowners} />
                    <CheckItem label="CI/CD Config" value={data.hasCiConfig} />
                    <CheckItem label="Architecture Docs" value={data.hasArchDoc} />
                    <CheckItem label="README" value={data.hasReadme} />
                    <CheckItem label="Contributing Guide" value={data.hasContributing} />
                  </div>
                </div>
              </div>
            )}

            {tab === 'issues' && (
              <div className="flex flex-col gap-3">
                {findings.length === 0 ? (
                  <div className="p-8 border-2 border-dashed border-green-400 rounded-[6px] text-center">
                    <div className="text-2xl mb-2">✅</div>
                    <div className="font-display font-bold text-green-600 uppercase">No Issues Found</div>
                    <div className="text-muted text-sm font-mono mt-1">Your documentation is in great shape!</div>
                  </div>
                ) : findings.map((f, i) => (
                  <div key={i} className={`p-4 rounded-[6px] border-2 ${f.severity === 'HIGH' ? 'border-orange-400 bg-orange-50' : f.severity === 'MEDIUM' ? 'border-yellow-400 bg-yellow-50' : 'border-blue-300 bg-blue-50'}`}>
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`text-xs font-bold uppercase px-1.5 py-0.5 rounded ${f.severity === 'HIGH' ? 'bg-orange-500 text-white' : f.severity === 'MEDIUM' ? 'bg-yellow-400 text-black' : 'bg-blue-400 text-white'}`}>{f.severity}</span>
                      <span className="font-display font-bold text-sm">{f.message}</span>
                    </div>
                    <p className="text-sm text-muted ml-1">💡 {f.recommendation}</p>
                  </div>
                ))}
              </div>
            )}

            {tab === 'missing' && (
              <div>
                <p className="font-mono text-sm text-muted mb-4">{missingDocs.length} functions detected without docstrings</p>
                {missingDocs.length === 0 ? (
                  <div className="p-8 border-2 border-dashed border-green-400 rounded-[6px] text-center">
                    <div className="text-2xl mb-2">✅</div>
                    <div className="font-display font-bold text-green-600 uppercase">All functions are documented!</div>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
                    {missingDocs.map((item, i) => <MissingDoc key={i} item={item} />)}
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
