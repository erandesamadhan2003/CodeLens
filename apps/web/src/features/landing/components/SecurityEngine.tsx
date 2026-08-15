import React from 'react';

export default function SecurityEngine() {
  return (
    <section className="w-full bg-accent py-16 px-6 relative">
      <div className="w-full max-w-7xl mx-auto flex flex-col">
        
        {/* Top elements */}
        <div className="flex flex-col items-start gap-4">
          <div className="bg-paper text-ink border-2 border-ink font-mono text-sm font-bold px-3 py-1.5 rounded-[6px] uppercase flex items-center gap-2 shadow-[2px_2px_0px_#0A0A0A] lg:shadow-[4px_4px_0px_#0A0A0A]">
            <div className="w-2.5 h-2.5 bg-accent-alt border-2 border-ink"></div>
            THE FIRST LINE OF DEFENSE FOR YOUR CODEBASE
          </div>
          
          <div className="mt-8 max-w-2xl">
            <p className="font-mono text-sm font-bold text-[#6A210D] uppercase mb-2">
              OBLIGATORY SECURITY PITCH BELOW
            </p>
            <h2 className="font-display font-bold text-4xl lg:text-6xl uppercase text-ink leading-none tracking-tight">
              Infilra finds what you missed.
            </h2>
          </div>
        </div>

        {/* Callout Card */}
        <div className="relative w-full max-w-[520px] mx-auto lg:ml-auto lg:mr-0 mt-16 lg:-mt-12">
          {/* Sticker Tag */}
          <div className="absolute -top-4 -left-2 lg:-left-6 z-10 bg-accent-alt text-ink border-2 border-ink px-3 py-1 rounded-[6px] font-mono font-bold text-sm uppercase -rotate-[4deg] shadow-[2px_2px_0px_#0A0A0A] lg:shadow-[4px_4px_0px_#0A0A0A]">
            // VULNERABILITY SCAN
          </div>
          
          <div className="bg-ink border-2 border-ink rounded-[8px] p-6 lg:p-8 flex flex-col gap-5 text-[#A3A3A3] font-sans text-base lg:text-lg leading-relaxed shadow-[4px_4px_0px_#0A0A0A] lg:shadow-[6px_6px_0px_#0A0A0A]">
            <p>
              Your repo probably has a security hole in it right now. You just don't know where — because nobody reads every diff before it merges.
            </p>
            <p>
              Infilra scans the full codebase the moment you connect it — flagging exploitable vulnerabilities before they ship, not after.
            </p>
          </div>
        </div>

      </div>
    </section>
  );
}
