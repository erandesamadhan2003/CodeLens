import { query } from '../config/database.js';
import { decrypt } from '../utils/crypto.js';
import { dispatchAllEngineJobs } from './queue.service.js';
import { getLatestCommit } from './github.service.js';
import logger from '../utils/logger.js';

/**
 * Triggers an infrastructure analysis run.
 */
export const triggerInfrastructureAnalysis = async (userId, repoId, providedSha, branch) => {
  // 1. Verify repo belongs to user
  const repoResult = await query(
    'SELECT * FROM repositories WHERE id = $1 AND user_id = $2 AND is_active = true',
    [repoId, userId]
  );
  if (repoResult.rows.length === 0) {
    throw new Error('Repository not found');
  }
  const repo = repoResult.rows[0];

  // 2. Get user's GitHub token
  const userResult = await query('SELECT github_access_token FROM users WHERE id = $1', [userId]);
  const accessToken = decrypt(userResult.rows[0].github_access_token);

  // 3. Get latest commit if not provided
  let commitSha = providedSha;
  let commitMessage = '';
  let authorName = '';
  const targetBranch = branch || repo.default_branch;
  
  if (!commitSha) {
    const commit = await getLatestCommit(accessToken, repo.owner, repo.name, targetBranch);
    commitSha = commit.sha;
    commitMessage = commit.message;
    authorName = commit.authorName;
  }

  // 4. Create analysis run
  const runResult = await query(
    `INSERT INTO analysis_runs
       (repo_id, commit_sha, commit_message, branch, author_name, triggered_by,
        status, engines_requested, engines_completed)
     VALUES ($1,$2,$3,$4,$5,'api','queued',$6,'{}')
     RETURNING *`,
    [repoId, commitSha, commitMessage, targetBranch, authorName, ['infraq']]
  );
  const run = runResult.rows[0];

  // 5. Insert engine_results row for infraq
  await query(
    `INSERT INTO engine_results (run_id, engine, status) VALUES ($1,$2,'queued')`,
    [run.id, 'infraq']
  );

  // 6. Enqueue job
  const jobPayload = {
    runId: run.id,
    repoId: repo.id,
    userId: userId,
    repoFullName: repo.full_name,
    cloneUrl: repo.clone_url,
    commitSha,
    branch: targetBranch,
    githubToken: accessToken,
    webhookEventId: null,
  };

  await dispatchAllEngineJobs(jobPayload, ['infraq']);
  logger.info({ runId: run.id, userId, repoId }, 'Infrastructure analysis triggered');
  
  return run.id;
};

/**
 * Retrieves the aggregated results from infra_analyses and engine_results
 */
export const getInfrastructureAnalysis = async (runId, userId) => {
  // Ensure the run belongs to the user
  const authCheck = await query(
    `SELECT ar.id FROM analysis_runs ar
     JOIN repositories r ON ar.repo_id = r.id
     WHERE ar.id = $1 AND r.user_id = $2`,
    [runId, userId]
  );
  if (authCheck.rows.length === 0) throw new Error('Run not found');

  const engineResult = await query(
    `SELECT status, error_message FROM engine_results WHERE run_id = $1 AND engine = 'infraq'`,
    [runId]
  );
  
  const infraResult = await query(
    `SELECT 
        cloud_provider, 
        architecture_graph, 
        detected_services,
        k8s_resources,
        terraform_resources,
        recommendations,
        has_dockerfile,
        has_docker_compose,
        has_k8s_manifests,
        has_terraform,
        has_helm_charts,
        has_ci_config,
        has_pulumi,
        has_ansible
     FROM infra_analyses 
     WHERE run_id = $1`,
    [runId]
  );

  const status = engineResult.rows.length > 0 ? engineResult.rows[0].status : 'unknown';
  const progress = status === 'completed' ? 100 : (status === 'queued' ? 0 : 50);
  
  const infraData = infraResult.rows.length > 0 ? infraResult.rows[0] : null;

  return {
    status,
    progress,
    discovery: infraData ? {
      services: infraData.detected_services || [],
      cloudProvider: infraData.cloud_provider,
      has_dockerfile: infraData.has_dockerfile || false,
      has_docker_compose: infraData.has_docker_compose || false,
      has_k8s_manifests: infraData.has_k8s_manifests || false,
      has_terraform: infraData.has_terraform || false,
      has_helm_charts: infraData.has_helm_charts || false,
      has_ci_config: infraData.has_ci_config || false,
      has_pulumi: infraData.has_pulumi || false,
      has_ansible: infraData.has_ansible || false,
    } : null,
    architecture: infraData ? infraData.architecture_graph : null,
    recommendations: infraData ? (infraData.recommendations || {}) : {},
    error: engineResult.rows.length > 0 ? engineResult.rows[0].error_message : null
  };
};

/**
 * Fetches findings specific to an analysis run
 */
export const getInfrastructureFindings = async (runId, userId) => {
  // Ensure the run belongs to the user
  const authCheck = await query(
    `SELECT ar.id FROM analysis_runs ar
     JOIN repositories r ON ar.repo_id = r.id
     WHERE ar.id = $1 AND r.user_id = $2`,
    [runId, userId]
  );
  if (authCheck.rows.length === 0) throw new Error('Run not found');

  const result = await query(
    `SELECT id, category, severity, title, description, rule_id, file_path, line_number, evidence, recommendation
     FROM infrastructure_findings 
     WHERE analysis_run_id = $1
     ORDER BY severity DESC`,
    [runId]
  );
  
  return result.rows;
};
