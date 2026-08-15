import { query } from '../config/database.js';
import { decrypt } from '../utils/crypto.js';
import { verifyWebhookSignature } from '../utils/github.utils.js';
import { sendError } from '../utils/response.js';
import logger from '../utils/logger.js';

/**
 * Middleware that:
 * 1. Looks up the repository's webhook_secret from the DB (by :repoId param)
 * 2. Decrypts the secret
 * 3. Verifies the HMAC-SHA256 signature against req.rawBody
 */
const webhookSignatureMiddleware = async (req, res, next) => {
  try {
    const { repoId } = req.params;
    const signature = req.headers['x-hub-signature-256'];

    if (!signature) {
      logger.warn({ reqId: req.id, repoId }, 'Webhook missing signature header');
      return sendError(res, 'Missing webhook signature', null, 401);
    }

    // Fetch the encrypted webhook secret for this repo
    const result = await query(
      'SELECT webhook_secret FROM repositories WHERE id = $1 AND is_active = true',
      [repoId]
    );

    if (result.rows.length === 0) {
      return sendError(res, 'Repository not found', null, 404);
    }

    const encryptedSecret = result.rows[0].webhook_secret;
    const secret = decrypt(encryptedSecret);

    const valid = verifyWebhookSignature(req.rawBody, secret, signature);
    if (!valid) {
      logger.warn({ reqId: req.id, repoId }, 'Invalid webhook signature');
      return sendError(res, 'Invalid webhook signature', null, 401);
    }

    next();
  } catch (err) {
    next(err);
  }
};

export default webhookSignatureMiddleware;
