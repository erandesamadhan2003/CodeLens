import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../../../api/client';

const GridBg = () => (
  <div className="absolute inset-0 z-0 opacity-[0.05] pointer-events-none"
    style={{ backgroundImage: `linear-gradient(#0A0A0A 1px, transparent 1px), linear-gradient(90deg, #0A0A0A 1px, transparent 1px)`, backgroundSize: '24px 24px' }} />
);

const SEV_STYLE: Record<string, string> = {
  CRITICAL: 'bg-red-600 text-white border-red-700',
  HIGH: 'bg-orange-500 text-white border-orange-600',
  MEDIUM: 'bg-yellow-400 text-black border-yellow-500',
  LOW: 'bg-blue-400 text-white border-blue-500',
  UNKNOWN: 'bg-gray-400 text-white border-gray-500',
};

function DepRow({ dep }: { dep: any }) {
  const [open, setOpen] = useState(false);
  const v = dep.vuln;
  return (
    <div className={`border-b border-ink/10 ${dep.vulnerable ? 'bg-red-50/30' : ''}`}>
      <button className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-surface/60 transition-colors" onClick={() => dep.vulnerable && setOpen(o => !o)}>
        <div className="flex-1 min-w-0">
          <span className="font-mono font-bold text-sm">{dep.name}</span>
          <span className="ml-2 font-mono text-xs text-muted">v{dep.version}</span>
          <span className="ml-2 font-mono text-xs text-muted/60">{dep.file}</span>
        </div>
        <span className="px-2 py-0.5 text-xs font-mono border rounded bg-surface">{dep.ecosystem}</span>
        {dep.vulnerable && v ? (
          <span className={`px-2 py-0.5 text-[10px] font-bold rounded border uppercase ${SEV_STYLE[v.severity] || SEV_STYLE.UNKNOWN}`}>{v.severity}</span>
        ) : (
          <span className="px-2 py-0.5 text-[10px] font-bold rounded border bg-green-100 text-green-700 border-green-300">SAFE</span>
        )}
        {dep.vulnerable && <svg className={`transition-transform shrink-0 ${open ? 'rotate-180' : ''}`} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9" /></svg>}
      </button>
      {open && v && (
        <div className="px-4 pb-4 pt-1 bg-red-50/50 border-t border-red-200 flex flex-col gap-2">
          <div className="flex flex-wrap gap-3 text-sm">
            <div><span className="font-mono text-xs text-muted uppercase">CVE/ID</span><div className="font-mono font-bold text-red-600">{v.id}</div></div>
            {v.cvssScore && <div><span className="font-mono text-xs text-muted uppercase">CVSS Score</span><div className="font-display font-bold text-lg">{v.cvssScore.toFixed(1)}</div></div>}
            {v.fixVersion && <div><span className="font-mono text-xs text-muted uppercase">Fix Version</span><div className="font-mono font-bold text-green-600">{v.fixVersion}</div></div>}
          </div>
          {v.summary && <p className="text-sm text-muted">{v.summary}</p>}
          {v.fixVersion && (
            <div className="mt-1 p-2 bg-green-50 border border-green-300 rounded text-xs font-mono">
              💡 Update to <strong>{v.fixVersion}</strong> to fix this vulnerability
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function DependencyDashboard() {
  const { repoId } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState<any>(null);
  const [runInfo, setRunInfo] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
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
      const res = await api.get(`/api/v1/results/run/${run.id}/depra`);
      setData(res.data?.data?.result_data || res.data?.result_data);
    } catch { } finally { setIsLoading(false); }
  }, [repoId]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleAnalyze = async () => {
    if (!repoId || isAnalyzing) return;
    setIsAnalyzing(true);
    try {
      await api.post('/api/v1/runs', { repoId, engines: ['depra'] });
      let tries = 0;
      const poll = setInterval(async () => {
        tries++;
        if (tries > 40) { clearInterval(poll); setIsAnalyzing(false); return; }
        const runRes = await api.get(`/api/v1/runs?repoId=${repoId}&limit=1`);
        const run = (runRes.data?.data || runRes.data || [])[0];
        if (run) {
          const res = await api.get(`/api/v1/results/run/${run.id}/depra`);
          const rd = res.data?.data?.result_data || res.data?.result_data;
          if (rd?.status === 'completed') { clearInterval(poll); setIsAnalyzing(false); setData(rd); setRunInfo(run); }
        }
      }, 4000);
    } catch { setIsAnalyzing(false); }
  };

  const deps: any[] = data?.dependencies || [];
  const vulnerable = deps.filter(d => d.vulnerable);
  const filtered = deps.filter(d =>
    (filter === 'ALL' || (filter === 'VULNERABLE' && d.vulnerable) || (filter === 'SAFE' && !d.vulnerable)) &&
    (!search || d.name.toLowerCase().includes(search.toLowerCase()))
  );
  const counts = data?.severityCounts || {};
  const score = data?.riskScore ?? 100;

  return (
    <div className="relative min-h-screen bg-paper text-ink flex flex-col font-sans">
      <GridBg />
      <header className="relative z-10 w-full px-6 md:px-12 py-6 flex items-center gap-6 border-b-4 border-ink bg-paper">
        <button onClick={() => navigate('/home')} className="w-12 h-12 flex items-center justify-center border-[3px] border-ink bg-surface shadow-[4px_4px_0px_#0A0A0A] active:translate-x-[4px] active:translate-y-[4px] active:shadow-none transition-all rounded-[8px]">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" /></svg>
        </button>
        <div className="flex-1 min-w-0">
          <div className="font-display font-bold text-3xl uppercase tracking-tight truncate">Dependencies</div>
          {runInfo && <div className="font-mono text-sm text-muted mt-1 truncate bg-surface px-3 py-1 inline-block rounded-full border border-ink/20">{runInfo.repo_full_name} • {runInfo.branch}</div>}
        </div>
        <button id="dep-analyze-btn" onClick={handleAnalyze} disabled={isAnalyzing}
          className={`shrink-0 flex items-center gap-3 px-6 py-3 font-display font-bold text-lg uppercase border-[3px] border-ink rounded-[8px] shadow-[4px_4px_0px_#0A0A0A] active:translate-x-[2px] active:translate-y-[2px] active:shadow-[2px_2px_0px_#0A0A0A] transition-all ${isAnalyzing ? 'bg-muted text-paper cursor-not-allowed' : 'bg-accent text-ink hover:bg-accent/80'}`}>
          {isAnalyzing ? 'Scanning...' : '📦 Scan Now'}
        </button>
      </header>

      <main className="relative z-10 flex-1 w-full flex flex-col px-6 md:px-12 py-10 gap-10">
        {isLoading ? (
          <div className="flex-1 flex items-center justify-center"><div className="font-mono text-xl animate-pulse text-muted">Loading dependency results...</div></div>
        ) : !data ? (
          <div className="flex-1 flex flex-col items-center justify-center gap-6 p-10 border-2 border-dashed border-ink rounded-[6px]">
            <div className="text-center"><div className="font-display font-bold text-2xl uppercase mb-2">No Dependency Scan Yet</div><p className="text-muted font-mono text-sm">Scans npm and pip packages against the OSV.dev vulnerability database</p></div>
            <button onClick={handleAnalyze} className="px-6 py-3 bg-ink text-paper font-display font-bold uppercase border-2 border-ink rounded-[6px] shadow-[4px_4px_0px_#0A0A0A]">📦 Scan Dependencies</button>
          </div>
        ) : (
          <>
            {/* Score Header */}
            <div className="bg-surface border-2 border-ink rounded-[6px] shadow-[4px_4px_0px_#0A0A0A] p-6 flex flex-wrap items-center gap-6">
              <div className="text-right">
                <div className="text-xs font-mono font-bold text-muted uppercase">Risk Score</div>
                <div className={`font-display font-bold text-5xl ${score >= 80 ? 'text-green-500' : score >= 50 ? 'text-yellow-500' : 'text-red-500'}`}>{score}<span className="text-xl text-muted">/100</span></div>
              </div>
              <div className="flex-1 grid grid-cols-2 sm:grid-cols-4 gap-4 font-mono text-center">
                <div><div className="text-2xl font-bold">{data.totalDependencies || 0}</div><div className="text-xs text-muted uppercase">Total</div></div>
                <div><div className={`text-2xl font-bold ${vulnerable.length > 0 ? 'text-red-500' : 'text-green-500'}`}>{vulnerable.length}</div><div className="text-xs text-muted uppercase">Vulnerable</div></div>
                <div><div className="text-2xl font-bold text-red-600">{counts.CRITICAL || 0}</div><div className="text-xs text-muted uppercase">Critical</div></div>
                <div><div className="text-2xl font-bold text-orange-500">{counts.HIGH || 0}</div><div className="text-xs text-muted uppercase">High</div></div>
              </div>
              {/* Ecosystem badges */}
              <div className="flex flex-wrap gap-2">
                {Object.entries(data.ecosystems || {}).map(([eco, count]: any) => (
                  <span key={eco} className="px-2 py-1 bg-paper border-2 border-ink rounded font-mono text-xs font-bold">{eco}: {count}</span>
                ))}
              </div>
            </div>

            {/* Manifests */}
            {(data.manifests || []).length > 0 && (
              <div className="flex flex-wrap gap-2">
                {data.manifests.map((m: any) => (
                  <span key={m.file} className="px-3 py-1.5 bg-surface border border-ink rounded font-mono text-xs">
                    📄 <strong>{m.file}</strong> ({m.count} packages, {m.ecosystem})
                  </span>
                ))}
              </div>
            )}

            {/* Main Content Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Left Column: Dependency Table */}
              <div className="lg:col-span-2 flex flex-col gap-4">
                {/* Filter bar */}
                <div className="flex flex-wrap items-center gap-3">
                  {(['ALL', 'VULNERABLE', 'SAFE'] as const).map(f => (
                    <button key={f} onClick={() => setFilter(f)} className={`px-3 py-1.5 font-mono text-xs uppercase font-bold border-2 border-ink rounded-[6px] transition-all ${filter === f ? 'bg-ink text-paper' : 'bg-paper hover:bg-surface'}`}>{f}</button>
                  ))}
                  <input type="text" placeholder="Search package..." value={search} onChange={e => setSearch(e.target.value)}
                    className="ml-auto px-3 py-1.5 text-sm font-mono border-2 border-ink rounded-[6px] bg-paper focus:outline-none" />
                </div>
                
                {/* Dependency table */}
                <div className="bg-paper border-2 border-ink rounded-[6px] overflow-hidden shadow-[4px_4px_0px_#0A0A0A]">
                  <div className="grid grid-cols-[1fr_auto_auto_auto] gap-4 px-4 py-2 border-b-2 border-ink bg-surface font-mono text-xs uppercase text-muted">
                    <span>Package</span><span>Ecosystem</span><span>Status</span><span></span>
                  </div>
                  <div className="max-h-[500px] overflow-y-auto divide-y divide-ink/5">
                    {filtered.length === 0 ? (
                      <div className="p-8 text-center text-muted font-mono">No packages match filter</div>
                    ) : filtered.map((dep, i) => <DepRow key={dep.name + i} dep={dep} />)}
                  </div>
                </div>
              </div>

              {/* Right Column: Recommendations Sidebar */}
              <div className="lg:col-span-1">
                <div className="bg-paper border-2 border-ink rounded-[6px] shadow-[4px_4px_0px_#0A0A0A] flex flex-col h-full max-h-[555px]">
                  <div className="px-4 py-3 border-b-2 border-ink bg-surface font-display font-bold uppercase tracking-tight flex items-center gap-2">
                    <span>💡 Actionable Fixes</span>
                    <span className="ml-auto px-2 py-0.5 bg-ink text-paper text-xs rounded-full">
                      {vulnerable.filter(v => v.vuln?.fixVersion).length}
                    </span>
                  </div>
                  <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3">
                    {vulnerable.filter(v => v.vuln?.fixVersion).length === 0 ? (
                      <div className="text-center text-muted font-mono text-sm py-8 border-2 border-dashed border-ink/20 rounded">
                        No actionable upgrades available.
                      </div>
                    ) : (
                      vulnerable.filter(v => v.vuln?.fixVersion).map((dep, i) => (
                        <div key={i} className="border-2 border-ink p-3 rounded bg-surface shadow-[2px_2px_0px_#0A0A0A]">
                          <div className="font-mono text-sm font-bold truncate mb-1" title={dep.name}>{dep.name}</div>
                          <div className="font-mono text-xs text-muted mb-3 flex items-center gap-2">
                            <span>Current:</span>
                            <span className="px-1.5 py-0.5 bg-red-100 text-red-700 border border-red-300 rounded line-through">v{dep.version}</span>
                          </div>
                          <div className="p-2 bg-green-100 border border-green-400 rounded text-xs font-mono text-green-900">
                            Update to <strong className="text-green-700 text-sm">v{dep.vuln.fixVersion}</strong>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
