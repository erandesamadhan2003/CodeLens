import React from 'react';

export interface Repository {
  id: string;
  github_repo_id: string;
  owner: string;
  name: string;
  full_name: string;
  default_branch: string;
  is_private: boolean;
}

interface RepoSidebarProps {
  repositories: Repository[];
  activeRepoId: string | null;
  onSelectRepo: (repoId: string) => void;
}

export default function RepoSidebar({ repositories, activeRepoId, onSelectRepo }: RepoSidebarProps) {
  return (
    <aside className="w-64 shrink-0 flex flex-col gap-4 border-r-2 border-ink pr-6">
      <h2 className="font-display font-bold text-xl uppercase tracking-tight">Connected Repos</h2>
      <div className="flex flex-col gap-2">
        {repositories.length === 0 ? (
          <div className="text-muted text-sm font-sans italic">
            No repositories connected yet.
          </div>
        ) : (
          repositories.map((repo) => {
            const isActive = repo.id === activeRepoId;
            return (
              <button
                key={repo.id}
                onClick={() => onSelectRepo(repo.id)}
                className={`text-left px-3 py-2 border-2 rounded-[6px] font-mono text-sm transition-all ${
                  isActive 
                    ? 'bg-accent border-ink text-ink shadow-[2px_2px_0px_#0A0A0A] font-bold' 
                    : 'bg-transparent border-transparent hover:border-ink hover:bg-surface text-muted hover:text-ink'
                }`}
              >
                <div className="flex items-center gap-2">
                  {repo.is_private && (
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                      <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
                    </svg>
                  )}
                  <span className="truncate">{repo.name}</span>
                </div>
              </button>
            );
          })
        )}
      </div>
    </aside>
  );
}
