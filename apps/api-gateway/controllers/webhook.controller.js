import { query } from '../config/database.js';
import { decrypt } from '../utils/crypto.js';
import {
  collectChangedFiles,
  compareCommits,
  mapCompareFilesToDiffs,
} from '../services/github.service.js';
import {
  dispatchAllEngineJobs,
  dispatchDependencyEngineJob,
  dispatchDocumentationEngineJob,
} from '../services/queue.service.js';
import {
  touchesDependencyManifest,
  touchesRouteFiles,
} from '../utils/webhookFilePatterns.js';
import { sendSuccess, sendError } from '../utils/response.js';
import asyncHandler from '../utils/asyncHandler.js';
import logger from '../utils/logger.js';

const BASE_ENGINES = ['infraq', 'infilra', 'devora'];

/**
 * POST /api/v1/webhooks/github/:repoId
 *
 * Receives raw GitHub webhook payload, verifies HMAC (via middleware),
 * processes push events, creates analysis runs, dispatches BullMQ jobs.
 */
export const handleGitHubWebhook = asyncHandler(async (req, res) => {
  const { repoId } = req.params;
  const eventType  = req.headers['x-github-event'];
  const deliveryId = req.headers['x-github-delivery'];

  // Only process push events
  if (eventType !== 'push') {
    return res.status(200).json({ received: true, skipped: true, reason: 'non-push event' });
  }

  // Parse the raw body
  const payload = JSON.parse(req.rawBody.toString('utf8'));

  // Check idempotency
  const existing = await query(
    'SELECT id FROM webhook_events WHERE delivery_id = $1',
    [deliveryId]
  );
  if (existing.rows.length > 0) {
    logger.info({ deliveryId }, 'Webhook already processed (idempotency)');
    return res.status(200).json({ received: true, skipped: true, reason: 'already processed' });
  }

  // Extract push data
  const commitSha     = payload.head_commit?.id || payload.after;
  const rawRef        = payload.ref || '';
  const branch        = rawRef.replace('refs/heads/', '');
  const pusherEmail   = payload.pusher?.email || null;
  const commitMessage = payload.head_commit?.message || '';
  const authorName    = payload.head_commit?.author?.name || '';

  // Fetch repo to get user_id
  const repoResult = await query(
    'SELECT id, user_id, clone_url, full_name FROM repositories WHERE id = $1 AND is_active = true',
    [repoId]
  );
  if (repoResult.rows.length === 0) {
    return sendError(res, 'Repository not found', null, 404);
  }
  const repo = repoResult.rows[0];

  // Get user's GitHub token
  const userResult = await query('SELECT github_access_token FROM users WHERE id = $1', [repo.user_id]);
  const githubToken = decrypt(userResult.rows[0].github_access_token);

  const changedFiles = collectChangedFiles(payload.commits || []);
  const shouldDepra = touchesDependencyManifest(changedFiles);
  const shouldDocryx = touchesRouteFiles(changedFiles);

  const enginesToRun = [...BASE_ENGINES];
  if (shouldDepra) enginesToRun.push('depra');
  if (shouldDocryx) enginesToRun.push('docryx');

  // Insert webhook_event
  const webhookEventResult = await query(
    `INSERT INTO webhook_events
       (repo_id, github_repo_id, event_type, delivery_id, commit_sha, branch,
        pusher_email, payload, status)
     VALUES ($1,$2,$3,$4,$5,$6,$7,$8,'received')
     RETURNING id`,
    [repoId, payload.repository?.id?.toString(), eventType, deliveryId,
     commitSha, branch, pusherEmail, payload]
  );
  const webhookEventId = webhookEventResult.rows[0].id;

  // Update status to processing
  await query('UPDATE webhook_events SET status = $1 WHERE id = $2', ['processing', webhookEventId]);

  // Insert analysis run
  const runResult = await query(
    `INSERT INTO analysis_runs
       (repo_id, webhook_event_id, commit_sha, commit_message, branch,
        author_name, author_email, triggered_by, status, engines_requested, engines_completed)
     VALUES ($1,$2,$3,$4,$5,$6,$7,'webhook','queued',$8,'{}')
     RETURNING *`,
    [repoId, webhookEventId, commitSha, commitMessage, branch,
     authorName, pusherEmail, enginesToRun]
  );
  const run = runResult.rows[0];

  // Insert engine_results rows only for engines we will dispatch
  for (const engine of enginesToRun) {
    await query(
      `INSERT INTO engine_results (run_id, engine, status) VALUES ($1,$2,'queued')`,
      [run.id, engine]
    );
  }

  // Link run back to webhook event
  await query('UPDATE webhook_events SET run_id = $1 WHERE id = $2', [run.id, webhookEventId]);

  let diffs = [];

  const [owner, repoName] = (repo.full_name || '').split('/');
  if (owner && repoName && payload.before && payload.after) {
    try {
      const compareData = await compareCommits(
        githubToken, owner, repoName, payload.before, payload.after,
      );
      diffs = mapCompareFilesToDiffs(compareData.files || []);
    } catch (err) {
      logger.warn(
        { err: err.message, runId: run.id, repo: repo.full_name },
        'GitHub compare API failed — continuing with empty diffs',
      );
    }
  }

  const jobPayload = {
    runId: run.id,
    repoId: repo.id,
    userId: repo.user_id,
    repoFullName: repo.full_name,
    cloneUrl: repo.clone_url,
    commitSha,
    branch,
    githubToken,
    webhookEventId,
  };

  await dispatchAllEngineJobs(jobPayload, BASE_ENGINES);

  if (shouldDepra) {
    await dispatchDependencyEngineJob({
      repoUrl: repo.clone_url,
      scanId: run.id,
      triggeredBy: 'webhook',
    });
  }

  if (shouldDocryx) {
    await dispatchDocumentationEngineJob({
      repoUrl: repo.clone_url,
      scanId: run.id,
      triggeredBy: 'webhook',
      changedFiles,
      commitSha,
      diffs,
      repoFullName: repo.full_name,
      githubToken,
    });
  }

  // Mark webhook as processed
  await query(
    'UPDATE webhook_events SET status = $1, processed_at = NOW() WHERE id = $2',
    ['processed', webhookEventId]
  );

  logger.info({
    runId: run.id,
    repoId,
    branch,
    commitSha,
    shouldDepra,
    shouldDocryx,
    enginesToRun,
  }, 'Webhook processed, run dispatched');
  return res.status(200).json({ received: true, runId: run.id });
});
