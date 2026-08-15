import crypto from 'crypto';
import { query } from '../config/database.js';
import { encrypt, decrypt } from '../utils/crypto.js';
import { sendSuccess, sendError, sendPaginated } from '../utils/response.js';
import asyncHandler from '../utils/asyncHandler.js';
import * as githubService from '../services/github.service.js';
import logger from '../utils/logger.js';

/**
 * GET /api/v1/repositories/github
 * List all repositories for the authenticated user from GitHub.
 */
export const getGitHubRepositories = asyncHandler(async (req, res) => {
  const userResult = await query('SELECT github_access_token FROM users WHERE id = $1', [req.user.id]);
  const accessToken = decrypt(userResult.rows[0].github_access_token);
  const repos = await githubService.getUserRepos(accessToken, 1, 100);
  return sendSuccess(res, repos, 'GitHub repositories retrieved');
});

/**
 * GET /api/v1/repositories
 * List all repositories for the current user.
 */
export const listRepositories = asyncHandler(async (req, res) => {
  const result = await query(
    `SELECT id, github_repo_id, owner, name, full_name, description, default_branch,
            is_private, clone_url, language, webhook_active, last_analyzed_at,
            last_commit_sha, is_active, created_at, updated_at
     FROM repositories
     WHERE user_id = $1 AND is_active = true
     ORDER BY updated_at DESC`,
    [req.user.id]
  );
  return sendSuccess(res, result.rows, 'Repositories retrieved');
});

/**
 * POST /api/v1/repositories
 * Connect a new repository and register a GitHub webhook.
 */
export const connectRepository = asyncHandler(async (req, res) => {
  const {
    githubRepoId, owner, name, fullName, description,
    defaultBranch, isPrivate, cloneUrl, language,
  } = req.body;

  // Get user's decrypted GitHub token
  const userResult = await query(
    'SELECT github_access_token FROM users WHERE id = $1',
    [req.user.id]
  );
  const accessToken = decrypt(userResult.rows[0].github_access_token);

  // Generate webhook secret
  const webhookSecret = crypto.randomBytes(32).toString('hex');
  const webhookUrl = `${process.env.GITHUB_WEBHOOK_BASE_URL}/api/v1/webhooks/github`;

  // Insert repository first to get the ID
  const repoResult = await query(
    `INSERT INTO repositories
       (user_id, github_repo_id, owner, name, full_name, description,
        default_branch, is_private, clone_url, language, webhook_secret)
     VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
     RETURNING id`,
    [
      req.user.id, githubRepoId, owner, name, fullName, description || null,
      defaultBranch || 'main', isPrivate || false, cloneUrl,
      language || null, encrypt(webhookSecret),
    ]
  );

  const repoId = repoResult.rows[0].id;

  // Register GitHub webhook using repo ID in the URL
  let webhookData;
  let webhookFailed = false;
  try {
    webhookData = await githubService.createWebhook(
      accessToken, owner, name,
      `${webhookUrl}/${repoId}`,
      webhookSecret
    );
  } catch (err) {
    logger.warn({ err: err.message, repoId }, 'Failed to create GitHub webhook. Repository will be connected without automatic webhooks.');
    webhookFailed = true;
  }

  if (!webhookFailed && webhookData) {
    // Update repo with webhook info
    await query(
      `UPDATE repositories
       SET webhook_id = $1, webhook_active = true
       WHERE id = $2`,
      [String(webhookData.id), repoId]
    );
  }

  const finalRepo = await query(
    `SELECT id, github_repo_id, owner, name, full_name, description, default_branch,
            is_private, clone_url, language, webhook_active, last_analyzed_at,
            last_commit_sha, is_active, created_at, updated_at
     FROM repositories WHERE id = $1`,
    [repoId]
  );

  logger.info({ repoId, userId: req.user.id, fullName, webhookFailed }, 'Repository connected');
  return sendSuccess(
    res, 
    finalRepo.rows[0], 
    webhookFailed ? 'Repository connected (Webhook failed, requires manual setup or admin permissions)' : 'Repository connected successfully', 
    201
  );
});

/**
 * GET /api/v1/repositories/:repoId
 * Get a single repository.
 */
export const getRepository = asyncHandler(async (req, res) => {
  const { repoId } = req.params;
  const result = await query(
    `SELECT id, github_repo_id, owner, name, full_name, description, default_branch,
            is_private, clone_url, language, webhook_active, last_analyzed_at,
            last_commit_sha, is_active, created_at, updated_at
     FROM repositories WHERE id = $1 AND user_id = $2`,
    [repoId, req.user.id]
  );
  if (result.rows.length === 0) return sendError(res, 'Repository not found', null, 404);
  return sendSuccess(res, result.rows[0], 'Repository retrieved');
});

/**
 * DELETE /api/v1/repositories/:repoId
 * Disconnect a repository — delete webhook and deactivate.
 */
