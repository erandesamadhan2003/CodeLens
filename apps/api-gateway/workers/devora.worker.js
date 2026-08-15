import { Worker } from 'bullmq';
import redis from '../config/redis.js';
import { query } from '../config/database.js';
import { callEngine } from '../services/engine.service.js';
import { broadcastToUser } from '../services/websocket.service.js';
import { createNotification } from '../services/notification.service.js';
import logger from '../utils/logger.js';

const ENGINE = 'devora';
const QUEUE_NAME = 'codelens-devora';
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

  const duration = Date.now() - startTime;

  await query(
    `UPDATE engine_results
     SET status = 'completed', result_data = $1, duration_ms = $2, ai_tokens_used = $3, completed_at = NOW()
     WHERE run_id = $4 AND engine = $5`,
    [result, duration, result?.ai_tokens_used || null, runId, ENGINE]
  );

  await query(
    `UPDATE analysis_runs SET engines_completed = array_append(engines_completed, $1::engine_name_enum) WHERE id = $2`,
    [ENGINE, runId]
  );

  const runResult = await query('SELECT engines_completed FROM analysis_runs WHERE id = $1', [runId]);
  const run = runResult.rows[0];
  const allDone = ALL_ENGINES.every((e) => run.engines_completed.includes(e));

  if (allDone) {
    await query(`UPDATE analysis_runs SET status = 'completed', completed_at = NOW() WHERE id = $1`, [runId]);
    broadcastToUser(userId, 'run:complete', { runId, status: 'completed', completedAt: new Date().toISOString() });
    await createNotification(userId, runId, 'run_complete', 'Analysis Complete', `All engines finished for ${repoFullName}`);
  }

  broadcastToUser(userId, 'engine:complete', { runId, engine: ENGINE, status: 'completed', completedAt: new Date().toISOString() });
  logger.info({ jobId: job.id, runId, engine: ENGINE, duration }, 'Worker: job completed');
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
