import React from 'react';

export default function DocryxSection() {
  return (
    <section className="w-full bg-ink py-[72px] px-6">
      <div className="w-full max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
        
        {/* Left Column (Text) */}
        <div className="flex flex-col items-start gap-4">
          <div className="border-2 border-paper text-paper bg-transparent font-mono text-sm font-bold px-3 py-1.5 rounded-[6px] uppercase tracking-wide">
            // DOCUMENT GENERATION
          </div>
          
          <h2 className="font-display font-bold text-4xl lg:text-[56px] uppercase text-paper leading-[1.05] tracking-tight mt-2">
            Docryx writes your docs.
          </h2>
          
          <p className="font-sans text-muted text-lg lg:text-xl leading-relaxed mt-2 max-w-md">
            Docryx reads your codebase and automatically generates and maintains your README and API documentation — so you never have to.
          </p>
        </div>

        {/* Right Column (Fixed Doc Preview Panel) */}
        <div className="relative w-full max-w-lg mx-auto lg:ml-auto mt-8 lg:mt-0">
          <div className="bg-[#111111] border-2 border-accent rounded-[8px] overflow-hidden flex flex-col shadow-none">
            {/* Header Bar */}
            <div className="bg-accent text-ink px-4 py-3 border-b-2 border-accent flex justify-between items-center">
              <span className="font-mono text-sm font-bold">README.md — generated</span>
              <span className="font-mono text-sm font-black tracking-widest">●●●</span>
            </div>
            
            {/* Body */}
            <div className="p-6 flex flex-col font-sans text-sm leading-relaxed text-[#D4D4D4] whitespace-pre-wrap">
              <h1 className="text-[28px] font-bold text-white mb-2 pb-1 border-b border-[#333]">CodeLense</h1>
              <p className="mb-5 text-[#A3A3A3]">CodeLense is the missing intelligence layer for your repository.</p>
              
              <h2 className="text-xl font-bold text-white mb-3">Installation</h2>
              <pre className="bg-ink border border-[#333] rounded-[4px] p-3 mb-5 font-mono text-[13px] text-accent-alt overflow-x-auto">
                <code>npm install @codelense/sdk</code>
              </pre>

              <h2 className="text-xl font-bold text-white mb-3">Usage</h2>
              <pre className="bg-ink border border-[#333] rounded-[4px] p-3 font-mono text-[13px] overflow-x-auto">
                <code><span className="text-[#FF7B72]">import</span> {'{ codelense }'} <span className="text-[#FF7B72]">from</span> <span className="text-[#A5D6FF]">'@codelense/sdk'</span>;</code>
              </pre>
            </div>
          </div>
        </div>

      </div>
    </section>
  );
}
