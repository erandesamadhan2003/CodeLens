import { Router } from 'express';
import authMiddleware from '../middlewares/auth.middleware.js';
import validateRequest from '../middlewares/validate.middleware.js';
import { analyzeRequestSchema } from '../validators/infrastructure.validator.js';
import { sendSuccess, sendError } from '../utils/response.js';
import asyncHandler from '../utils/asyncHandler.js';
import { 
  triggerInfrastructureAnalysis, 
  getInfrastructureAnalysis, 
  getInfrastructureFindings 
} from '../services/infrastructure.service.js';

const router = Router();

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

export default router;
