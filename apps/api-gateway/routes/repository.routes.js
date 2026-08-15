import { Router } from 'express';
import {
  listRepositories,
  connectRepository,
  getRepository,
  deleteRepository,
  syncRepository,
  activateWebhook,
  deactivateWebhook,
} from '../controllers/repository.controller.js';
import authMiddleware from '../middlewares/auth.middleware.js';
import { generalRateLimit } from '../middlewares/rateLimit.middleware.js';
import validate from '../middlewares/validate.middleware.js';
import { connectRepoSchema } from '../validators/repository.validator.js';

const router = Router();

router.use(authMiddleware, generalRateLimit);

router.get('/',         listRepositories);
router.post('/',        validate(connectRepoSchema), connectRepository);
router.get('/:repoId',  getRepository);
router.delete('/:repoId', deleteRepository);
router.post('/:repoId/sync', syncRepository);
router.post('/:repoId/webhook/activate', activateWebhook);
router.delete('/:repoId/webhook/deactivate', deactivateWebhook);

export default router;
