import { Router } from 'express';
import { redirectToGitHub, handleGitHubCallback, getMe, logout } from '../controllers/auth.controller.js';
import { createApiKey, listApiKeys, revokeApiKey } from '../controllers/apiKey.controller.js';
import authMiddleware from '../middlewares/auth.middleware.js';
import { authRateLimit } from '../middlewares/rateLimit.middleware.js';

const router = Router();

router.get('/github', authRateLimit, redirectToGitHub);
router.get('/github/callback', authRateLimit, handleGitHubCallback);
router.get('/me', authMiddleware, getMe);
router.post('/logout', authMiddleware, logout);

// API Key management
router.post('/api-keys', authMiddleware, createApiKey);
router.get('/api-keys', authMiddleware, listApiKeys);
router.delete('/api-keys/:id', authMiddleware, revokeApiKey);

export default router;
