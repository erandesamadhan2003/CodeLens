import { Router } from 'express';
import { getRunResults, getEngineResult } from '../controllers/result.controller.js';
import authMiddleware from '../middlewares/auth.middleware.js';
import { generalRateLimit } from '../middlewares/rateLimit.middleware.js';

const router = Router();

router.use(authMiddleware, generalRateLimit);

router.get('/run/:runId',          getRunResults);
router.get('/run/:runId/:engine',  getEngineResult);

export default router;
