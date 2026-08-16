import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';

const GridBg = () => (
  <div 
    className="absolute inset-0 z-0 opacity-[0.05] pointer-events-none"
    style={{
      backgroundImage: `linear-gradient(#0A0A0A 1px, transparent 1px), linear-gradient(90deg, #0A0A0A 1px, transparent 1px)`,
      backgroundSize: '24px 24px'
    }}
  />
);

export default function CodeQualityDashboard() {
  const { runId } = useParams();
  const navigate = useNavigate();

  return (
    <div className="relative min-h-screen bg-paper text-ink flex flex-col font-sans">
      <GridBg />
      
      {/* Top Navbar */}
      <header className="relative z-10 w-full px-6 md:px-12 py-6 flex items-center gap-6 border-b-4 border-ink bg-paper">
        <button 
          onClick={() => navigate('/home')}
          className="w-12 h-12 flex items-center justify-center border-[3px] border-ink bg-surface shadow-[4px_4px_0px_#0A0A0A] active:translate-x-[4px] active:translate-y-[4px] active:shadow-none transition-all rounded-[8px]"
          title="Back to Dashboard"
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
            <line x1="19" y1="12" x2="5" y2="12"></line>
            <polyline points="12 19 5 12 12 5"></polyline>
          </svg>
        </button>
        <div className="flex-1 min-w-0">
          <span className="font-display font-bold text-3xl uppercase tracking-tight truncate block">Code Quality</span>
        </div>
      </header>

      {/* Main Content */}
      <main className="relative z-10 flex-1 w-full flex flex-col px-6 md:px-12 py-10 gap-10">
        <div className="flex-1 flex items-center justify-center p-20 bg-surface border-2 border-ink rounded-[6px] shadow-[4px_4px_0px_#0A0A0A]">
          <div className="text-center flex flex-col gap-4">
            <h3 className="font-display font-bold text-2xl uppercase tracking-tight">Engine Coming Soon</h3>
            <p className="font-mono text-muted text-sm max-w-md">
              The Code Quality engine (Devora) is currently in development and will be integrated into the CodeLens pipeline soon.
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
