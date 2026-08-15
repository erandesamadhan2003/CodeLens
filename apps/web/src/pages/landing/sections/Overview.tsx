import React from 'react';
import { useNavigate } from 'react-router-dom';
import Button from '../../../components/ui/Button';

export default function HeroSection() {
  const navigate = useNavigate();
  return (
    <section className="w-full bg-ink text-paper flex flex-col items-center">
      {/* Nav bar */}
      <nav className="w-full max-w-7xl mx-auto px-6 py-6 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-accent flex items-center justify-center border-2 border-ink shadow-[4px_4px_0px_#0A0A0A]">
            <span className="font-display font-bold text-ink text-lg">C</span>
          </div>
          <span className="font-display font-bold text-xl tracking-wide uppercase">CODELENSE</span>
        </div>
        <div className="flex items-center gap-6">
          <a href="#" className="font-mono text-sm hover:text-accent transition-colors">DOCS</a>
          <a href="#" className="font-mono text-sm hover:text-accent transition-colors">GITHUB</a>
          <Button variant="light" size="sm" onClick={() => navigate('/login')}>
            CONNECT REPO ↗
          </Button>
        </div>
      </nav>

      {/* Main Hero Content */}
      <div className="w-full max-w-7xl mx-auto px-6 pt-16 pb-24 grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
        {/* Left Column */}
        <div className="flex flex-col items-start gap-6">
          <div className="border-2 border-ink bg-paper text-ink font-mono text-sm font-bold px-3 py-1 rounded-[6px] uppercase">
            // REPOSITORY INTELLIGENCE
          </div>
          <h1 className="font-display font-bold text-5xl lg:text-[72px] leading-[1.05] uppercase">
            Connect one repo.<br />Hire five<br />engines.
          </h1>
          <p className="text-muted text-lg lg:text-xl font-sans max-w-md">
            CodeLense scans your GitHub repo the moment you connect it — security, dependencies, infrastructure, roadmap, and docs, all at once.
          </p>
          <Button variant="light" size="lg" className="mt-4" onClick={() => navigate('/login')}>
            CONNECT REPO
          </Button>
        </div>

        {/* Right Column (Live Results Panel) */}
        <div className="relative w-full max-w-md mx-auto lg:ml-auto mt-8 lg:mt-0">
          {/* Status Badge */}
          <div className="absolute -top-4 -right-4 z-10 bg-accent-alt text-ink border-2 border-ink px-3 py-1 rounded-[6px] font-mono font-bold text-sm uppercase rotate-[6deg] shadow-[4px_4px_0px_#0A0A0A]">
            STATUS: READY
          </div>
          
          {/* Panel */}
          <div className="bg-[#111111] border-2 border-accent rounded-[8px] overflow-hidden flex flex-col">
            {/* Header Bar */}
            <div className="bg-accent text-ink px-4 py-3 border-b-2 border-accent flex justify-between items-center">
              <span className="font-mono text-sm font-bold">connect.ts</span>
              <span className="font-mono text-sm font-black tracking-widest">●●●</span>
            </div>
            
            {/* Body */}
            <div className="p-6 flex flex-col font-mono text-sm leading-loose text-[#A3A3A3] whitespace-pre-wrap">
              <span className="text-muted">// One repo. Five engines. Zero setup.</span>
              <br />
              <span>
                <span className="text-accent">import</span> {'{ codelense }'} <span className="text-accent">from</span> <span className="text-accent-alt">"@codelense/sdk"</span>
              </span>
              <br />
              <span>
                <span className="text-accent">const</span> scan = <span className="text-accent">await</span> codelense.analyze({'{'}
              </span>
              <span className="pl-4">
                repo: <span className="text-accent-alt">"github.com/you/project"</span>,
              </span>
              <span>{'}'})</span>
              <br />
              <span>
                scan.on(<span className="text-accent-alt">"engine:done"</span>, (result) =&gt; {'{'}
              </span>
              <span className="pl-4">
                console.log(result.engine, result.summary)
              </span>
              <span>{'}'})</span>
            </div>
          </div>
        </div>
      </div>

      {/* Marquee Ticker Strip */}
      <div className="w-full bg-accent border-y-2 border-ink overflow-hidden whitespace-nowrap py-3 flex">
        <div className="animate-marquee flex gap-4 min-w-max">
          {[...Array(6)].map((_, i) => (
            <span key={i} className="font-mono font-bold text-ink text-sm lg:text-base uppercase px-4">
              INFILRA /// DEPRA /// INFRAQ /// DEVORA /// DOCRYX ///
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}
