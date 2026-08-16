import React, { useState, useEffect } from 'react';
import { useAuth } from '../../auth/hooks/useAuth';
import RepoConnectBar, { GitHubRepository } from '../components/RepoConnectBar';
import EngineStatusCard, { EngineStatus } from '../components/EngineStatusCard';
import LiveActivityFeed from '../components/LiveActivityFeed';
import SeverityBadge from '../components/SeverityBadge';
import RepoSidebar, { Repository } from '../components/RepoSidebar';
import { api } from '../../../api/client';
import { useNavigate } from 'react-router-dom';
import { CICDSetupModal } from '../components/CICDSetupModal';

// A subtle grid pattern for the paper background
const GridBg = () => (
  <div 
    className="absolute inset-0 z-0 opacity-[0.05] pointer-events-none"
    style={{
      backgroundImage: `linear-gradient(#0A0A0A 1px, transparent 1px), linear-gradient(90deg, #0A0A0A 1px, transparent 1px)`,
      backgroundSize: '24px 24px'
    }}
  />
);

export default function HomePage() {
  const { user, logout } = useAuth();
  
  // Repository state
  const [connectedRepos, setConnectedRepos] = useState<Repository[]>([]);
  const [activeRepoId, setActiveRepoId] = useState<string | null>(null);
  const [isConnecting, setIsConnecting] = useState(false);
  const [showCICDModal, setShowCICDModal] = useState(false);

  // Real backend states
  const [isTriggering, setIsTriggering] = useState(false);
  const [events, setEvents] = useState<any[]>([]);
  
  const [latestRun, setLatestRun] = useState<any>(null);
  const navigate = useNavigate();

  // Engine Status Derivation
  const getEngineStatus = (engineName: string): EngineStatus => {
    if (!latestRun) return 'IDLE';
    const engineRes = latestRun.engineResults?.find((er: any) => er.engine === engineName);
    if (!engineRes) return 'IDLE';
    
    switch (engineRes.status) {
      case 'queued': return 'QUEUED';
      case 'processing': return 'RUNNING';
      case 'completed': return 'DONE';
      case 'failed': return 'FAILED';
      default: return 'IDLE';
    }
  };

  // Fetch connected repos on mount
  useEffect(() => {
    const fetchConnectedRepos = async () => {
      try {
        const response = await api.get('/api/v1/repositories');
        setConnectedRepos(response.data.data || response.data);
        if (response.data.data?.length > 0) {
          setActiveRepoId(response.data.data[0].id);
        } else if (response.data.length > 0) {
          setActiveRepoId(response.data[0].id);
        }
      } catch (err) {
        console.error('Failed to fetch connected repos', err);
      }
    };
    fetchConnectedRepos();
  }, []);

  const handleConnectRepo = async (githubRepo: GitHubRepository) => {
    setIsConnecting(true);
    try {
      const response = await api.post('/api/v1/repositories', {
        githubRepoId: String(githubRepo.id),
        owner: githubRepo.owner.login,
        name: githubRepo.name,
        fullName: githubRepo.full_name,
        description: githubRepo.description,
        defaultBranch: githubRepo.default_branch,
        isPrivate: githubRepo.private,
        cloneUrl: githubRepo.clone_url,
        language: githubRepo.language
      });
      const newRepo = response.data;
      setConnectedRepos(prev => [newRepo, ...prev]);
      setActiveRepoId(newRepo.id);
    } catch (err) {
      console.error('Failed to connect repo', err);
    } finally {
      setIsConnecting(false);
    }
  };

  // Polling for the latest run of the active repo
  useEffect(() => {
    if (!activeRepoId) {
      setLatestRun(null);
      return;
    }

    let mounted = true;
    const fetchLatestRunDetails = async () => {
      try {
        const res = await api.get(`/api/v1/runs?repoId=${activeRepoId}&limit=1`);
        if (!mounted) return;
        
        const runSummary = res.data.data?.[0];
        if (runSummary) {
          // Fetch full run details to get engine statuses
          const fullRunRes = await api.get(`/api/v1/runs/${runSummary.id}`);
          if (!mounted) return;
          const fullRun = fullRunRes.data.data;
          setLatestRun(fullRun);
        } else {
          setLatestRun(null);
        }
      } catch (err) {
        console.error('Polling error', err);
      }
    };

    fetchLatestRunDetails();
    const interval = setInterval(fetchLatestRunDetails, 5000);
    return () => { mounted = false; clearInterval(interval); };
  }, [activeRepoId]);

  const addEvent = (engine: string, message: string, type: 'info' | 'success' | 'error' | 'warning' = 'info') => {
    setEvents(prev => [...prev, {
      id: Math.random().toString(36).substring(7),
      timestamp: new Date().toLocaleTimeString('en-US', { hour12: false }),
      engine,
      message,
      type
    }].slice(-50)); // keep last 50
  };

  const activeRepo = connectedRepos.find(r => r.id === activeRepoId);

  const handleAnalyze = async () => {
    if (!activeRepo) return;
    setIsTriggering(true);
    addEvent('SYSTEM', `Manual analysis triggered for ${activeRepo.full_name}.`, 'info');

    // Optimistically set to QUEUED to immediately show skeleton loaders
    setLatestRun({
      status: 'queued',
      engineResults: ['infraq', 'infilra', 'depra', 'devora', 'docryx'].map(e => ({
        engine: e,
        status: 'queued'
      }))
    });

    try {
      await api.post('/api/v1/runs', {
        repoId: activeRepo.id,
        branch: activeRepo.default_branch
      });
      addEvent('SYSTEM', 'Analysis job queued on backend API...', 'success');
      // The polling interval will naturally pick up the new run!
    } catch (err) {
      console.error('Failed to trigger analysis', err);
      addEvent('INFRAQ', 'Failed to trigger backend analysis API.', 'error');
    } finally {
      setIsTriggering(false);
    }
  };

  return (
    <div className="relative min-h-screen bg-paper text-ink flex flex-col font-sans">
      <GridBg />
      
      {/* Top Navbar */}
      <header className="relative z-10 w-full px-6 py-4 flex items-center justify-between border-b-2 border-ink bg-paper">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-accent flex items-center justify-center border-2 border-ink shadow-[4px_4px_0px_#0A0A0A]">
            <span className="font-display font-bold text-ink text-lg">C</span>
          </div>
          <span className="font-display font-bold text-xl tracking-wide uppercase">CODELENSE</span>
        </div>
        
        <div className="flex items-center gap-6">
          <div className="hidden md:flex items-center gap-3">
            <span className="font-mono text-sm font-bold">{user?.username}</span>
            {user?.avatar_url && (
              <img 
                src={user.avatar_url} 
                alt="Avatar" 
                className="w-8 h-8 border-2 border-ink rounded-[4px] object-cover"
              />
            )}
          </div>
          <button 
            onClick={logout}
            className="font-mono text-sm font-bold uppercase hover:text-accent transition-colors underline decoration-2 underline-offset-4"
          >
            Logout
          </button>
        </div>
      </header>

      {/* Main Dashboard Content */}
      <main className="relative z-10 flex-1 w-full flex flex-col md:flex-row px-6 md:px-12 py-10 gap-12 lg:gap-16">
        
        {/* Sidebar */}
        <RepoSidebar 
          repositories={connectedRepos}
          activeRepoId={activeRepoId}
          onSelectRepo={setActiveRepoId}
        />

        {/* Dashboard Area */}
        <div className="flex-1 flex flex-col gap-12 min-w-0">
          
          <div className="flex flex-col gap-6">
            <div className="flex flex-col gap-3">
              <h1 className="font-display font-bold text-4xl lg:text-5xl uppercase tracking-tight">Audit Dashboard</h1>
              <p className="text-muted text-xl">Select a connected repository or add a new one.</p>
            </div>
            
            {/* Connect Bar */}
            <RepoConnectBar onConnect={handleConnectRepo} isConnecting={isConnecting} />
          </div>

          {activeRepo ? (
            <div className="flex flex-col gap-10">
              <div className="flex items-center justify-between border-b-4 border-ink pb-6">
                <div className="flex flex-col gap-2 min-w-0 pr-4">
                  <h2 className="font-mono font-bold text-3xl lg:text-4xl truncate" title={activeRepo.full_name}>{activeRepo.full_name}</h2>
                  <span className="text-muted font-mono text-base bg-surface px-3 py-1 rounded-full border border-ink/20 self-start">Branch: {activeRepo.default_branch}</span>
                </div>
                <div className="flex items-center gap-4 shrink-0">
                  <button 
                    onClick={() => setShowCICDModal(true)}
                    className="bg-paper text-ink border-[3px] border-ink font-display font-bold text-lg uppercase px-6 py-4 rounded-[8px] shadow-[4px_4px_0px_#0A0A0A] hover:bg-surface active:translate-x-[2px] active:translate-y-[2px] active:shadow-none transition-all flex items-center gap-2"
                  >
                    <span>⚙️</span> CI/CD Setup
                  </button>
                  <button 
                    onClick={handleAnalyze}
                    disabled={isTriggering || (latestRun && latestRun.status !== 'completed' && latestRun.status !== 'failed')}
                    className="bg-accent text-ink border-[3px] border-ink font-display font-bold text-xl uppercase px-8 py-4 rounded-[8px] shadow-[6px_6px_0px_#0A0A0A] active:translate-x-[3px] active:translate-y-[3px] active:shadow-[3px_3px_0px_#0A0A0A] transition-all disabled:opacity-50 shrink-0"
                  >
                    {(latestRun && latestRun.status !== 'completed' && latestRun.status !== 'failed') ? 'Running...' : 'Analyze Now'}
                  </button>
                </div>
              </div>

              {/* Engine Grid */}
              <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">
                <EngineStatusCard 
                  name="Infrastructure" 
                  status={getEngineStatus('infraq')} 
                  onClick={() => {
                    navigate(`/dashboard/infrastructure/${activeRepo.id}`);
                  }}
                  summary={
                    latestRun?.id ? (
                      <div className="flex gap-2 text-xs font-mono mt-1">
                        <span className="text-muted border-b border-muted">Click to view report &rarr;</span>
                      </div>
                    ) : null
                  }
                />
                <EngineStatusCard 
                  name="Security" 
                  status={getEngineStatus('infilra')} 
                  onClick={() => {
                    navigate(`/dashboard/security/${activeRepo.id}`);
                  }}
                  summary={
                    latestRun?.id ? (
                      <div className="flex gap-2 text-xs font-mono mt-1">
                        <span className="text-muted border-b border-muted">Click to view report &rarr;</span>
                      </div>
                    ) : null
                  }
                />
                <EngineStatusCard 
                  name="Dependency" 
                  status={getEngineStatus('depra')} 
                  onClick={() => {
                    navigate(`/dashboard/dependency/${activeRepo.id}`);
                  }}
                  summary={
                    latestRun?.id ? (
                      <div className="flex gap-2 text-xs font-mono mt-1">
                        <span className="text-muted border-b border-muted">Click to view report &rarr;</span>
                      </div>
                    ) : null
                  }
                />
                {/* Devora (Code Quality) engine — not yet built, commented out
                <EngineStatusCard 
                  name="Code Quality" 
                  status={getEngineStatus('devora')} 
                  onClick={() => {
                    navigate(`/dashboard/code-quality/${activeRepo.id}`);
                  }}
                  summary={
                    latestRun?.id ? (
                      <div className="flex gap-2 text-xs font-mono mt-1">
                        <span className="text-muted border-b border-muted">Click to view report &rarr;</span>
                      </div>
                    ) : null
                  }
                />
                */}
                <EngineStatusCard 
                  name="Documentation" 
                  status={getEngineStatus('docryx')} 
                  onClick={() => {
                    navigate(`/dashboard/documents/${activeRepo.id}`);
                  }}
                  summary={
                    latestRun?.id ? (
                      <div className="flex gap-2 text-xs font-mono mt-1">
                        <span className="text-muted border-b border-muted">Click to view report &rarr;</span>
                      </div>
                    ) : null
                  }
                />
              </div>

              {/* Activity Feed */}
              <div className="mt-4">
                <LiveActivityFeed events={events} />
              </div>
            </div>
          ) : (
            <div className="flex-1 border-2 border-dashed border-muted rounded-[6px] flex items-center justify-center text-muted font-mono p-10 text-center">
              No repository selected. Connect a repository above to view its dashboard.
            </div>
          )}
          
        </div>
      </main>
      
      {showCICDModal && activeRepo && (
        <CICDSetupModal repo={activeRepo} onClose={() => setShowCICDModal(false)} />
      )}
    </div>
  );
}
