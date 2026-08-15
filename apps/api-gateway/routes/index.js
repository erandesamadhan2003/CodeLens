import { Router, raw } from 'express';
import authRoutes        from './auth.routes.js';
import repositoryRoutes  from './repository.routes.js';
import runRoutes         from './run.routes.js';
import resultRoutes      from './result.routes.js';
import notificationRoutes from './notification.routes.js';
import webhookSignatureMiddleware from '../middlewares/webhookSignature.middleware.js';
import { webhookRateLimit } from '../middlewares/rateLimit.middleware.js';
import { handleGitHubWebhook } from '../controllers/webhook.controller.js';

const router = Router();

// ── API Routes ────────────────────────────────────────────────────────────
router.use('/auth',          authRoutes);
router.use('/repositories',  repositoryRoutes);
router.use('/runs',          runRoutes);
router.use('/results',       resultRoutes);
router.use('/notifications', notificationRoutes);

// ── Webhook (PUBLIC — raw body, HMAC verified, rate limited) ──────────────
router.post(
  '/webhooks/github/:repoId',
  webhookRateLimit,
  raw({ type: 'application/json' }),
  (req, _res, next) => {
    // Preserve raw body for HMAC verification
    req.rawBody = req.body;
    next();
  },
  webhookSignatureMiddleware,
  handleGitHubWebhook
);

export default router;
