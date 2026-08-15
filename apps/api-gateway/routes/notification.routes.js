import { Router } from 'express';
import { getNotifications, markRead, markAllRead } from '../controllers/notification.controller.js';
import authMiddleware from '../middlewares/auth.middleware.js';
import { generalRateLimit } from '../middlewares/rateLimit.middleware.js';

const router = Router();

router.use(authMiddleware, generalRateLimit);

router.get('/',                    getNotifications);
router.put('/read-all',            markAllRead);
router.put('/:notifId/read',       markRead);

export default router;
