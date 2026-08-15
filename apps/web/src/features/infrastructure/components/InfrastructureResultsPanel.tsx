import React, { useState } from 'react';

interface FileChange {
  file_path: string;
  action: string;
  new_content: string;
  diff_summary: string;
  original_content?: string;
}

interface Recommendation {
  id: string;
  priority: string;
  category: string;
  title: string;
  problem: string;
  solution: string;
  reasoning: string;
  impact: string;
  estimated_effort: string;
  file_changes: FileChange[];
  applied?: boolean;
  pr_url?: string;
}

interface Props {
  runId?: string;
  score: number;
  scores: any;
  architecture: any;
  discovery: any;
  findings: any[];
  recommendations: Recommendation[];
  aiPowered?: boolean;
  onApply?: (runId: string, recId: string) => Promise<string>;
}

const PRIORITY_STYLES: Record<string, string> = {
  HIGH: 'bg-red-500 text-white',
  MEDIUM: 'bg-yellow-400 text-black',
  LOW: 'bg-blue-400 text-white',
};

const CATEGORY_ICONS: Record<string, string> = {
  security: '🔒',
  reliability: '🛡️',
  performance: '⚡',
  cost: '💰',
  maintainability: '🔧',
  deployment: '🚀',
  scalability: '📈',
};

const ScoreBar = ({ label, value }: { label: string; value: number }) => (
  <div className="flex flex-col gap-1">
    <div className="flex justify-between items-center font-mono text-xs">
      <span className="text-muted uppercase">{label}</span>
      <span className={`font-bold ${value >= 80 ? 'text-green-500' : value >= 50 ? 'text-yellow-500' : 'text-red-500'}`}>{value}</span>
    </div>
    <div className="h-1.5 bg-surface border border-ink/20 rounded-full overflow-hidden">
      <div
        className={`h-full rounded-full transition-all duration-700 ${value >= 80 ? 'bg-green-500' : value >= 50 ? 'bg-yellow-400' : 'bg-red-500'}`}
        style={{ width: `${value}%` }}
      />
    </div>
  </div>
);

function FileChangeCard({ change, idx }: { change: FileChange; idx: number }) {
  const [expanded, setExpanded] = useState(false);

  const actionColor: Record<string, string> = {
    create: 'text-green-500 bg-green-50 border-green-300',
    modify: 'text-yellow-600 bg-yellow-50 border-yellow-300',
    delete: 'text-red-500 bg-red-50 border-red-300',
  };

  return (
    <div className="border border-ink/30 rounded-[6px] overflow-hidden">
      <button
        className="w-full flex items-center gap-3 p-3 bg-paper hover:bg-surface text-left transition-colors"
        onClick={() => setExpanded(e => !e)}
      >
        <span className={`px-2 py-0.5 text-xs font-bold rounded border uppercase ${actionColor[change.action] || actionColor.modify}`}>
          {change.action}
        </span>
        <span className="font-mono text-sm font-bold flex-1">{change.file_path}</span>
        <span className="text-muted text-xs hidden sm:block">{change.diff_summary}</span>
        <svg
          className={`transition-transform shrink-0 ${expanded ? 'rotate-180' : ''}`}
          width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {expanded && (
        <div className="border-t border-ink/20">
          {change.diff_summary && (
            <div className="px-3 py-2 bg-surface text-muted text-xs font-mono border-b border-ink/10">
              {change.diff_summary}
            </div>
          )}
          <pre className="p-3 text-xs font-mono bg-[#0d0d0d] text-green-400 overflow-x-auto max-h-64 leading-relaxed">
            {change.new_content || '(empty)'}
          </pre>
        </div>
      )}
    </div>
  );
}

