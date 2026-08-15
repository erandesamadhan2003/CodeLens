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

export default function DocumentsDashboard() {
  const { runId } = useParams();
  const navigate = useNavigate();

  return (
    <div className="relative min-h-screen bg-paper text-ink flex flex-col font-sans">
      <GridBg />
      
      {/* Top Navbar */}
      <header className="relative z-10 w-full px-6 py-4 flex items-center gap-4 border-b-2 border-ink bg-paper">
        <button 
          onClick={() => navigate('/home')}
          className="w-10 h-10 flex items-center justify-center border-2 border-ink bg-surface shadow-[2px_2px_0px_#0A0A0A] active:translate-x-[2px] active:translate-y-[2px] active:shadow-none transition-all rounded-[6px]"
          title="Back to Dashboard"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
            <line x1="19" y1="12" x2="5" y2="12"></line>
            <polyline points="12 19 5 12 12 5"></polyline>
          </svg>
        </button>
        <div className="flex flex-col">
          <span className="font-display font-bold text-xl uppercase tracking-tight">Documentation (Docryx)</span>
        </div>
      </header>

      {/* Main Content */}
      <main className="relative z-10 flex-1 w-full max-w-7xl mx-auto px-6 py-10 flex flex-col gap-8">
        <div className="flex-1 flex items-center justify-center p-20 bg-surface border-2 border-ink rounded-[6px] shadow-[4px_4px_0px_#0A0A0A]">
          <div className="text-center flex flex-col gap-4">
            <h3 className="font-display font-bold text-2xl uppercase tracking-tight">Engine Coming Soon</h3>
            <p className="font-mono text-muted text-sm max-w-md">
              The Documentation engine (Docryx) is currently in development and will be integrated into the CodeLens pipeline soon.
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
