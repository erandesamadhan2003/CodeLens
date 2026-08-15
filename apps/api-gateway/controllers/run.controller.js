import { query } from '../config/database.js';
import { decrypt } from '../utils/crypto.js';
import { sendSuccess, sendError, sendPaginated } from '../utils/response.js';
import asyncHandler from '../utils/asyncHandler.js';
import { dispatchAllEngineJobs } from '../services/queue.service.js';
import { getLatestCommit } from '../services/github.service.js';
import logger from '../utils/logger.js';

const ALL_ENGINES = ['infraq', 'infilra', 'depra', 'devora', 'docryx'];

/**
 * GET /api/v1/runs
 * List all runs for current user (paginated).
 */
export const listRuns = asyncHandler(async (req, res) => {
  const page  = parseInt(req.query.page  || '1', 10);
  const limit = parseInt(req.query.limit || '20', 10);
  const offset = (page - 1) * limit;

  const repoId = req.query.repoId;
  let countQuery = `
    SELECT COUNT(*) FROM analysis_runs ar
    JOIN repositories r ON ar.repo_id = r.id
    WHERE r.user_id = $1
  `;
  const countParams = [req.user.id];

  if (repoId) {
    countQuery += ` AND r.id = $2`;
    countParams.push(repoId);
  }

  const countResult = await query(countQuery, countParams);
  const total = parseInt(countResult.rows[0].count, 10);

  let fetchQuery = `
    SELECT ar.id, ar.repo_id, ar.commit_sha, ar.commit_message, ar.branch,
           ar.author_name, ar.triggered_by, ar.status, ar.engines_requested,
           ar.engines_completed, ar.started_at, ar.completed_at, ar.created_at,
           r.full_name AS repo_full_name
    FROM analysis_runs ar
    JOIN repositories r ON ar.repo_id = r.id
    WHERE r.user_id = $1
  `;
  const fetchParams = [req.user.id];

  if (repoId) {
    fetchQuery += ` AND r.id = $2`;
    fetchParams.push(repoId);
  }

  fetchQuery += ` ORDER BY ar.created_at DESC LIMIT $${fetchParams.length + 1} OFFSET $${fetchParams.length + 2}`;
  fetchParams.push(limit, offset);

  const result = await query(fetchQuery, fetchParams);

  return sendPaginated(res, result.rows, page, limit, total);
});

/**
 * GET /api/v1/runs/:runId
 * Get a single run with engine result statuses.
 */
export const getRun = asyncHandler(async (req, res) => {
  const { runId } = req.params;

  const runResult = await query(
    `SELECT ar.*, r.full_name AS repo_full_name
     FROM analysis_runs ar
     JOIN repositories r ON ar.repo_id = r.id
     WHERE ar.id = $1 AND r.user_id = $2`,
    [runId, req.user.id]
  );
  if (runResult.rows.length === 0) return sendError(res, 'Run not found', null, 404);

  const enginesResult = await query(
    `SELECT id, engine, status, duration_ms, ai_tokens_used, started_at, completed_at, error_message
     FROM engine_results WHERE run_id = $1`,
    [runId]
  );

  return sendSuccess(res, {
    ...runResult.rows[0],
    engineResults: enginesResult.rows,
  }, 'Run retrieved');
});

/**
 * POST /api/v1/runs
 * Trigger a manual analysis run.
 */
export const triggerRun = asyncHandler(async (req, res) => {
  const { repoId, commitSha: providedSha, engines = ALL_ENGINES } = req.body;

  // Verify repo belongs to user
  const repoResult = await query(
    'SELECT * FROM repositories WHERE id = $1 AND user_id = $2 AND is_active = true',
    [repoId, req.user.id]
  );
  if (repoResult.rows.length === 0) return sendError(res, 'Repository not found', null, 404);

  const repo = repoResult.rows[0];

  // Get user's GitHub token
  const userResult = await query('SELECT github_access_token FROM users WHERE id = $1', [req.user.id]);
  const accessToken = decrypt(userResult.rows[0].github_access_token);

  // Get latest commit if not provided
  let commitSha = providedSha;
  let commitMessage = '';
  let authorName = '';
  if (!commitSha) {
    const commit = await getLatestCommit(accessToken, repo.owner, repo.name, repo.default_branch);
    commitSha = commit.sha;
    commitMessage = commit.message;
    authorName = commit.authorName;
  }

  // Insert analysis run
  const runResult = await query(
    `INSERT INTO analysis_runs
       (repo_id, commit_sha, commit_message, branch, author_name, triggered_by,
        status, engines_requested, engines_completed)
     VALUES ($1,$2,$3,$4,$5,'manual','queued',$6,'{}')
     RETURNING *`,
    [repoId, commitSha, commitMessage, repo.default_branch, authorName, engines]
  );
  const run = runResult.rows[0];

  // Insert engine_results rows (one per engine)
  for (const engine of engines) {
    await query(
      `INSERT INTO engine_results (run_id, engine, status) VALUES ($1,$2,'queued')`,
      [run.id, engine]
    );
  }

  // Dispatch BullMQ jobs
  const jobPayload = {
    runId: run.id,
    repoId: repo.id,
    userId: req.user.id,
    repoFullName: repo.full_name,
    cloneUrl: repo.clone_url,
    commitSha,
    branch: repo.default_branch,
    githubToken: accessToken,
    webhookEventId: null,
  };

  await dispatchAllEngineJobs(jobPayload, engines);

  logger.info({ runId: run.id, userId: req.user.id, repoId }, 'Manual run triggered');
  return sendSuccess(res, run, 'Analysis run triggered', 201);
});

/**
 * POST /api/v1/runs/:runId/cancel
 * Cancel a queued run.
 */
export const cancelRun = asyncHandler(async (req, res) => {
  const { runId } = req.params;

  const result = await query(
    `SELECT ar.* FROM analysis_runs ar
     JOIN repositories r ON ar.repo_id = r.id
     WHERE ar.id = $1 AND r.user_id = $2`,
    [runId, req.user.id]
  );
  if (result.rows.length === 0) return sendError(res, 'Run not found', null, 404);
  if (result.rows[0].status !== 'queued') {
    return sendError(res, 'Only queued runs can be cancelled', null, 400);
  }

  await query(
    `UPDATE analysis_runs SET status = 'cancelled' WHERE id = $1`,
    [runId]
  );

  logger.info({ runId, userId: req.user.id }, 'Run cancelled');
  return sendSuccess(res, null, 'Run cancelled');
});
