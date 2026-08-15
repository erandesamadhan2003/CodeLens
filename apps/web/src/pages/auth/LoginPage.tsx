import React from 'react';

// Faint circuit/grid texture matching the intended aesthetic
const TextureBg = () => (
  <div 
    className="absolute inset-0 z-0 opacity-[0.03] pointer-events-none"
    style={{
      backgroundImage: `radial-gradient(circle at 2px 2px, white 1px, transparent 0)`,
      backgroundSize: '32px 32px'
    }}
  />
);

const GitHubIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg" className="shrink-0">
    <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.865 8.166 6.839 9.489.5.092.682-.217.682-.482 0-.237-.008-.866-.013-1.7-2.782.604-3.369-1.34-3.369-1.34-.454-1.156-1.11-1.464-1.11-1.464-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.831.092-.646.35-1.086.636-1.336-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.578 9.578 0 0112 6.836c.85.004 1.705.114 2.504.336 1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.203 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.578.688.48C19.138 20.161 22 16.416 22 12c0-5.523-4.477-10-10-10z" />
  </svg>
);

export default function LoginPage() {
  const handleLogin = () => {
    // Redirect to the API Gateway OAuth init endpoint
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:3001';
    window.location.href = `${apiUrl}/api/v1/auth/github`;
  };

  return (
    <div className="relative min-h-screen bg-ink flex flex-col items-center justify-center p-6 overflow-hidden">
      <TextureBg />
      
      {/* Top Logo */}
      <div className="absolute top-6 lg:top-8 left-6 lg:left-8 flex items-center gap-3 z-10">
        <div className="w-8 h-8 bg-accent flex items-center justify-center border-2 border-ink shadow-[4px_4px_0px_#0A0A0A]">
          <span className="font-display font-bold text-ink text-lg">C</span>
        </div>
        <span className="font-display font-bold text-xl tracking-wide text-paper uppercase">CODELENSE</span>
      </div>

      {/* Main Content Box */}
      <div className="relative z-10 w-full max-w-md flex flex-col items-center text-center">
        <div className="border-2 border-paper text-paper bg-transparent font-mono text-sm font-bold px-3 py-1.5 rounded-[6px] uppercase tracking-wide mb-6">
          // AUTHENTICATE
        </div>
        
        <h1 className="font-display font-bold text-3xl lg:text-4xl uppercase text-paper leading-[1.1] tracking-tight mb-4">
          Connect your GitHub to continue.
        </h1>
        
        <p className="font-sans text-muted text-lg leading-relaxed mb-10 px-4">
          CodeLense needs read access to analyze your repository.
        </p>

        <button 
          onClick={handleLogin}
          className="w-full flex items-center justify-center gap-3 bg-paper border-2 border-ink text-ink font-display font-bold uppercase px-8 py-4 rounded-[6px] text-base hover:bg-[#EAEAEA] shadow-[4px_4px_0px_#0A0A0A] active:translate-x-[2px] active:translate-y-[2px] active:shadow-[2px_2px_0px_#0A0A0A] transition-all"
        >
          <GitHubIcon />
          Continue with GitHub
        </button>
      </div>
    </div>
  );
}
