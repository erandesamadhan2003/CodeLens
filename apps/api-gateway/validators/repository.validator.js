import { z } from 'zod';

export const connectRepoSchema = z.object({
  githubRepoId: z.string().min(1),
  owner: z.string().min(1),
  name: z.string().min(1),
  fullName: z.string().min(1),
  description: z.string().nullable().optional(),
  defaultBranch: z.string().default('main'),
  isPrivate: z.boolean().default(false),
  cloneUrl: z.string().url(),
  language: z.string().nullable().optional(),
});
