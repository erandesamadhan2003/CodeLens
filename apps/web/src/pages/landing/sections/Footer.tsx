import React from 'react';

export default function Footer() {
  return (
    <footer className="w-full bg-ink border-t-2 border-[#222] py-7 px-6">
      <div className="w-full max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
        <span className="font-sans text-muted text-xs">
          © 2026 Mailflow
        </span>
        <div className="font-sans text-muted text-xs flex gap-3">
          <a href="#" className="hover:text-paper transition-colors">Docs</a>
          <span>·</span>
          <a href="#" className="hover:text-paper transition-colors">GitHub</a>
          <span>·</span>
          <a href="#" className="hover:text-paper transition-colors">Contact</a>
        </div>
      </div>
    </footer>
  );
}
