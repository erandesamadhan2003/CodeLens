import { z } from 'zod';

export const loginSchema = z.object({
  code: z.string().min(1, 'GitHub OAuth code is required'),
});
