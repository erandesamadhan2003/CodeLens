import { Worker } from 'bullmq';
import axios from 'axios';
import redis from '../config/redis.js';
import { query } from '../config/database.js';
import { ENGINE_URLS } from '../services/engine.service.js';
import { broadcastToUser } from '../services/websocket.service.js';
import { createNotification } from '../services/notification.service.js';
import logger from '../utils/logger.js';
import readline from 'readline';

const ENGINE = 'infraq';
const QUEUE_NAME = `codelens-${ENGINE}`;
const ALL_ENGINES = ['infraq', 'infilra', 'depra', 'devora', 'docryx'];

async function processEngineJob(job) {
  const { runId, repoId, userId, repoFullName, cloneUrl, commitSha, branch } = job.data;
  const startTime = Date.now();

  logger.info({ jobId: job.id, runId, engine: ENGINE }, 'Worker: job started');

  // Mark engine_result as running
  await query(
    `UPDATE engine_results SET status = 'running', started_at = NOW() WHERE run_id = $1 AND engine = $2`,
    [runId, ENGINE]
  );

  // Mark analysis_run as running (only if still queued)
  await query(
    `UPDATE analysis_runs SET status = 'running', started_at = NOW() WHERE id = $1 AND status = 'queued'`,
    [runId]
  );

  // Exact Payload Contract for InfraQ
  const payload = {
    runId,
    repositoryId: repoId,
    repoUrl: cloneUrl,
    commitSha,
    branch
  };

  const url = ENGINE_URLS[ENGINE];
  if (!url) throw new Error(`Unknown engine URL for: ${ENGINE}`);
  const endpoint = `${url}/internal/analyze`;

  return new Promise(async (resolve, reject) => {
    try {
      const response = await axios.post(endpoint, payload, {
        responseType: 'stream',
        timeout: 300000, // 5 minutes max
        headers: { 'Content-Type': 'application/json' },
      });

      const rl = readline.createInterface({ input: response.data });
      
      let finalResult = null;

      rl.on('line', (line) => {
        if (!line.trim()) return;
        try {
          const event = JSON.parse(line);
          
          if (event.final_result) {
            finalResult = event.final_result;
          } else if (event.stage) {
            // Standard Progress Event
            const eventName = `infra.${event.stage}.${event.status}`;
            broadcastToUser(userId, eventName, event);
            logger.debug({ runId, eventName }, 'Broadcasted progress event');
          }
        } catch (err) {
          logger.error({ err, line }, 'Failed to parse NDJSON line from engine');
        }
      });

      rl.on('close', async () => {
        const duration = Date.now() - startTime;
        
        if (!finalResult) {
           // Connection closed before final result received
           return reject(new Error("Stream closed before final result was received."));
        }

        try {
          // Update engine_result with success
          await query(
            `UPDATE engine_results
             SET status = 'completed', result_data = $1, duration_ms = $2, ai_tokens_used = $3, completed_at = NOW()
             WHERE run_id = $4 AND engine = $5`,
            [finalResult, duration, finalResult?.ai_tokens_used || null, runId, ENGINE]
          );

          // Append engine to engines_completed
          await query(
            `UPDATE analysis_runs
             SET engines_completed = array_append(engines_completed, $1::engine_name_enum)
             WHERE id = $2`,
            [ENGINE, runId]
          );

          // Check if all engines completed
          const runResult = await query(
            'SELECT engines_completed, engines_requested FROM analysis_runs WHERE id = $1',
            [runId]
          );
          const run = runResult.rows[0];
          const allDone = ALL_ENGINES.every((e) => run.engines_completed.includes(e));

          if (allDone) {
            await query(
              `UPDATE analysis_runs SET status = 'completed', completed_at = NOW() WHERE id = $1`,
              [runId]
            );
            broadcastToUser(userId, 'run:complete', { runId, status: 'completed', completedAt: new Date().toISOString() });
            await createNotification(userId, runId, 'run_complete', 'Analysis Complete', `All engines finished for ${repoFullName}`);
          }

          broadcastToUser(userId, 'engine:complete', { runId, engine: ENGINE, status: 'completed', completedAt: new Date().toISOString() });
          logger.info({ jobId: job.id, runId, engine: ENGINE, duration }, 'Worker: job completed');
          resolve();
        } catch (dbErr) {
          reject(dbErr);
        }
      });

      rl.on('error', (err) => reject(err));
      
    } catch (err) {
      reject(err);
    }
  });
}

const infrastructureWorker = new Worker(QUEUE_NAME, processEngineJob, {
  connection: redis,
  concurrency: 5,
  attempts: 3,
  backoff: { type: 'exponential', delay: 2000 }
});

infrastructureWorker.on('failed', async (job, err) => {
  logger.error({ jobId: job?.id, runId: job?.data?.runId, engine: ENGINE, err }, 'Worker: job failed');
  if (job?.data?.runId) {
    await query(
      `UPDATE engine_results SET status = 'failed', error_message = $1 WHERE run_id = $2 AND engine = $3`,
      [err.message, job.data.runId, ENGINE]
    ).catch(() => {});
    if (job?.data?.userId) {
      broadcastToUser(job.data.userId, 'infra.analysis.failed', { 
        runId: job.data.runId, 
        engine: ENGINE, 
        stage: 'analysis',
        status: 'failed',
        message: err.message 
      });
      broadcastToUser(job.data.userId, 'engine:failed', { runId: job.data.runId, engine: ENGINE, error: err.message });
    }
  }
});

infrastructureWorker.on('error', (err) => logger.error({ err, engine: ENGINE }, 'Worker error'));

export default infrastructureWorker;
