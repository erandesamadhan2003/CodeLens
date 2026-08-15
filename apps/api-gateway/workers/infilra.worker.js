import { Worker } from 'bullmq';
import redis from '../config/redis.js';
import { query } from '../config/database.js';
import { callEngine } from '../services/engine.service.js';
import { broadcastToUser } from '../services/websocket.service.js';
import { createNotification } from '../services/notification.service.js';
import { infilraAiQueue } from '../config/queues.js';
import logger from '../utils/logger.js';

const ENGINE = 'infilra';
const QUEUE_NAME = 'codelens-infilra';
const ALL_ENGINES = ['infraq', 'infilra', 'depra', 'devora', 'docryx'];

async function processEngineJob(job) {
  const { runId, repoId, userId, engine, repoFullName, cloneUrl, commitSha, branch, githubToken, webhookEventId } = job.data;
  const startTime = Date.now();

  logger.info({ jobId: job.id, runId, engine: ENGINE }, 'Worker: job started');

  await query(
    `UPDATE engine_results SET status = 'running', started_at = NOW() WHERE run_id = $1 AND engine = $2`,
    [runId, ENGINE]
  );

  await query(
    `UPDATE analysis_runs SET status = 'running', started_at = NOW() WHERE id = $1 AND status = 'queued'`,
    [runId]
  );

  const result = await callEngine(ENGINE, {
    runId, repoId, userId, engine: ENGINE, repoFullName, cloneUrl, commitSha, branch, githubToken, webhookEventId,
  });

  if (result?.status === 'failed') {
    throw new Error(result.failureReason || result.failure_reason || 'infilra_scan_failed');
  }

  const scanId = result.scanId || result.scan_id || runId;
  const findingsPath = result.findingsPath || result.findings_path || null;
  const findings = result.findings;

  if (!Array.isArray(findings)) {
    throw new Error('infilra_findings_missing');
  }

  await query(
    `UPDATE engine_results
     SET status = 'analyzing', result_data = $1
     WHERE run_id = $2 AND engine = $3`,
    [result, runId, ENGINE]
  );

  await infilraAiQueue.add(`infilra-ai:run:${runId}`, {
    runId,
    scanId,
    findingsPath,
    findings,
    userId,
    repoFullName,
  });

  const duration = Date.now() - startTime;

  logger.info(
    {
      jobId: job.id,
      runId,
      scanId,
      findingsPath,
      findingsCount: findings.length,
      duration,
      engine: ENGINE,
    },
    'Worker: stage-1 complete, AI triage job enqueued'
  );
}

const worker = new Worker(QUEUE_NAME, processEngineJob, {
  connection: redis,
  concurrency: 5,
});

worker.on('failed', async (job, err) => {
  logger.error({ jobId: job?.id, runId: job?.data?.runId, engine: ENGINE, err }, 'Worker: job failed');
  if (job?.data?.runId) {
    await query(
      `UPDATE engine_results SET status = 'failed', error_message = $1 WHERE run_id = $2 AND engine = $3`,
      [err.message, job.data.runId, ENGINE]
    ).catch(() => {});
    if (job?.data?.userId) {
      broadcastToUser(job.data.userId, 'engine:failed', { runId: job.data.runId, engine: ENGINE, error: err.message });
    }
  }
});

worker.on('error', (err) => logger.error({ err, engine: ENGINE }, 'Worker error'));

export default worker;
