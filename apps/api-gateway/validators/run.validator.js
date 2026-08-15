import { z } from 'zod';

const ENGINE_NAMES = ['infraq', 'infilra', 'depra', 'devora', 'docryx'];

export const triggerRunSchema = z.object({
  repoId: z.string().uuid(),
  commitSha: z.string().optional(),
  engines: z
    .array(z.enum(ENGINE_NAMES))
    .default(['infraq', 'infilra', 'depra', 'devora', 'docryx']),
});
