import { query } from '../config/database.js';
import { sendSuccess, sendError } from '../utils/response.js';
import asyncHandler from '../utils/asyncHandler.js';

/**
 * GET /api/v1/results/run/:runId
 * Get all engine results for a run.
 */
export const getRunResults = asyncHandler(async (req, res) => {
  const { runId } = req.params;

  // Verify run belongs to user
  const runCheck = await query(
    `SELECT ar.id FROM analysis_runs ar
     JOIN repositories r ON ar.repo_id = r.id
     WHERE ar.id = $1 AND r.user_id = $2`,
    [runId, req.user.id]
  );
  if (runCheck.rows.length === 0) return sendError(res, 'Run not found', null, 404);

  const result = await query(
    `SELECT id, run_id, engine, status, result_data, error_message,
            duration_ms, ai_tokens_used, started_at, completed_at
     FROM engine_results
     WHERE run_id = $1
     ORDER BY engine`,
    [runId]
  );

  return sendSuccess(res, result.rows, 'Engine results retrieved');
});

/**
 * GET /api/v1/results/run/:runId/:engine
 * Get a single engine's result for a run.
 */
export const getEngineResult = asyncHandler(async (req, res) => {
  const { runId, engine } = req.params;

  const runCheck = await query(
    `SELECT ar.id FROM analysis_runs ar
     JOIN repositories r ON ar.repo_id = r.id
     WHERE ar.id = $1 AND r.user_id = $2`,
    [runId, req.user.id]
  );
  if (runCheck.rows.length === 0) return sendError(res, 'Run not found', null, 404);

  const result = await query(
    `SELECT id, run_id, engine, status, result_data, error_message,
            duration_ms, ai_tokens_used, started_at, completed_at
     FROM engine_results
     WHERE run_id = $1 AND engine = $2`,
    [runId, engine]
  );

  if (result.rows.length === 0) return sendError(res, 'Engine result not found', null, 404);
  return sendSuccess(res, result.rows[0], 'Engine result retrieved');
});
