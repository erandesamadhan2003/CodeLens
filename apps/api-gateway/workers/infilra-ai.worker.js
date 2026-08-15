import 'dotenv/config';
import fs from 'fs';
import { Worker } from 'bullmq';
import redis from '../config/redis.js';
import { query } from '../config/database.js';
import { broadcastToUser } from '../services/websocket.service.js';
import { createNotification } from '../services/notification.service.js';
import {
  assertGeminiConfigured,
  buildTriageSummary,
  mergeFindingsWithNarratives,
  triageFindings,
} from '../services/gemini-triage.service.js';
import {
  countNarrativesGenerated,
  generateExecutiveSummary,
  generateNarratives,
} from '../services/gemini-narrative.service.js';
import logger from '../utils/logger.js';

const WORKER_NAME = 'infilra-ai';
const ENGINE = 'infilra';
const QUEUE_NAME = 'codelens-infilra-ai';
const ALL_ENGINES = ['infraq', 'infilra', 'depra', 'devora', 'docryx'];

assertGeminiConfigured();

async function processAiJob(job) {
  const { runId, scanId, findingsPath, findings, userId, repoFullName } = job.data;
  const startTime = Date.now();

  logger.info(
    {
      jobId: job.id,
      runId,
      scanId,
      findingsPath,
      inlineFindingsCount: Array.isArray(findings) ? findings.length : 0,
      worker: WORKER_NAME,
    },
    'Infilra AI worker: job received'
  );

  if (!Array.isArray(findings)) {
    throw new Error('findings_missing');
  }

  const contextPresent = findings.every((finding) => typeof finding.context === 'string');
  if (!contextPresent) {
    throw new Error('findings_context_missing');
  }

  if (findingsPath && fs.existsSync(findingsPath)) {
    const raw = fs.readFileSync(findingsPath, 'utf8');
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      throw new Error('findings_file_invalid');
    }
    logger.info(
      { runId, scanId, findingsPath, findingsCount: parsed.length, worker: WORKER_NAME },
      'Infilra AI worker: findings file validated'
    );
  }

  const triagedFindings = await triageFindings(findings);
  const triageSummary = buildTriageSummary(triagedFindings);

  const truePositiveFindings = triagedFindings.filter((finding) => finding.verdict === 'true_positive');
  const narratives = await generateNarratives(truePositiveFindings);
  const mergedFindings = mergeFindingsWithNarratives(triagedFindings, narratives);

  const narrativesGenerated = countNarrativesGenerated(mergedFindings);
  const executiveSummary = await generateExecutiveSummary(mergedFindings);
  const duration = Date.now() - startTime;

  const resultData = {
    scanId: scanId || runId,
    status: 'completed',
    findingsPath,
    findingsCount: mergedFindings.length,
    findings: mergedFindings,
    triageSummary,
    narrativesGenerated,
    executiveSummary,
    summary: `${mergedFindings.length} findings triaged: ${triageSummary.truePositive} true positive, ${triageSummary.falsePositive} false positive, ${triageSummary.unverified} unverified; ${narrativesGenerated} of ${triageSummary.truePositive} real issues explained`,
  };

  await query(
    `UPDATE engine_results
     SET status = 'completed', result_data = $1, duration_ms = $2, completed_at = NOW()
     WHERE run_id = $3 AND engine = $4`,
    [resultData, duration, runId, ENGINE]
  );

  await query(
    `UPDATE analysis_runs SET engines_completed = array_append(engines_completed, $1::engine_name_enum) WHERE id = $2`,
    [ENGINE, runId]
  );

  const runResult = await query('SELECT engines_completed FROM analysis_runs WHERE id = $1', [runId]);
  const run = runResult.rows[0];
  const allDone = ALL_ENGINES.every((e) => run.engines_completed.includes(e));

  if (allDone && userId) {
    await query(`UPDATE analysis_runs SET status = 'completed', completed_at = NOW() WHERE id = $1`, [runId]);
    broadcastToUser(userId, 'run:complete', {
      runId,
      status: 'completed',
      completedAt: new Date().toISOString(),
    });
    if (repoFullName) {
      await createNotification(
        userId,
        runId,
        'run_complete',
        'Analysis Complete',
        `All engines finished for ${repoFullName}`
      );
    }
  }

  if (userId) {
    broadcastToUser(userId, 'engine:complete', {
      runId,
      engine: ENGINE,
      status: 'completed',
      completedAt: new Date().toISOString(),
      triageSummary,
      findingsCount: mergedFindings.length,
      narrativesGenerated,
      truePositiveCount: triageSummary.truePositive,
      narrativeSummary: `${narrativesGenerated} of ${triageSummary.truePositive} real issues explained`,
      headline: executiveSummary.headline,
      topPriority: executiveSummary.topPriority,
      oneLinePerSeverity: executiveSummary.oneLinePerSeverity,
    });
  }

  logger.info(
    {
      jobId: job.id,
      runId,
      scanId,
      duration,
      triageSummary,
      narrativesGenerated,
      executiveSummary,
      worker: WORKER_NAME,
    },
    'Infilra AI worker: triage, narrative, and executive summary complete'
  );
}

const worker = new Worker(QUEUE_NAME, processAiJob, {
  connection: redis,
  concurrency: 5,
});

worker.on('failed', async (job, err) => {
  logger.error(
    {
      jobId: job?.id,
      runId: job?.data?.runId,
      scanId: job?.data?.scanId,
      worker: WORKER_NAME,
      err,
    },
    'Infilra AI worker: job failed'
  );

  if (job?.data?.runId) {
    const errorMessage = err?.message || 'ai_triage_failed';
    await query(
      `UPDATE engine_results SET status = 'failed', error_message = $1 WHERE run_id = $2 AND engine = $3`,
      [errorMessage, job.data.runId, ENGINE]
    ).catch(() => {});

    if (job?.data?.userId) {
      broadcastToUser(job.data.userId, 'engine:failed', {
        runId: job.data.runId,
        engine: ENGINE,
        error: errorMessage,
      });
    }
  }
});

worker.on('error', (err) => logger.error({ err, worker: WORKER_NAME }, 'Infilra AI worker error'));

export default worker;
