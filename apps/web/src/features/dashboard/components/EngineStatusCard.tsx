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
        <span className="px-2 py-0.5 border-2 border-muted text-muted font-mono text-xs font-bold uppercase rounded-[4px]">
          QUEUED
        </span>
      );
      break;
    case 'RUNNING':
      statusPill = (
        <span className="px-2 py-0.5 border-2 border-accent text-accent font-mono text-xs font-bold uppercase rounded-[4px] animate-pulse">
          RUNNING
        </span>
      );
      break;
    case 'DONE':
      statusPill = (
        <span className="px-2 py-0.5 border-2 border-ink bg-accent-alt text-ink font-mono text-xs font-bold uppercase rounded-[4px] shadow-[2px_2px_0px_#0A0A0A]">
          DONE
        </span>
      );
      break;
    case 'FAILED':
      statusPill = (
        <span className="px-2 py-0.5 border-2 border-danger text-danger font-mono text-xs font-bold uppercase rounded-[4px]">
          FAILED
        </span>
      );
      break;
    case 'IDLE':
    default:
      statusPill = (
        <span className="px-2 py-0.5 border-2 border-transparent text-muted font-mono text-xs font-bold uppercase rounded-[4px]">
          WAITING
        </span>
      );
      break;
  }

  const isClickable = !!onClick;

  return (
    <div 
      onClick={isClickable ? onClick : undefined}
      className={`flex flex-col bg-surface border-2 border-ink rounded-[6px] p-4 gap-4 h-full transition-all ${
        isClickable 
          ? 'cursor-pointer hover:bg-paper hover:shadow-[4px_4px_0px_#0A0A0A] active:translate-x-[2px] active:translate-y-[2px] active:shadow-none' 
          : ''
      }`}
    >
      <div className="flex items-center justify-between">
        <h3 className="font-display font-bold text-ink text-lg uppercase tracking-tight">{name}</h3>
        {statusPill}
      </div>
      
      <div className="flex-1 text-muted text-sm font-sans flex flex-col justify-center">
        {status === 'IDLE' && <div className="animate-pulse bg-muted/20 h-4 w-3/4 rounded-sm"></div>}
        {status === 'QUEUED' && <div className="animate-pulse bg-muted/20 h-4 w-3/4 rounded-sm"></div>}
        {status === 'RUNNING' && (
          <div className="space-y-2">
            <div className="animate-pulse bg-muted/30 h-4 w-full rounded-sm"></div>
            <div className="animate-pulse bg-muted/20 h-4 w-5/6 rounded-sm"></div>
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
