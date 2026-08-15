import { z } from 'zod';

export const analyzeRequestSchema = z.object({
  repositoryId: z.string().uuid('Invalid repositoryId format'),
  commitSha: z.string().optional(),
  branch: z.string().optional()
});
