import crypto from 'crypto';
import { query } from '../config/database.js';
import { sendError } from '../utils/response.js';
import logger from '../utils/logger.js';

const hashApiKey = (key) => {
  return crypto.createHash('sha256').update(key).digest('hex');
};

const apiKeyMiddleware = async (req, res, next) => {
  try {
    const apiKeyHeader = req.headers['x-api-key'] || req.headers.authorization;
    if (!apiKeyHeader) {
      return sendError(res, 'API Key missing', null, 401);
    }

    let apiKey = apiKeyHeader;
    if (apiKeyHeader.startsWith('Bearer ')) {
      apiKey = apiKeyHeader.split(' ')[1];
    }

    const keyHash = hashApiKey(apiKey);

    const result = await query(
      `SELECT u.id, u.github_id, u.username, u.email, u.avatar_url, u.plan, u.created_at, a.id as api_key_id
       FROM users u
       JOIN api_keys a ON u.id = a.user_id
       WHERE a.key_hash = $1 AND a.revoked_at IS NULL AND (a.expires_at IS NULL OR a.expires_at > NOW())`,
      [keyHash]
    );

    if (result.rows.length === 0) {
      return sendError(res, 'Invalid or revoked API Key', null, 401);
    }

    req.user = result.rows[0];
    const apiKeyId = result.rows[0].api_key_id;

    // Update last_used_at asynchronously
    query(`UPDATE api_keys SET last_used_at = NOW() WHERE id = $1`, [apiKeyId]).catch(err => {
      logger.error({ err: err.message, apiKeyId }, 'Failed to update last_used_at for API key');
    });

    logger.debug({ userId: req.user.id, apiKeyId }, 'API Key middleware: user attached');
    next();
  } catch (err) {
    next(err);
  }
};

export default apiKeyMiddleware;
