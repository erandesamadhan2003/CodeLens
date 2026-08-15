import rateLimit from 'express-rate-limit';
import { sendError } from '../utils/response.js';

const handler = (_req, res) => {
  sendError(res, 'Too many requests, please try again later', null, 429);
};

/** Auth routes: 10 requests per 15 minutes per IP */
export const authRateLimit = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 10,
  standardHeaders: true,
  legacyHeaders: false,
  handler,
});

/** Webhook route: 100 requests per minute per IP */
export const webhookRateLimit = rateLimit({
  windowMs: 60 * 1000,
  max: 100,
  standardHeaders: true,
  legacyHeaders: false,
  handler,
});

/** General API routes: 100 per 15 minutes */
export const generalRateLimit = rateLimit({
  windowMs: parseInt(process.env.RATE_LIMIT_WINDOW_MS || '900000', 10),
  max: parseInt(process.env.RATE_LIMIT_MAX || '100', 10),
  standardHeaders: true,
  legacyHeaders: false,
  handler,
  keyGenerator: (req) => req.user?.id || req.ip,
});
