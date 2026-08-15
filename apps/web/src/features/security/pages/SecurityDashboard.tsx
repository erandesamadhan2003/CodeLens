import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../../../api/client';

const GridBg = () => (
  <div className="absolute inset-0 z-0 opacity-[0.05] pointer-events-none"
    style={{ backgroundImage: `linear-gradient(#0A0A0A 1px, transparent 1px), linear-gradient(90deg, #0A0A0A 1px, transparent 1px)`, backgroundSize: '24px 24px' }} />
);

const SEV_STYLE: Record<string, string> = {
  CRITICAL: 'bg-red-600 text-white',
  HIGH: 'bg-orange-500 text-white',
  MEDIUM: 'bg-yellow-400 text-black',
  LOW: 'bg-blue-400 text-white',
  UNKNOWN: 'bg-gray-400 text-white',
};
const CAT_ICON: Record<string, string> = {
  secrets: '🔑', injection: '💉', xss: '🕸️', tls: '🔒', cryptography: '🔐', config: '⚙️', default: '🛡️'
};

function FindingCard({ f }: { f: any }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={`border-l-4 ${f.severity === 'CRITICAL' ? 'border-red-600' : f.severity === 'HIGH' ? 'border-orange-500' : f.severity === 'MEDIUM' ? 'border-yellow-400' : 'border-blue-400'} bg-paper rounded-r-[6px] overflow-hidden`}>
      <button className="w-full flex items-center gap-3 p-4 text-left hover:bg-surface transition-colors" onClick={() => setOpen(o => !o)}>
        <span className="text-xl shrink-0">{CAT_ICON[f.category] || CAT_ICON.default}</span>
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-0.5">
            <span className={`px-1.5 py-0.5 text-[10px] font-bold rounded uppercase ${SEV_STYLE[f.severity] || SEV_STYLE.UNKNOWN}`}>{f.severity}</span>
            <span className="font-mono text-xs text-muted truncate max-w-[200px]">{f.file}:{f.line}</span>
          </div>
          <div className="font-display font-bold text-sm">{f.title}</div>
        </div>
        <svg className={`transition-transform shrink-0 ${open ? 'rotate-180' : ''}`} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9" /></svg>
      </button>
      {open && (
        <div className="px-4 pb-4 flex flex-col gap-3 border-t border-ink/10">
          {f.snippet && (
            <pre className="mt-3 text-xs font-mono bg-[#0d0d0d] text-green-400 p-3 rounded overflow-x-auto">
              {f.snippet}
            </pre>
          )}
          {f.context && (
            <details className="text-xs">
              <summary className="cursor-pointer text-muted font-mono uppercase">Context</summary>
              <pre className="mt-2 font-mono bg-surface p-2 rounded overflow-x-auto text-muted">{f.context}</pre>
            </details>
          )}
        </div>
      )}
    </div>
  );
}