function RecommendationCard({
  rec, index, runId, onApply,
}: {
  rec: Recommendation;
  index: number;
  runId?: string;
  onApply?: (runId: string, recId: string) => Promise<string>;
}) {
  const [isApplying, setIsApplying] = useState(false);
  const [prUrl, setPrUrl] = useState(rec.pr_url || '');
  const [applied, setApplied] = useState(rec.applied || false);
  const [applyError, setApplyError] = useState('');
  const [showFiles, setShowFiles] = useState(false);

  const handleApply = async () => {
    if (!runId || !onApply || isApplying || applied) return;
    setIsApplying(true);
    setApplyError('');
    try {
      const url = await onApply(runId, rec.id);
      setPrUrl(url);
      setApplied(true);
    } catch (err: any) {
      setApplyError(err?.message || 'Failed to apply recommendation');
    } finally {
      setIsApplying(false);
    }
  };

  const hasFileChanges = rec.file_changes && rec.file_changes.length > 0;

  return (
    <div className={`bg-surface border-2 border-ink rounded-[6px] overflow-hidden shadow-[4px_4px_0px_#0A0A0A] transition-all duration-300 ${applied ? 'border-green-500 shadow-[4px_4px_0px_rgba(34,197,94,0.3)]' : ''}`}>
      {/* Header */}
      <div className="bg-ink text-paper p-4 flex items-start gap-3">
        <span className="text-2xl shrink-0 mt-0.5">{CATEGORY_ICONS[rec.category] || '🔧'}</span>
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <span className={`px-2 py-0.5 text-xs font-bold rounded uppercase ${PRIORITY_STYLES[rec.priority] || PRIORITY_STYLES.MEDIUM}`}>
              {rec.priority} PRIORITY
            </span>
            <span className="px-2 py-0.5 text-xs font-mono uppercase text-paper/60 border border-paper/20 rounded">
              {rec.category}
            </span>
            {rec.estimated_effort && (
              <span className="px-2 py-0.5 text-xs font-mono text-paper/60">
                ⏱ {rec.estimated_effort}
              </span>
            )}
          </div>
          <h3 className="font-display font-bold text-lg leading-tight">{rec.title}</h3>
        </div>
        <span className="font-mono text-sm text-paper/40 shrink-0">#{index + 1}</span>
      </div>

      {/* Body */}
      <div className="p-5 flex flex-col gap-5">
        {/* Problem */}
        <div className="border-l-4 border-red-500 pl-4">
          <div className="font-mono text-xs font-bold text-red-500 uppercase mb-1">⚠ Problem</div>
          <p className="text-sm font-sans leading-relaxed">{rec.problem}</p>
        </div>

        {/* Solution */}
        <div className="border-l-4 border-green-500 pl-4">
          <div className="font-mono text-xs font-bold text-green-500 uppercase mb-1">✓ Solution</div>
          <p className="text-sm font-sans leading-relaxed">{rec.solution}</p>
        </div>

        {/* Reasoning */}
        {rec.reasoning && (
          <div className="p-3 bg-paper border border-ink/10 rounded-[6px]">
            <div className="font-mono text-xs font-bold text-muted uppercase mb-1">💡 Why This Matters</div>
            <p className="text-sm text-muted leading-relaxed">{rec.reasoning}</p>
          </div>
        )}

        {/* Impact */}
        {rec.impact && (
          <div className="p-3 bg-green-500/5 border border-green-500/30 rounded-[6px]">
            <div className="font-mono text-xs font-bold text-green-600 uppercase mb-1">📈 Expected Impact</div>
            <p className="text-sm font-sans font-medium">{rec.impact}</p>
          </div>
        )}

        {/* File Changes */}
        {hasFileChanges && (
          <div>
            <button
              className="flex items-center gap-2 font-mono text-sm font-bold uppercase text-muted hover:text-ink transition-colors mb-3"
              onClick={() => setShowFiles(f => !f)}
            >
              <svg className={`transition-transform ${showFiles ? 'rotate-90' : ''}`} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <polyline points="9 18 15 12 9 6" />
              </svg>
              {rec.file_changes.length} File{rec.file_changes.length !== 1 ? 's' : ''} to Change
            </button>
            {showFiles && (
              <div className="flex flex-col gap-2">
                {rec.file_changes.map((change, idx) => (
                  <FileChangeCard key={idx} change={change} idx={idx} />
                ))}
              </div>
            )}
          </div>
        )}

        {/* Apply Error */}
        {applyError && (
          <div className="p-3 bg-red-50 border border-red-300 rounded text-red-600 text-sm font-mono">
            ✗ {applyError}
          </div>
        )}

        {/* Actions */}
        <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-ink/10">
          {applied && prUrl ? (
            <a
              href={prUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 px-4 py-2 bg-green-500 text-white font-display font-bold text-sm uppercase rounded-[6px] border-2 border-green-700 shadow-[2px_2px_0px_rgba(0,0,0,0.2)] hover:bg-green-400 transition-colors"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                <polyline points="15 3 21 3 21 9" />
                <line x1="10" y1="14" x2="21" y2="3" />
              </svg>
              View PR on GitHub →
            </a>
          ) : hasFileChanges && runId ? (
            <button
              id={`apply-rec-${rec.id}`}
              onClick={handleApply}
              disabled={isApplying || !hasFileChanges}
              className={`flex items-center gap-2 px-4 py-2 font-display font-bold text-sm uppercase rounded-[6px] border-2 border-ink shadow-[2px_2px_0px_#0A0A0A] active:translate-x-[1px] active:translate-y-[1px] active:shadow-none transition-all ${
                isApplying
                  ? 'bg-muted text-paper cursor-not-allowed'
                  : 'bg-ink text-paper hover:bg-gray-800'
              }`}
            >
              {isApplying ? (
                <>
                  <svg className="animate-spin" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <circle cx="12" cy="12" r="10" strokeOpacity="0.25" />
                    <path d="M12 2a10 10 0 0 1 10 10" />
                  </svg>
                  Creating PR...
                </>
              ) : (
                <>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <circle cx="18" cy="18" r="3" />
                    <circle cx="6" cy="6" r="3" />
                    <path d="M6 21V9a9 9 0 0 0 9 9" />
                  </svg>
                  Apply to GitHub →
                </>
              )}
            </button>
          ) : null}

          {!hasFileChanges && (
            <span className="text-muted text-xs font-mono italic">No automated code changes for this recommendation</span>
          )}
        </div>
      </div>
    </div>
  );
}

export default function InfrastructureResultsPanel({
  runId, score, scores, architecture, discovery, findings, recommendations, aiPowered, onApply,
}: Props) {
  const getCount = (sev: string) => (findings || []).filter((f: any) => f.severity === sev).length;

  const scoreKeys: [string, string][] = [
    ['Security', 'security_score'],
    ['Reliability', 'reliability_score'],
    ['Scalability', 'scalability_score'],
    ['Deployment', 'deployment_score'],
    ['Maintainability', 'maintainability_score'],
    ['Cost', 'cost_score'],
  ];

  return (
    <div className="flex flex-col gap-8 w-full">

      {/* ── Header / Overall Score ───────────────────────────────────── */}
      <div className="bg-surface border-2 border-ink shadow-[4px_4px_0px_#0A0A0A] rounded-[6px] p-6 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
        <div>
          <h2 className="font-display font-bold text-2xl uppercase tracking-tight">Infrastructure Analysis Complete</h2>
          <p className="text-muted text-sm font-sans mt-1">
            {aiPowered
              ? '🤖 AI-powered file-level recommendations generated by Groq (llama-3.3-70b)'
              : 'Rule-based recommendations. Click "Generate AI" in the header for AI-powered insights.'}
          </p>
        </div>
        <div className="text-right shrink-0">
          <div className="text-xs font-mono font-bold text-muted uppercase">Overall Score</div>
          <div className={`font-display font-bold text-5xl ${score >= 80 ? 'text-green-500' : score >= 50 ? 'text-yellow-500' : 'text-red-500'}`}>
            {score}<span className="text-xl text-muted">/100</span>
          </div>
        </div>
      </div>

      {/* ── Score Breakdown + Architecture ──────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Score bars */}
        <div className="bg-paper border-2 border-ink rounded-[6px] p-5">
          <h3 className="font-display font-bold text-base uppercase tracking-tight border-b-2 border-ink pb-2 mb-4">Score Breakdown</h3>
          <div className="flex flex-col gap-3">
            {scoreKeys.map(([label, key]) => (
              <ScoreBar key={key} label={label} value={scores[key] ?? 100} />
            ))}
          </div>
        </div>

        {/* Architecture Details */}
        <div className="lg:col-span-2 bg-paper border-2 border-ink rounded-[6px] p-5">
          <h3 className="font-display font-bold text-base uppercase tracking-tight border-b-2 border-ink pb-2 mb-4">Architecture</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 font-mono text-sm">
            <div>
              <span className="text-muted block mb-2">Detected Services</span>
              <div className="flex flex-wrap gap-2">
                {(discovery?.services || []).length > 0
                  ? (discovery.services || []).map((s: any, idx: number) => (
                    <span key={s.name || idx} className="px-2 py-1 bg-surface border border-ink rounded text-xs font-bold">
                      {s.name || s.type || 'Service'}
                    </span>
                  ))
                  : <span className="text-muted italic text-xs">None detected</span>}
              </div>
            </div>
            <div>
              <span className="text-muted block mb-2">Cloud Provider</span>
              <span className="px-2 py-1 bg-accent text-ink border border-ink rounded font-bold text-xs">
                {discovery?.cloudProvider?.toUpperCase() || 'UNKNOWN'}
              </span>
            </div>
            <div>
              <span className="text-muted block mb-2">Infrastructure Files</span>
              <div className="flex flex-wrap gap-1">
                {[
                  discovery?.has_dockerfile && 'Dockerfile',
                  discovery?.has_docker_compose && 'Compose',
                  discovery?.has_k8s_manifests && 'Kubernetes',
                  discovery?.has_terraform && 'Terraform',
                  discovery?.has_ci_config && 'CI/CD',
                  discovery?.has_helm_charts && 'Helm',
                ].filter(Boolean).map((label: any) => (
                  <span key={label} className="px-1.5 py-0.5 bg-green-100 text-green-700 border border-green-300 rounded text-[10px] font-bold">✓ {label}</span>
                ))}
                {![discovery?.has_dockerfile, discovery?.has_docker_compose, discovery?.has_k8s_manifests, discovery?.has_terraform, discovery?.has_ci_config].some(Boolean) && (
                  <span className="text-muted italic text-xs">No infra files detected</span>
                )}
              </div>
            </div>
            <div>
              <span className="text-muted block mb-2">Issues Found</span>
              <div className="flex flex-wrap gap-2 text-xs">
                {getCount('CRITICAL') > 0 && <span className="px-2 py-1 bg-red-500 text-white rounded font-bold">{getCount('CRITICAL')} CRITICAL</span>}
                {getCount('HIGH') > 0 && <span className="px-2 py-1 bg-orange-400 text-white rounded font-bold">{getCount('HIGH')} HIGH</span>}
                {getCount('MEDIUM') > 0 && <span className="px-2 py-1 bg-yellow-400 text-black rounded font-bold">{getCount('MEDIUM')} MEDIUM</span>}
                {getCount('LOW') > 0 && <span className="px-2 py-1 bg-blue-400 text-white rounded font-bold">{getCount('LOW')} LOW</span>}
                {findings.length === 0 && <span className="text-muted italic">None</span>}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Findings (collapsible) ───────────────────────────────────── */}
      {findings.length > 0 && (
        <div className="bg-paper border-2 border-ink rounded-[6px] overflow-hidden">
          <details>
            <summary className="cursor-pointer p-5 font-display font-bold text-lg uppercase tracking-tight border-b-2 border-ink select-none hover:bg-surface transition-colors">
              Static Analysis Findings ({findings.length})
            </summary>
            <div className="divide-y divide-ink/10 max-h-80 overflow-y-auto">
              {findings.map((f: any) => (
                <div key={f.id} className="p-4 flex flex-col gap-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className={`px-1.5 py-0.5 text-[10px] font-bold rounded uppercase ${
                      f.severity === 'CRITICAL' ? 'bg-red-500 text-white' :
                      f.severity === 'HIGH' ? 'bg-orange-400 text-white' :
                      f.severity === 'MEDIUM' ? 'bg-yellow-400 text-black' :
                      'bg-blue-400 text-white'
                    }`}>{f.severity}</span>
                    <span className="font-mono text-xs text-muted">{f.file_path}</span>
                    <span className="font-bold text-sm">{f.title}</span>
                  </div>
                  <p className="text-muted text-xs">{f.description}</p>
                  {f.recommendation && (
                    <p className="text-xs text-green-600 font-mono">→ {f.recommendation}</p>
                  )}
                </div>
              ))}
            </div>
          </details>
        </div>
      )}

      {/* ── AI Recommendations ───────────────────────────────────────── */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-display font-bold text-xl uppercase tracking-tight">
            {aiPowered ? '🤖 AI Recommendations' : 'Recommendations'}
          </h3>
          <span className="font-mono text-sm text-muted">{recommendations.length} total</span>
        </div>

        {recommendations.length === 0 ? (
          <div className="p-8 border-2 border-dashed border-ink rounded-[6px] text-center text-muted font-mono">
            No recommendations available. Click "Generate AI" to get AI-powered insights.
          </div>
        ) : (
          <div className="flex flex-col gap-6">
            {recommendations.map((rec, i) => (
              <RecommendationCard
                key={rec.id}
                rec={rec}
                index={i}
                runId={runId}
                onApply={onApply}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
