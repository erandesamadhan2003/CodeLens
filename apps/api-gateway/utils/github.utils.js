import crypto from 'crypto';

/**
 * Verifies GitHub's HMAC-SHA256 webhook signature.
 * Uses timingSafeEqual to prevent timing attacks.
 *
 * @param {Buffer} rawBody  - The raw request body as a Buffer
 * @param {string} secret   - The webhook secret stored in the DB
 * @param {string} signature - The value of X-Hub-Signature-256 header
 * @returns {boolean}
 */
export function verifyWebhookSignature(rawBody, secret, signature) {
  if (!signature || !secret) return false;

  const hmac = crypto.createHmac('sha256', secret);
  hmac.update(rawBody);
  const digest = `sha256=${hmac.digest('hex')}`;

  // Both buffers must be the same length for timingSafeEqual
  if (digest.length !== signature.length) return false;

  return crypto.timingSafeEqual(
    Buffer.from(digest, 'utf8'),
    Buffer.from(signature, 'utf8')
  );
}
