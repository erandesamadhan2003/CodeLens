import React from 'react';

const PREVIEW_ROWS = [
  { pkg: 'lodash', version: '4.17.11', status: 'OUTDATED' },
  { pkg: 'event-stream', version: '3.3.6', status: 'COMPROMISED' },
  { pkg: 'react', version: '18.2.0', status: 'OK' },
];



const StatusBadge = ({ status }: { status: string }) => {
  if (status === 'OUTDATED') {
    return <span className="border-2 border-warning text-warning px-2.5 py-0.5 rounded-[4px] text-[11px] font-bold tracking-wider">OUTDATED</span>;
  }
  if (status === 'COMPROMISED') {
    return <span className="bg-danger text-paper border-2 border-danger px-2.5 py-0.5 rounded-[4px] text-[11px] font-bold tracking-wider">COMPROMISED</span>;
  }
  return <span className="border-2 border-accent-alt text-accent-alt px-2.5 py-0.5 rounded-[4px] text-[11px] font-bold tracking-wider">OK</span>;
};

const DataTable = ({ rows, isLight = false }: { rows: typeof PREVIEW_ROWS, isLight?: boolean }) => {
  const containerBorder = isLight ? 'border-ink' : 'border-accent';
  const headerBorder = isLight ? 'border-ink' : 'border-[#333]';
  const rowBorder = isLight ? 'border-ink/20' : 'border-[#333]';
  const textColor = isLight ? 'text-ink' : 'text-paper';
  const bgClass = isLight ? 'bg-white' : 'bg-[#111111]';

  return (
    <div className={`w-full border-2 ${containerBorder} rounded-[8px] overflow-x-auto ${bgClass}`}>
      <div className="min-w-[500px]">
        {/* Header */}
        <div className={`grid grid-cols-[2fr_1fr_1fr] p-4 border-b-2 ${headerBorder} font-mono text-xs font-bold uppercase text-muted tracking-wide`}>
          <div>Package</div>
          <div>Installed</div>
          <div>Status</div>
        </div>
        
        {/* Body */}
        <div className="flex flex-col">
          {rows.map((row, i) => (
            <div 
              key={i} 
              className={`grid grid-cols-[2fr_1fr_1fr] p-4 font-mono text-sm items-center ${i !== rows.length - 1 ? `border-b ${rowBorder}` : ''} ${textColor}`}
            >
              <div>{row.pkg}</div>
              <div>{row.version}</div>
              <div><StatusBadge status={row.status} /></div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default function DepraSection() {
  return (
    <section className="w-full bg-ink py-[72px] px-6">
      <div className="w-full max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
        
        {/* Left Column (Text) */}
        <div className="flex flex-col items-start gap-4">
          <div className="border-2 border-paper text-paper bg-transparent font-mono text-sm font-bold px-3 py-1.5 rounded-[6px] uppercase tracking-wide">
            // DEPENDENCY AUDIT
          </div>
          
          <h2 className="font-display font-bold text-4xl lg:text-5xl uppercase text-paper leading-[1.05] tracking-tight mt-2">
            Depra audits every package you shipped.
          </h2>
          
          <p className="font-sans text-muted text-lg lg:text-xl leading-relaxed mt-2 max-w-md">
            Every dependency in your package manager, checked against known vulnerabilities and staleness — the moment you connect your repo.
          </p>
        </div>

        {/* Right Column (Preview Table) */}
        <div className="w-full relative">
          <DataTable rows={PREVIEW_ROWS} />
        </div>
      </div>
    </section>
  );
}
