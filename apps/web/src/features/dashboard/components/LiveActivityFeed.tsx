import React, { useEffect, useRef } from 'react';

interface FeedEvent {
  id: string;
  timestamp: string;
  engine: string;
  message: string;
  type?: 'info' | 'success' | 'error' | 'warning';
}

interface LiveActivityFeedProps {
  events: FeedEvent[];
}

export default function LiveActivityFeed({ events }: LiveActivityFeedProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [events]);

  return (
    <div className="w-full bg-ink text-muted p-4 border-2 border-ink rounded-[6px] shadow-[4px_4px_0px_#0A0A0A] font-mono text-xs flex flex-col h-[200px]">
      <div className="flex items-center gap-2 mb-4 border-b border-muted/30 pb-2">
        <span className="w-2 h-2 rounded-full bg-danger"></span>
        <span className="w-2 h-2 rounded-full bg-warning"></span>
        <span className="w-2 h-2 rounded-full bg-success"></span>
        <span className="text-paper ml-2 font-bold uppercase tracking-widest text-[10px]">Activity Feed</span>
      </div>
      
      <div 
        ref={scrollRef}
        className="flex-1 overflow-y-auto flex flex-col gap-2 pr-2 scrollbar-thin"
      >
        {events.length === 0 ? (
          <div className="text-muted/50 italic">// Waiting for activity...</div>
        ) : (
          events.map((event) => (
            <div key={event.id} className="flex items-start gap-3 hover:bg-muted/10 p-1 rounded transition-colors">
              <span className="text-muted/50 shrink-0">{event.timestamp}</span>
              <span className="text-accent shrink-0 font-bold w-[70px]">{event.engine}</span>
              <span className="text-muted/50 shrink-0">→</span>
              <span className={`
                ${event.type === 'error' ? 'text-danger font-bold' : ''}
                ${event.type === 'success' ? 'text-accent-alt font-bold' : ''}
                ${event.type === 'warning' ? 'text-warning font-bold' : ''}
                ${!event.type || event.type === 'info' ? 'text-paper' : ''}
              `}>
                {event.message}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
