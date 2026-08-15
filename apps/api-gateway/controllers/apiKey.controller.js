import crypto from 'crypto';
import { query } from '../config/database.js';
import { sendSuccess, sendError } from '../utils/response.js';
import asyncHandler from '../utils/asyncHandler.js';
import logger from '../utils/logger.js';

/**
 * Helper to hash the API key using SHA-256 for secure storage.
 */
const hashApiKey = (key) => {
  return crypto.createHash('sha256').update(key).digest('hex');
};

/**
 * POST /api/v1/auth/api-keys
 * Generate a new API key for the authenticated user.
 */
export const createApiKey = asyncHandler(async (req, res) => {
  const { name } = req.body;
  if (!name) {
    return sendError(res, 'API key name is required', null, 400);
  }

  // Generate a random 32-byte hex string (64 characters)
  const rawKey = crypto.randomBytes(32).toString('hex');
  const keyPrefix = rawKey.substring(0, 8);
  const keyHash = hashApiKey(rawKey);

  const result = await query(
    `INSERT INTO api_keys (user_id, name, key_prefix, key_hash)
     VALUES ($1, $2, $3, $4)
     RETURNING id, name, key_prefix, created_at`,
    [req.user.id, name, keyPrefix, keyHash]
  );

  logger.info({ userId: req.user.id, keyId: result.rows[0].id }, 'API Key created');

  // We only return the raw key ONCE upon creation
  return sendSuccess(res, {
    ...result.rows[0],
    apiKey: rawKey
  }, 'API key generated successfully', 201);
});

/**
 * GET /api/v1/auth/api-keys
 * List all active API keys for the user.
 */
export const listApiKeys = asyncHandler(async (req, res) => {
  const result = await query(
    `SELECT id, name, key_prefix, last_used_at, created_at 
     FROM api_keys 
     WHERE user_id = $1 AND revoked_at IS NULL
     ORDER BY created_at DESC`,
    [req.user.id]
  );

  return sendSuccess(res, result.rows, 'API keys retrieved');
});

/**
 * DELETE /api/v1/auth/api-keys/:id
 * Revoke an API key.
 */
export const revokeApiKey = asyncHandler(async (req, res) => {
  const { id } = req.params;

  const result = await query(
    `UPDATE api_keys 
     SET revoked_at = NOW() 
     WHERE id = $1 AND user_id = $2 AND revoked_at IS NULL
     RETURNING id`,
    [id, req.user.id]
  );

  if (result.rowCount === 0) {
    return sendError(res, 'API key not found or already revoked', null, 404);
  }

  logger.info({ userId: req.user.id, keyId: id }, 'API Key revoked');
  return sendSuccess(res, null, 'API key revoked successfully');
});
