import React from 'react';
import SeverityBadge from './SeverityBadge';

export type EngineStatus = 'IDLE' | 'QUEUED' | 'RUNNING' | 'DONE' | 'FAILED';

interface EngineStatusCardProps {
  name: string;
  status: EngineStatus;
  summary?: React.ReactNode;
  onClick?: () => void;
}

export default function EngineStatusCard({ name, status, summary, onClick }: EngineStatusCardProps) {
  let statusPill = null;

  switch (status) {
    case 'QUEUED':
      statusPill = (
        <span className="px-3 py-1 border-[2px] border-muted text-muted font-mono text-sm font-bold uppercase rounded-[6px]">
          QUEUED
        </span>
      );
      break;
    case 'RUNNING':
      statusPill = (
        <span className="px-3 py-1 border-[2px] border-accent text-accent font-mono text-sm font-bold uppercase rounded-[6px] animate-pulse">
          RUNNING
        </span>
      );
      break;
    case 'DONE':
      statusPill = (
        <span className="px-3 py-1 border-[2px] border-ink bg-accent-alt text-ink font-mono text-sm font-bold uppercase rounded-[6px] shadow-[3px_3px_0px_#0A0A0A]">
          DONE
        </span>
      );
      break;
    case 'FAILED':
      statusPill = (
        <span className="px-3 py-1 border-[2px] border-danger text-danger font-mono text-sm font-bold uppercase rounded-[6px]">
          FAILED
        </span>
      );
      break;
    case 'IDLE':
    default:
      statusPill = (
        <span className="px-3 py-1 border-2 border-transparent text-muted font-mono text-sm font-bold uppercase rounded-[6px]">
          WAITING
        </span>
      );
      break;
  }

  const isClickable = !!onClick;

  return (
    <div 
      onClick={isClickable ? onClick : undefined}
      className={`flex flex-col bg-surface border-[3px] border-ink rounded-[8px] p-6 gap-6 h-full transition-all ${
        isClickable 
          ? 'cursor-pointer hover:bg-paper hover:shadow-[6px_6px_0px_#0A0A0A] active:translate-x-[3px] active:translate-y-[3px] active:shadow-none' 
          : ''
      }`}
    >
      <div className="flex items-center justify-between">
        <h3 className="font-display font-bold text-ink text-2xl uppercase tracking-tight">{name}</h3>
        {statusPill}
      </div>
      
      <div className="flex-1 text-muted text-base font-sans flex flex-col justify-center">
        {status === 'IDLE' && <div className="text-muted font-mono text-sm">Ready to analyze.</div>}
        {status === 'QUEUED' && <div className="animate-pulse bg-muted/20 h-5 w-3/4 rounded-sm"></div>}
        {status === 'RUNNING' && (
          <div className="space-y-3">
            <div className="animate-pulse bg-muted/30 h-5 w-full rounded-sm"></div>
            <div className="animate-pulse bg-muted/20 h-5 w-5/6 rounded-sm"></div>
          </div>
        )}
        {status === 'DONE' && summary && (
          <div className="flex flex-col gap-2">
            {summary}
          </div>
        )}
        {status === 'FAILED' && (
          <div className="text-danger font-mono font-bold">Engine failed to run.</div>
        )}
      </div>
    </div>
  );
}
