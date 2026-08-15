import { Router } from 'express';
import { listRuns, getRun, triggerRun, cancelRun } from '../controllers/run.controller.js';
import multiAuthMiddleware from '../middlewares/multiAuth.middleware.js';
import { generalRateLimit } from '../middlewares/rateLimit.middleware.js';
import validate from '../middlewares/validate.middleware.js';
import { triggerRunSchema } from '../validators/run.validator.js';

const router = Router();

router.use(multiAuthMiddleware, generalRateLimit);

router.get('/',         listRuns);
router.get('/:runId',   getRun);
router.post('/',        validate(triggerRunSchema), triggerRun);
router.post('/:runId/cancel', cancelRun);

export default router;
