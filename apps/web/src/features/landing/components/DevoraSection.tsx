import React from 'react';

const PREVIEW_ITEMS = [
  { label: '01 · NOW', title: 'Fix 3 critical Infilra findings', desc: 'Highest-severity issues flagged before your next release.' },
  { label: '02 · NEXT', title: 'Upgrade 4 outdated dependencies', desc: 'Packages Depra flagged as stale or compromised.' },
  { label: '03 · LATER', title: 'Adopt the Infraq scaling plan', desc: 'Move to the recommended provider/capacity setup.' }
];



const Timeline = ({ items }: { items: typeof PREVIEW_ITEMS }) => {
  return (
    <div className="flex flex-col w-full">
      {items.map((item, idx) => (
        <div key={idx} className="flex flex-row items-stretch">
          {/* Left / Label */}
          <div className="w-[80px] md:w-[100px] shrink-0 flex flex-col items-end pr-4">
            <div className="font-mono text-[11px] md:text-xs font-bold text-ink py-4 tracking-wide">
              {item.label}
            </div>
          </div>
          
          {/* Middle / Line */}
          <div className="flex flex-col items-center mr-4 md:mr-6">
            <div className="w-2 h-2 rounded-full bg-ink mt-5 z-10 shadow-[0_0_0_4px_#FAFAF8]"></div>
            {idx !== items.length - 1 && (
              <div className="w-[2px] bg-ink flex-1 -my-1"></div>
            )}
          </div>
          
          {/* Right / Card */}
          <div className="flex-1 pb-6">
            <div className="bg-white border-2 border-ink rounded-[6px] p-4 lg:p-5 shadow-none">
              <h3 className="font-display font-bold text-[15px] text-ink mb-1 leading-tight">{item.title}</h3>
              <p className="font-sans text-muted text-sm leading-relaxed">{item.desc}</p>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};

export default function DevoraSection() {
  return (
    <section className="w-full bg-paper py-[72px] px-6">
      <div className="w-full max-w-7xl mx-auto flex flex-col items-center text-center">
        
        <div className="border-2 border-ink text-ink bg-transparent font-mono text-sm font-bold px-3 py-1.5 rounded-[6px] uppercase tracking-wide">
          // ROADMAP GENERATION
        </div>
        
        <h2 className="font-display font-bold text-4xl lg:text-[56px] uppercase text-ink leading-[1.05] tracking-tight mt-6 max-w-3xl">
          Devora plans what's next.
        </h2>
        
        <p className="font-sans text-muted text-lg lg:text-xl leading-relaxed mt-4 max-w-2xl">
          Devora reads your repo's coding trends and generates a prioritized roadmap — so planning stops living in a stale doc nobody opens.
        </p>

        <div className="w-full max-w-2xl mt-12 text-left">
          <Timeline items={PREVIEW_ITEMS} />
        </div>
      </div>
    </section>
  );
}
