import { useState } from 'react';
import { api } from '../../../api/client';

export const CICDSetupModal = ({ repo, onClose }) => {
  const [apiKey, setApiKey] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const generateApiKey = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api.post('/api/v1/auth/api-keys', { name: `GitHub Actions - ${repo.name}` });
      console.log("API Key Creation Response:", res);
      setApiKey(res.data.apiKey);
    } catch (err: any) {
      console.error("API Key Creation Error:", err);
      setError(err.response?.data?.message || err.message || 'Failed to generate API Key');
    } finally {
      setLoading(false);
    }
  };

  const workflowYaml = `name: CodeLens Automated Scan

on:
  push:
    branches: [ "main", "master" ]

jobs:
  codelens-scan:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger CodeLens Analysis
        run: |
          curl -X POST "${window.location.origin}/api/v1/runs" \\
          -H "Content-Type: application/json" \\
          -H "x-api-key: \${{ secrets.CODELENS_API_KEY }}" \\
          -d '{
            "repoId": "${repo.id}",
            "branch": "\${{ github.ref_name }}"
          }'
`;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/80 p-6">
      <div className="bg-paper border-4 border-ink w-full max-w-3xl flex flex-col shadow-[8px_8px_0px_#0A0A0A] max-h-[90vh]">

        <header className="flex items-center justify-between p-4 border-b-4 border-ink bg-surface">
          <h2 className="font-display font-bold text-2xl uppercase tracking-tight">GitHub Actions Setup</h2>
          <button
            onClick={onClose}
            className="w-10 h-10 flex items-center justify-center border-2 border-ink bg-paper hover:bg-danger hover:text-white transition-colors"
          >
            ✕
          </button>
        </header>

        <div className="p-6 overflow-y-auto flex flex-col gap-6">
          <p className="font-mono text-sm leading-relaxed">
            Automate your security and infrastructure scans by integrating CodeLens into your CI/CD pipeline.
            Whenever code is pushed, GitHub Actions will trigger an analysis automatically.
          </p>

          {/* API Key Generation */}
          <div className="bg-surface border-2 border-ink p-5">
            <h3 className="font-display font-bold text-lg uppercase mb-2">1. Generate API Key</h3>
            <p className="font-mono text-xs text-muted mb-4">You need an API key to authenticate the GitHub Action runner.</p>

            {error && <div className="text-danger font-bold text-sm mb-3">{error}</div>}

            {!apiKey ? (
              <button
                onClick={generateApiKey}
                disabled={loading}
                className="px-6 py-2 font-display font-bold uppercase border-2 border-ink shadow-[2px_2px_0px_#0A0A0A] bg-accent hover:bg-accent/80 active:translate-y-[2px] active:shadow-none transition-all disabled:opacity-50"
              >
                {loading ? 'Generating...' : 'Generate Secret API Key'}
              </button>
            ) : (
              <div className="flex flex-col gap-2">
                <div className="bg-ink text-paper p-3 font-mono text-sm break-all select-all">
                  {apiKey}
                </div>
                <p className="font-bold text-danger text-sm">⚠️ Copy this key now! It will not be shown again.</p>
                <p className="font-mono text-xs">Add this as a repository secret in GitHub named <code className="bg-ink/10 px-1 font-bold">CODELENS_API_KEY</code>.</p>
              </div>
            )}
          </div>

          {/* Workflow YAML */}
          <div className="bg-surface border-2 border-ink p-5 flex flex-col gap-3">
            <h3 className="font-display font-bold text-lg uppercase">2. Add Workflow File</h3>
            <p className="font-mono text-xs text-muted">Create a file at <code className="bg-ink/10 px-1 font-bold">.github/workflows/codelens.yml</code> and paste this code:</p>
            <div className="relative group">
              <pre className="bg-ink text-paper p-4 font-mono text-sm overflow-x-auto whitespace-pre-wrap">
                {workflowYaml}
              </pre>
              <button
                onClick={() => navigator.clipboard.writeText(workflowYaml)}
                className="absolute top-2 right-2 bg-paper text-ink px-3 py-1 font-bold text-xs uppercase border-2 border-ink opacity-0 group-hover:opacity-100 transition-opacity hover:bg-accent"
              >
                Copy YAML
              </button>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
};
