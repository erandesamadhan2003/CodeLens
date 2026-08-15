import request from 'supertest';
import { jest } from '@jest/globals';
import express from 'express';
import { v4 as uuidv4 } from 'uuid';

// Mock dependencies before importing routes
jest.unstable_mockModule('../middlewares/auth.middleware.js', () => ({
  requireAuth: (req, res, next) => {
    req.user = { id: 'test-user-id' };
    next();
  }
}));

jest.unstable_mockModule('../services/infrastructure.service.js', () => ({
  triggerInfrastructureAnalysis: jest.fn(),
  getInfrastructureAnalysis: jest.fn(),
  getInfrastructureFindings: jest.fn()
}));

// Import dynamically to ensure mocks are applied
const { requireAuth } = await import('../middlewares/auth.middleware.js');
const infraService = await import('../services/infrastructure.service.js');
const infrastructureRoutes = (await import('../routes/infrastructure.routes.js')).default;
const errorMiddleware = (await import('../middlewares/error.middleware.js')).default;

const app = express();
app.use(express.json());
app.use('/api/v1/infrastructure', infrastructureRoutes);
app.use(errorMiddleware);

describe('Infrastructure Routes', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('POST /api/v1/infrastructure/analyze', () => {
    it('should validate the request and trigger analysis', async () => {
      infraService.triggerInfrastructureAnalysis.mockResolvedValue('mocked-run-id');

      const repoId = uuidv4();
      const response = await request(app)
        .post('/api/v1/infrastructure/analyze')
        .send({
          repositoryId: repoId,
          commitSha: 'abcdef123',
          branch: 'main'
        });

      expect(response.status).toBe(201);
      expect(response.body.data.runId).toBe('mocked-run-id');
      expect(response.body.data.status).toBe('QUEUED');
      expect(infraService.triggerInfrastructureAnalysis).toHaveBeenCalledWith(
        'test-user-id',
        repoId,
        'abcdef123',
        'main'
      );
    });

    it('should return 422 for invalid validation', async () => {
      const response = await request(app)
        .post('/api/v1/infrastructure/analyze')
        .send({
          repositoryId: 'not-a-uuid'
        });

      expect(response.status).toBe(422);
      expect(response.body.message).toBe('Validation failed');
      expect(response.body.errors[0].message).toContain('Invalid repositoryId format');
    });

    it('should return 404 if repository is not found', async () => {
      infraService.triggerInfrastructureAnalysis.mockRejectedValue(new Error('Repository not found'));
      
      const repoId = uuidv4();
      const response = await request(app)
        .post('/api/v1/infrastructure/analyze')
        .send({ repositoryId: repoId });

      expect(response.status).toBe(404);
      expect(response.body.message).toBe('Repository not found or access denied');
    });
  });

  describe('GET /api/v1/infrastructure/analyses/:runId', () => {
    it('should fetch analysis details', async () => {
      infraService.getInfrastructureAnalysis.mockResolvedValue({
        status: 'completed',
        progress: 100,
        architecture: {},
        findings: []
      });

      const response = await request(app).get('/api/v1/infrastructure/analyses/1234');
      
      expect(response.status).toBe(200);
      expect(response.body.data.status).toBe('completed');
      expect(infraService.getInfrastructureAnalysis).toHaveBeenCalledWith('1234', 'test-user-id');
    });
  });
});
