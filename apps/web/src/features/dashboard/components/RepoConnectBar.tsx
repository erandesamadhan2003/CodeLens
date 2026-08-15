import React, { useState, useEffect } from 'react';
import Button from '../../../components/ui/Button';
import { api } from '../../../api/client';

export interface GitHubRepository {
  id: number;
  owner: { login: string };
  name: string;
  full_name: string;
  description: string;
  default_branch: string;
  private: boolean;
  clone_url: string;
  language: string;
}

interface RepoConnectBarProps {
  onConnect: (repo: GitHubRepository) => Promise<void>;
  isConnecting: boolean;
}

export default function RepoConnectBar({ onConnect, isConnecting }: RepoConnectBarProps) {
  const [githubRepos, setGithubRepos] = useState<GitHubRepository[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedRepoFullName, setSelectedRepoFullName] = useState('');

  useEffect(() => {
    const fetchGithubRepos = async () => {
      try {
        const response = await api.get('/api/v1/repositories/github');
        setGithubRepos(response.data);
      } catch (err) {
        console.error('Failed to fetch github repos', err);
      } finally {
        setIsLoading(false);
      }
    };
    fetchGithubRepos();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedRepoFullName || isConnecting) return;
    
    const repo = githubRepos.find(r => r.full_name === selectedRepoFullName);
    if (repo) {
      await onConnect(repo);
      setSelectedRepoFullName('');
    }
  };

  return (
    <form onSubmit={handleSubmit} className="w-full flex items-center gap-4 bg-surface p-4 border-2 border-ink shadow-[4px_4px_0px_#0A0A0A] rounded-[6px]">
      <div className="flex-1 flex flex-col gap-1">
        <label className="text-xs font-mono font-bold uppercase text-muted">Add New Repository</label>
        <div className="flex-1 flex items-center bg-paper border-2 border-ink rounded-[4px] px-4 py-2 font-mono text-sm relative">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" className="text-muted mr-3 shrink-0">
            <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.865 8.166 6.839 9.489.5.092.682-.217.682-.482 0-.237-.008-.866-.013-1.7-2.782.604-3.369-1.34-3.369-1.34-.454-1.156-1.11-1.464-1.11-1.464-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.831.092-.646.35-1.086.636-1.336-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.578 9.578 0 0112 6.836c.85.004 1.705.114 2.504.336 1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.203 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.578.688.48C19.138 20.161 22 16.416 22 12c0-5.523-4.477-10-10-10z" />
          </svg>
          {isLoading ? (
            <span className="text-muted animate-pulse">Loading GitHub repositories...</span>
          ) : (
            <select 
              value={selectedRepoFullName}
              onChange={(e) => setSelectedRepoFullName(e.target.value)}
              className="bg-transparent border-none outline-none flex-1 text-ink font-bold cursor-pointer appearance-none"
              disabled={isConnecting || githubRepos.length === 0}
            >
              <option value="" disabled>Select a repository to connect...</option>
              {githubRepos.map(repo => (
                <option key={repo.id} value={repo.full_name}>
                  {repo.full_name} {repo.private ? '(Private)' : ''}
                </option>
              ))}
            </select>
          )}
          {/* Custom dropdown arrow */}
          <div className="absolute right-4 pointer-events-none text-ink">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="6 9 12 15 18 9"></polyline>
            </svg>
          </div>
        </div>
      </div>
      <Button 
        type="submit" 
        variant="primary" 
        size="lg" 
        disabled={isConnecting || !selectedRepoFullName || isLoading}
        className="self-end"
      >
        {isConnecting ? 'CONNECTING...' : 'CONNECT'}
      </Button>
    </form>
  );
}
