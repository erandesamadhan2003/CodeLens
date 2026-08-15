import React from 'react';
import { useAuth } from '../../auth/hooks/useAuth';

// Same circuit texture used in login
const TextureBg = () => (
  <div 
    className="absolute inset-0 z-0 opacity-[0.03] pointer-events-none"
    style={{
      backgroundImage: `radial-gradient(circle at 2px 2px, white 1px, transparent 0)`,
      backgroundSize: '32px 32px'
    }}
  />
);

export default function HomePage() {
  const { user, logout } = useAuth();

  return (
    <div className="relative min-h-screen bg-ink flex flex-col items-center justify-center p-6 overflow-hidden">
      <TextureBg />
      
      {/* Top Logo */}
      <div className="absolute top-6 lg:top-8 left-6 lg:left-8 flex items-center gap-3 z-10">
        <div className="w-8 h-8 bg-accent flex items-center justify-center border-2 border-ink shadow-[4px_4px_0px_#0A0A0A]">
          <span className="font-display font-bold text-ink text-lg">C</span>
        </div>
        <span className="font-display font-bold text-xl tracking-wide text-paper uppercase">CODELENSE</span>
      </div>

      {/* Main Content Box */}
      <div className="relative z-10 w-full max-w-lg flex flex-col items-center text-center">
        {user?.avatar_url && (
          <img 
            src={user.avatar_url} 
            alt={`${user.username}'s avatar`}
            className="w-24 h-24 rounded-full border-4 border-ink shadow-[4px_4px_0px_#0A0A0A] mb-6 object-cover"
          />
        )}
        
        <h1 className="font-display font-bold text-3xl lg:text-5xl uppercase text-paper leading-[1.1] tracking-tight mb-4">
          Welcome, {user?.username || 'Hacker'}.
        </h1>
        <p className="font-sans text-muted text-lg lg:text-xl leading-relaxed mb-10">
          You have successfully authenticated with GitHub.
        </p>

        <button 
          onClick={logout}
          className="flex items-center justify-center gap-3 bg-transparent border-2 border-paper text-paper font-display font-bold uppercase px-8 py-3 rounded-[6px] text-sm hover:bg-paper hover:text-ink transition-colors"
        >
          Logout
        </button>
      </div>
    </div>
  );
}