export default function SecurityDashboard() {
  const { repoId } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState<any>(null);
  const [runInfo, setRunInfo] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState<string>('ALL');
  const [search, setSearch] = useState('');

  const fetchData = useCallback(async () => {
    if (!repoId) return;
    try {
      setIsLoading(true);
      const runRes = await api.get(`/api/v1/runs?repoId=${repoId}&limit=1`);
      const run = (runRes.data?.data || runRes.data || [])[0];
      if (!run) { setIsLoading(false); return; }
      setRunInfo(run);
      const res = await api.get(`/api/v1/results/run/${run.id}/infilra`);
      setData(res.data?.data?.result_data || res.data?.result_data);
    } catch (e: any) { setError(e?.message || 'Failed to load'); }
    finally { setIsLoading(false); }
  }, [repoId]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleAnalyze = async () => {
    if (!repoId || isAnalyzing) return;
    setIsAnalyzing(true);
    try {
      await api.post('/api/v1/runs', { repoId, engines: ['infilra'] });
      let tries = 0;
      const poll = setInterval(async () => {
        tries++;
        if (tries > 40) { clearInterval(poll); setIsAnalyzing(false); return; }
        const runRes = await api.get(`/api/v1/runs?repoId=${repoId}&limit=1`);
        const run = (runRes.data?.data || runRes.data || [])[0];
        if (run) {
          const res = await api.get(`/api/v1/results/run/${run.id}/infilra`);
          const rd = res.data?.data?.result_data || res.data?.result_data;
          if (rd?.status === 'completed') { clearInterval(poll); setIsAnalyzing(false); setData(rd); setRunInfo(run); }
        }
      }, 4000);
    } catch { setIsAnalyzing(false); }
  };

  const findings: any[] = data?.findings || [];
  const filtered = findings.filter(f =>
    (filter === 'ALL' || f.severity === filter) &&
    (!search || f.file.toLowerCase().includes(search.toLowerCase()) || f.title.toLowerCase().includes(search.toLowerCase()))
  );
  const counts = data?.severityCounts || {};
  const score = data?.securityScore ?? 100;

  return (
    <div className="relative min-h-screen bg-paper text-ink flex flex-col font-sans">
      <GridBg />
      <header className="relative z-10 w-full px-6 py-4 flex items-center gap-4 border-b-2 border-ink bg-paper">
        <button onClick={() => navigate('/home')} className="w-10 h-10 flex items-center justify-center border-2 border-ink bg-surface shadow-[2px_2px_0px_#0A0A0A] active:translate-x-[2px] active:translate-y-[2px] active:shadow-none transition-all rounded-[6px]">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" /></svg>
        </button>
        <div className="flex-1">
          <div className="font-display font-bold text-xl uppercase tracking-tight">Security (Infilra)</div>
          {runInfo && <div className="font-mono text-xs text-muted">{runInfo.repo_full_name} • {runInfo.branch} • {runInfo.commit_sha?.slice(0,7)}</div>}
        </div>
        <button id="security-analyze-btn" onClick={handleAnalyze} disabled={isAnalyzing}
          className={`flex items-center gap-2 px-4 py-2 font-display font-bold text-sm uppercase border-2 border-ink rounded-[6px] shadow-[2px_2px_0px_#0A0A0A] active:translate-x-[1px] active:translate-y-[1px] active:shadow-none transition-all ${isAnalyzing ? 'bg-muted text-paper cursor-not-allowed' : 'bg-ink text-paper hover:bg-gray-800'}`}>
          {isAnalyzing ? (<><svg className="animate-spin" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><circle cx="12" cy="12" r="10" strokeOpacity=".25"/><path d="M12 2a10 10 0 0 1 10 10"/></svg>Scanning...</>) : (<><span>🔍</span> Scan Now</>)}
        </button>
      </header>

      <main className="relative z-10 flex-1 w-full max-w-7xl mx-auto px-6 py-8 flex flex-col gap-6">
        {isLoading ? (
          <div className="flex-1 flex items-center justify-center"><div className="font-mono text-xl animate-pulse text-muted">Loading security results...</div></div>
        ) : error ? (
          <div className="p-8 bg-red-50 border-2 border-red-400 rounded-[6px] text-red-600 font-mono">{error}</div>
        ) : !data ? (
          <div className="flex-1 flex flex-col items-center justify-center gap-6 p-10 border-2 border-dashed border-ink rounded-[6px]">
            <div className="text-center"><div className="font-display font-bold text-2xl uppercase mb-2">No Security Scan Yet</div><p className="text-muted font-mono text-sm">Click "Scan Now" to run a full security analysis</p></div>
            <button onClick={handleAnalyze} disabled={isAnalyzing} className="px-6 py-3 bg-ink text-paper font-display font-bold uppercase border-2 border-ink rounded-[6px] shadow-[4px_4px_0px_#0A0A0A]">{isAnalyzing ? 'Scanning...' : '🔍 Run Security Scan'}</button>
          </div>
        ) : (
          <>
            {/* Score header */}
            <div className="bg-surface border-2 border-ink rounded-[6px] shadow-[4px_4px_0px_#0A0A0A] p-6 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
              <div>
                <h2 className="font-display font-bold text-2xl uppercase">Security Analysis Complete</h2>
                <p className="text-muted text-sm font-mono mt-1">{data.aiSummary || `${findings.length} security findings across your codebase`}</p>
              </div>
              <div className="text-right shrink-0">
                <div className="text-xs font-mono font-bold text-muted uppercase">Security Score</div>
                <div className={`font-display font-bold text-5xl ${score >= 80 ? 'text-green-500' : score >= 50 ? 'text-yellow-500' : 'text-red-500'}`}>{score}<span className="text-xl text-muted">/100</span></div>
              </div>
            </div>

            {/* Severity breakdown */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              {(['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'] as const).map(sev => (
                <button key={sev} onClick={() => setFilter(filter === sev ? 'ALL' : sev)}
                  className={`p-4 border-2 border-ink rounded-[6px] shadow-[2px_2px_0px_#0A0A0A] text-center transition-all ${filter === sev ? 'bg-ink text-paper' : 'bg-paper hover:bg-surface'}`}>
                  <div className={`text-3xl font-display font-bold ${sev === 'CRITICAL' ? 'text-red-600' : sev === 'HIGH' ? 'text-orange-500' : sev === 'MEDIUM' ? 'text-yellow-500' : 'text-blue-400'} ${filter === sev ? '!text-paper' : ''}`}>{counts[sev] || 0}</div>
                  <div className="font-mono text-xs uppercase">{sev}</div>
                </button>
              ))}
            </div>

            {/* Findings */}
            <div>
              <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
                <h3 className="font-display font-bold text-lg uppercase">
                  {filter === 'ALL' ? `All Findings (${findings.length})` : `${filter} Findings (${filtered.length})`}
                </h3>
                <div className="flex items-center gap-2">
                  <input type="text" placeholder="Search file or title..." value={search} onChange={e => setSearch(e.target.value)}
                    className="px-3 py-1.5 text-sm font-mono border-2 border-ink rounded-[6px] bg-paper focus:outline-none focus:bg-surface" />
                  {filter !== 'ALL' && <button onClick={() => setFilter('ALL')} className="px-3 py-1.5 text-sm font-mono border border-ink rounded-[6px] hover:bg-surface">Clear</button>}
                </div>
              </div>
              {filtered.length === 0 ? (
                <div className="p-8 border-2 border-dashed border-ink rounded-[6px] text-center text-muted font-mono">No findings match your filter</div>
              ) : (
                <div className="flex flex-col gap-3">
                  {filtered.map((f, i) => <FindingCard key={f.id || i} f={f} />)}
                </div>
              )}
            </div>
          </>
        )}
      </main>
    </div>
  );
}
