import React from 'react';

type Severity = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO';

interface SeverityBadgeProps {
  severity: Severity;
  count: number;
}

export default function SeverityBadge({ severity, count }: SeverityBadgeProps) {
  let styles = '';
  
  switch (severity) {
    case 'CRITICAL':
      styles = 'bg-danger text-paper border-danger';
      break;
    case 'HIGH':
      styles = 'bg-danger text-paper border-danger';
      break;
    case 'MEDIUM':
      styles = 'bg-warning text-ink border-ink';
      break;
    case 'LOW':
    case 'INFO':
    default:
      styles = 'bg-transparent text-muted border-muted';
      break;
  }

  return (
    <div className={`inline-flex items-center justify-center px-2 py-0.5 border-2 rounded-[4px] font-mono text-xs font-bold ${styles}`}>
      {count} {severity}
    </div>
  );
}
