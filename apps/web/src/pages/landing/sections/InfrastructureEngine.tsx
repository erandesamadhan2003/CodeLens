import React from 'react';

const FEATURES = [
  {
    eyebrow: '// ARCHITECTURE',
    heading: 'Topology',
    copy: 'Maps your services and how they actually talk to each other.',
  },
  {
    eyebrow: '// COST',
    heading: 'Spend',
    copy: 'Flags over-provisioned resources quietly draining your budget.',
  },
  {
    eyebrow: '// SCALING',
    heading: 'Capacity',
    copy: 'Recommends auto-scaling and capacity plans before you need them.',
  },
  {
    eyebrow: '// PROVIDERS',
    heading: 'Comparison',
    copy: 'Compares AWS, GCP, and Azure for your exact workload.',
  },
];

export default function InfrastructureEngine() {
  return (
    <section className="w-full bg-paper py-24 lg:py-28 px-6">
      <div className="w-full max-w-7xl mx-auto flex flex-col gap-16">
        <h2 className="font-display font-bold text-3xl lg:text-4xl uppercase text-ink">
          What Infraq checks.
        </h2>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
          {FEATURES.map((feature, idx) => (
            <div 
              key={idx} 
              className="bg-white border-2 border-ink rounded-[6px] p-5 flex flex-col items-start"
            >
              <span className="font-mono text-muted text-xs font-bold uppercase mb-4 tracking-wide">
                {feature.eyebrow}
              </span>
              <h3 className="font-display font-bold text-base text-ink mb-1.5 uppercase">
                {feature.heading}
              </h3>
              <p className="font-sans text-muted text-[13px] leading-relaxed">
                {feature.copy}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
