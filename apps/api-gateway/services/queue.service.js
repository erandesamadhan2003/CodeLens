import queues from '../config/queues.js';
import logger from '../utils/logger.js';

const ENGINE_QUEUE_MAP = {
  infraq:  'infraq',
  infilra: 'infilra',
  depra:   'depra',
  devora:  'devora',
  docryx:  'docryx',
};

/**
 * Dispatch a dependency-engine job (BullMQ worker queue).
 */
export async function dispatchDependencyEngineJob(payload) {
  const queue = queues.dependencyEngine;
  const job = await queue.add(
    `depra:run:${payload.scanId}`,
    payload,
    { jobId: `depra-${payload.scanId}` },
  );
  logger.info({ jobId: job.id, runId: payload.scanId }, 'Job dispatched to dependency-engine queue');
  return job;
}

/**
 * Dispatch a documentation-engine job (BullMQ worker queue) with optional webhook diff context.
 */
export async function dispatchDocumentationEngineJob(payload) {
  const queue = queues.documentationEngine;
  const job = await queue.add(
    `docryx:run:${payload.scanId}`,
    payload,
    { jobId: `docryx-${payload.scanId}` },
  );
  logger.info({ jobId: job.id, runId: payload.scanId }, 'Job dispatched to documentation-engine queue');
  return job;
}

/**
 * Dispatch a job for a single engine into its BullMQ queue.
 *
 * @param {string} engine  - One of: infraq, infilra, depra, devora, docryx
 * @param {object} payload - Standardised job payload
 */
export async function dispatchEngineJob(engine, payload) {
  const queue = queues[ENGINE_QUEUE_MAP[engine]];
  if (!queue) throw new Error(`Unknown engine: ${engine}`);

  const job = await queue.add(`${engine}:run:${payload.runId}`, payload);
  logger.info({ engine, jobId: job.id, runId: payload.runId }, 'Job dispatched to queue');
  return job;
}

/**
 * Dispatch jobs for all 5 engines for a given run.
 *
 * @param {object} basePayload - Common payload fields (runId, repoId, etc.)
 * @param {string[]} engines   - Array of engine names to dispatch
 */
export async function dispatchAllEngineJobs(basePayload, engines) {
  const jobs = await Promise.all(
    engines.map((engine) =>
      dispatchEngineJob(engine, { ...basePayload, engine })
    )
  );
  logger.info(
    { runId: basePayload.runId, engines, jobCount: jobs.length },
    'All engine jobs dispatched'
  );
  return jobs;
}
