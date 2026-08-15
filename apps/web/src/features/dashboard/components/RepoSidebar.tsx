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
    <aside className="w-full md:w-72 lg:w-80 shrink-0 flex flex-col gap-6 md:border-r-4 border-ink md:pr-8">
      <h2 className="font-display font-bold text-2xl lg:text-3xl uppercase tracking-tight">Connected Repos</h2>
      <div className="flex flex-col gap-3">
        {repositories.length === 0 ? (
          <div className="text-muted text-base font-sans italic">
            No repositories connected yet.
          </div>
        ) : (
          repositories.map((repo) => {
            const isActive = repo.id === activeRepoId;
            return (
              <button
                key={repo.id}
                onClick={() => onSelectRepo(repo.id)}
                className={`text-left px-4 py-3 border-2 rounded-[8px] font-mono text-base transition-all ${
                  isActive 
                    ? 'bg-accent border-ink text-ink shadow-[3px_3px_0px_#0A0A0A] font-bold scale-[1.02]' 
                    : 'bg-transparent border-transparent hover:border-ink hover:bg-surface text-muted hover:text-ink'
                }`}
              >
                <div className="flex items-center gap-3">
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