export const deleteRepository = asyncHandler(async (req, res) => {
  const { repoId } = req.params;

  const result = await query(
    'SELECT * FROM repositories WHERE id = $1 AND user_id = $2',
    [repoId, req.user.id]
  );
  if (result.rows.length === 0) return sendError(res, 'Repository not found', null, 404);

  const repo = result.rows[0];

  if (repo.webhook_id) {
    try {
      const userResult = await query('SELECT github_access_token FROM users WHERE id = $1', [req.user.id]);
      const accessToken = decrypt(userResult.rows[0].github_access_token);
      await githubService.deleteWebhook(accessToken, repo.owner, repo.name, repo.webhook_id);
    } catch (err) {
      logger.warn({ err, repoId }, 'Failed to delete GitHub webhook (continuing)');
    }
  }

  await query('UPDATE repositories SET is_active = false, webhook_active = false WHERE id = $1', [repoId]);
  logger.info({ repoId, userId: req.user.id }, 'Repository disconnected');
  return sendSuccess(res, null, 'Repository disconnected');
});

/**
 * POST /api/v1/repositories/:repoId/sync
 * Re-sync repository metadata from GitHub.
 */
export const syncRepository = asyncHandler(async (req, res) => {
  const { repoId } = req.params;
  const repoResult = await query('SELECT * FROM repositories WHERE id = $1 AND user_id = $2', [repoId, req.user.id]);
  if (repoResult.rows.length === 0) return sendError(res, 'Repository not found', null, 404);

  const repo = repoResult.rows[0];
  const userResult = await query('SELECT github_access_token FROM users WHERE id = $1', [req.user.id]);
  const accessToken = decrypt(userResult.rows[0].github_access_token);

  const ghRepo = await githubService.getRepo(accessToken, repo.owner, repo.name);

  await query(
    `UPDATE repositories SET
       description = $1, default_branch = $2, is_private = $3, language = $4, updated_at = NOW()
     WHERE id = $5`,
    [ghRepo.description, ghRepo.default_branch, ghRepo.private, ghRepo.language, repoId]
  );

  const updated = await query('SELECT id, github_repo_id, owner, name, full_name, description, default_branch, is_private, clone_url, language, webhook_active, last_analyzed_at, last_commit_sha, is_active, created_at, updated_at FROM repositories WHERE id = $1', [repoId]);
  return sendSuccess(res, updated.rows[0], 'Repository synced');
});

/**
 * POST /api/v1/repositories/:repoId/webhook/activate
 * Register a GitHub webhook for the repository.
 */
export const activateWebhook = asyncHandler(async (req, res) => {
  const { repoId } = req.params;
  const repoResult = await query('SELECT * FROM repositories WHERE id = $1 AND user_id = $2', [repoId, req.user.id]);
  if (repoResult.rows.length === 0) return sendError(res, 'Repository not found', null, 404);

  const repo = repoResult.rows[0];
  const userResult = await query('SELECT github_access_token FROM users WHERE id = $1', [req.user.id]);
  const accessToken = decrypt(userResult.rows[0].github_access_token);

  const webhookSecret = crypto.randomBytes(32).toString('hex');
  const webhookUrl = `${process.env.GITHUB_WEBHOOK_BASE_URL}/api/v1/webhooks/github/${repoId}`;

  const webhookData = await githubService.createWebhook(accessToken, repo.owner, repo.name, webhookUrl, webhookSecret);
  await query(
    'UPDATE repositories SET webhook_id = $1, webhook_secret = $2, webhook_active = true, updated_at = NOW() WHERE id = $3',
    [String(webhookData.id), encrypt(webhookSecret), repoId]
  );

  return sendSuccess(res, { webhookId: webhookData.id }, 'Webhook activated');
});

/**
 * DELETE /api/v1/repositories/:repoId/webhook/deactivate
 * Remove the GitHub webhook from a repository.
 */
export const deactivateWebhook = asyncHandler(async (req, res) => {
  const { repoId } = req.params;
  const repoResult = await query('SELECT * FROM repositories WHERE id = $1 AND user_id = $2', [repoId, req.user.id]);
  if (repoResult.rows.length === 0) return sendError(res, 'Repository not found', null, 404);

  const repo = repoResult.rows[0];
  if (!repo.webhook_id) return sendError(res, 'No active webhook found', null, 400);

  const userResult = await query('SELECT github_access_token FROM users WHERE id = $1', [req.user.id]);
  const accessToken = decrypt(userResult.rows[0].github_access_token);

  await githubService.deleteWebhook(accessToken, repo.owner, repo.name, repo.webhook_id);
  await query('UPDATE repositories SET webhook_id = NULL, webhook_active = false, updated_at = NOW() WHERE id = $1', [repoId]);

  return sendSuccess(res, null, 'Webhook deactivated');
});
