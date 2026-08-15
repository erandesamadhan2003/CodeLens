import { Router } from 'express';
import authMiddleware from '../middlewares/auth.middleware.js';
import validateRequest from '../middlewares/validate.middleware.js';
import { analyzeRequestSchema } from '../validators/infrastructure.validator.js';
import { sendSuccess, sendError } from '../utils/response.js';
import asyncHandler from '../utils/asyncHandler.js';
import { query } from '../config/database.js';
import { decrypt } from '../utils/crypto.js';
import axios from 'axios';
import {
  triggerInfrastructureAnalysis,
  getInfrastructureAnalysis,
  getInfrastructureFindings
} from '../services/infrastructure.service.js';

const router = Router();
const INFRA_ENGINE_URL = process.env.INFRA_ENGINE_URL || 'http://infrastructure-engine:8000';

// Protect all infrastructure routes
router.use(authMiddleware);

/**
 * POST /api/v1/infrastructure/analyze
 */
router.post('/analyze', validateRequest(analyzeRequestSchema), asyncHandler(async (req, res) => {
  const { repositoryId, commitSha, branch } = req.body;
  try {
    const runId = await triggerInfrastructureAnalysis(req.user.id, repositoryId, commitSha, branch);
    return sendSuccess(res, { runId, status: 'QUEUED' }, 'Infrastructure analysis triggered', 201);
  } catch (error) {
    if (error.message === 'Repository not found') {
      return sendError(res, 'Repository not found or access denied', null, 404);
    }
    throw error;
  }
}));

/**
 * GET /api/v1/infrastructure/analyses/:runId
 */
router.get('/analyses/:runId', asyncHandler(async (req, res) => {
  const { runId } = req.params;
  try {
    const data = await getInfrastructureAnalysis(runId, req.user.id);
    return sendSuccess(res, data, 'Analysis retrieved successfully');
  } catch (error) {
    if (error.message === 'Run not found') {
      return sendError(res, 'Run not found or access denied', null, 404);
    }
    throw error;
  }
}));

/**
 * GET /api/v1/infrastructure/analyses/:runId/findings
 */
router.get('/analyses/:runId/findings', asyncHandler(async (req, res) => {
  const { runId } = req.params;
  try {
    const data = await getInfrastructureFindings(runId, req.user.id);
    return sendSuccess(res, data, 'Findings retrieved successfully');
  } catch (error) {
    if (error.message === 'Run not found') {
      return sendError(res, 'Run not found or access denied', null, 404);
    }
    throw error;
  }
}));

/**
 * GET /api/v1/infrastructure/analyses/:runId/recommendations
 */
router.get('/analyses/:runId/recommendations', asyncHandler(async (req, res) => {
  const { runId } = req.params;
  try {
    const data = await getInfrastructureAnalysis(runId, req.user.id);
    return sendSuccess(res, data.recommendations, 'Recommendations retrieved successfully');
  } catch (error) {
    if (error.message === 'Run not found') {
      return sendError(res, 'Run not found or access denied', null, 404);
    }
    throw error;
  }
}));

/**
 * POST /api/v1/infrastructure/analyses/:runId/recommendations/:recId/apply
 * Applies a recommendation's file changes as a GitHub PR.
 */
router.post('/analyses/:runId/recommendations/:recId/apply', asyncHandler(async (req, res) => {
  const { runId, recId } = req.params;

  // 1. Verify the run belongs to this user and get repo info
  const runResult = await query(
    `SELECT ar.id, ar.branch, r.full_name, r.default_branch
     FROM analysis_runs ar
     JOIN repositories r ON ar.repo_id = r.id
     WHERE ar.id = $1 AND r.user_id = $2`,
    [runId, req.user.id]
  );
  if (runResult.rows.length === 0) {
    return sendError(res, 'Run not found or access denied', null, 404);
  }

  const run = runResult.rows[0];

  // 2. Get the specific recommendation from infra_analyses
  const infraResult = await query(
    `SELECT recommendations FROM infra_analyses WHERE run_id = $1`,
    [runId]
  );
  if (infraResult.rows.length === 0) {
    return sendError(res, 'Infrastructure analysis not found', null, 404);
  }

  const recommendationsData = infraResult.rows[0].recommendations;
  const allRecs = recommendationsData?.recommendations || [];
  const recommendation = allRecs.find(r => r.id === recId);

  if (!recommendation) {
    return sendError(res, `Recommendation ${recId} not found`, null, 404);
  }

  if (!recommendation.file_changes || recommendation.file_changes.length === 0) {
    return sendError(res, 'This recommendation has no file changes to apply', null, 400);
  }

  // 3. Get user's GitHub token
  const userResult = await query(
    'SELECT github_access_token FROM users WHERE id = $1',
    [req.user.id]
  );
  if (userResult.rows.length === 0) {
    return sendError(res, 'User not found', null, 404);
  }
  const githubToken = decrypt(userResult.rows[0].github_access_token);

  // 4. Call the infrastructure engine's /apply endpoint
  try {
    const engineResponse = await axios.post(`${INFRA_ENGINE_URL}/internal/apply`, {
      runId,
      recommendationId: recId,
      recommendationTitle: recommendation.title,
      fileChanges: recommendation.file_changes,
      githubToken,
      repoFullName: run.full_name,
      baseBranch: run.default_branch || run.branch || 'main',
    }, { timeout: 60000 });

    const { pr_url } = engineResponse.data;

    // 5. Mark this recommendation as applied in DB
    const updatedRecs = allRecs.map(r =>
      r.id === recId ? { ...r, applied: true, pr_url } : r
    );
    await query(
      `UPDATE infra_analyses SET recommendations = recommendations || $1::jsonb WHERE run_id = $2`,
      [JSON.stringify({ ...recommendationsData, recommendations: updatedRecs }), runId]
    );

    return sendSuccess(res, { pr_url }, 'Recommendation applied successfully. PR created!');
  } catch (err) {
    const message = err.response?.data?.detail || err.message || 'Failed to apply recommendation';
    return sendError(res, message, null, 500);
  }
}));

export default router;
