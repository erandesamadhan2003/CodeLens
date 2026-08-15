/**
 * Gemini-based severity triage for Infilra raw Semgrep findings.
 *
 * Model default follows Google AI docs for fast structured JSON tasks:
 * https://ai.google.dev/gemini-api/docs/models
 */

import { SchemaType } from '@google/generative-ai';
import {
  assertGeminiConfigured,
  chunk,
  createStructuredGeminiModel,
  getGeminiClient,
  isConnectivityError,
  isFatalGeminiError,
} from './gemini-client.service.js';
import logger from '../utils/logger.js';

const BATCH_SIZE = 8;

const VERDICTS = ['true_positive', 'false_positive', 'unverified'];
const SEVERITIES = ['critical', 'high', 'medium', 'low'];

const batchTriageSchema = {
  type: SchemaType.OBJECT,
  properties: {
    results: {
      type: SchemaType.ARRAY,
      items: {
        type: SchemaType.OBJECT,
        properties: {
          triageId: { type: SchemaType.INTEGER },
          verdict: {
            type: SchemaType.STRING,
            format: 'enum',
            enum: ['true_positive', 'false_positive'],
          },
          adjustedSeverity: {
            type: SchemaType.STRING,
            format: 'enum',
            enum: SEVERITIES,
          },
          reasoning: { type: SchemaType.STRING },
        },
        required: ['triageId', 'verdict', 'adjustedSeverity', 'reasoning'],
      },
    },
  },
  required: ['results'],
};

let triageModel = null;

export class TriageFatalError extends Error {
  constructor(reason = 'ai_triage_failed') {
    super(reason);
    this.name = 'TriageFatalError';
  }
}

function getTriageModel() {
  if (!triageModel) {
    triageModel = createStructuredGeminiModel(batchTriageSchema);
  }
  return triageModel;
}

export { assertGeminiConfigured };

function normalizeFindingFields(finding) {
  return {
    file: finding.file,
    startLine: finding.startLine ?? finding.start_line,
    endLine: finding.endLine ?? finding.end_line,
    ruleId: finding.ruleId ?? finding.rule_id,
    message: finding.message,
    rawSeverity: finding.rawSeverity ?? finding.raw_severity,
    codeSnippet: finding.codeSnippet ?? finding.code_snippet,
    context: finding.context ?? '',
  };
}

function buildBatchPrompt(batch) {
  const serialized = batch.map((finding) =>
    JSON.stringify({
      triageId: finding.triageId,
      ...normalizeFindingFields(finding),
    })
  );

  return [
    'You triage static analysis (Semgrep) security findings for a codebase.',
    'For each finding, return verdict, adjustedSeverity, and a short reasoning (1-2 sentences).',
    'verdict must be "true_positive" for likely real issues in reachable/production code,',
    'or "false_positive" for tests, fixtures, dead code, or benign patterns.',
    'adjustedSeverity must be one of: critical, high, medium, low.',
    'Return exactly one result per input finding, matched by triageId.',
    '',
    'FINDINGS:',
    ...serialized,
  ].join('\n');
}

function parseBatchResponse(text, batch) {
  const parsed = JSON.parse(text);
  const results = Array.isArray(parsed) ? parsed : parsed?.results;

  if (!Array.isArray(results)) {
    throw new Error('gemini_response_not_array');
  }

  const byId = new Map();
  for (const entry of results) {
    if (typeof entry?.triageId !== 'number') continue;
    byId.set(entry.triageId, entry);
  }

  const mapped = [];
  for (const finding of batch) {
    const entry = byId.get(finding.triageId);
    if (!entry) {
      mapped.push(unverifiedTriageResult(finding.triageId));
      continue;
    }

    mapped.push({
      triageId: finding.triageId,
      verdict: VERDICTS.includes(entry.verdict) ? entry.verdict : 'unverified',
      adjustedSeverity: SEVERITIES.includes(entry.adjustedSeverity)
        ? entry.adjustedSeverity
        : 'medium',
      reasoning:
        typeof entry.reasoning === 'string' && entry.reasoning.trim()
          ? entry.reasoning.trim()
          : 'AI triage failed',
    });
  }

  return mapped;
}

async function callGeminiBatch(batch) {
  const prompt = buildBatchPrompt(batch);
  const result = await getTriageModel().generateContent(prompt);
  const text = result.response.text();

  if (!text) {
    throw new Error('gemini_empty_response');
  }

  return parseBatchResponse(text, batch);
}

async function triageBatchWithRetry(batch) {
  try {
    return await callGeminiBatch(batch);
  } catch (firstError) {
    logger.warn(
      { err: firstError, batchSize: batch.length, triageIds: batch.map((f) => f.triageId) },
      'Gemini triage batch failed — retrying once'
    );

    if (isFatalGeminiError(firstError)) {
      throw firstError;
    }

    try {
      return await callGeminiBatch(batch);
    } catch (retryError) {
      if (isFatalGeminiError(retryError)) {
        throw retryError;
      }
      throw retryError;
    }
  }
}

function unverifiedTriageResult(triageId) {
  return {
    triageId,
    verdict: 'unverified',
    adjustedSeverity: 'medium',
    reasoning: 'AI triage failed',
  };
}

function mergeFindingWithTriage(finding, triage) {
  const { triageId: _triageId, ...rest } = finding;
  const normalized = normalizeFindingFields(finding);
  return {
    ...rest,
    ...normalized,
    triageId: finding.triageId,
    verdict: triage.verdict,
    adjustedSeverity: triage.adjustedSeverity,
    reasoning: triage.reasoning,
  };
}

/**
 * Triage raw findings with Gemini in batches.
 *
 * @param {object[]} findings - Raw findings from stage 1 (with context).
 * @returns {Promise<object[]>} Findings merged with triage fields.
 */
export async function triageFindings(findings) {
  try {
    getGeminiClient();
  } catch {
    throw new TriageFatalError('gemini_not_configured');
  }

  if (!Array.isArray(findings) || findings.length === 0) {
    return [];
  }

  const prepared = findings.map((finding, index) => ({
    ...finding,
    triageId: index,
  }));

  const batches = chunk(prepared, BATCH_SIZE);
  const triageById = new Map();
  let successfulBatches = 0;
  let lastConnectivityError = null;

  for (const batch of batches) {
    try {
      const triaged = await triageBatchWithRetry(batch);
      triaged.forEach((entry) => triageById.set(entry.triageId, entry));
      successfulBatches += 1;
    } catch (err) {
      if (isFatalGeminiError(err)) {
        throw new TriageFatalError('ai_triage_failed');
      }

      if (isConnectivityError(err)) {
        lastConnectivityError = err;
      }

      logger.error(
        { err, batchSize: batch.length, triageIds: batch.map((f) => f.triageId) },
        'Gemini triage batch failed after retry — marking findings unverified'
      );

      batch.forEach((finding) => {
        triageById.set(finding.triageId, unverifiedTriageResult(finding.triageId));
      });
    }
  }

  if (successfulBatches === 0 && lastConnectivityError) {
    throw new TriageFatalError('ai_triage_failed');
  }

  return prepared.map((finding) =>
    mergeFindingWithTriage(
      finding,
      triageById.get(finding.triageId) || unverifiedTriageResult(finding.triageId)
    )
  );
}

/**
 * Build summary counts for websocket payloads and result metadata.
 *
 * @param {object[]} triagedFindings
 */
export function buildTriageSummary(triagedFindings) {
  const summary = {
    truePositive: 0,
    falsePositive: 0,
    unverified: 0,
    severity: {
      critical: 0,
      high: 0,
      medium: 0,
      low: 0,
    },
  };

  for (const finding of triagedFindings) {
    if (finding.verdict === 'true_positive') summary.truePositive += 1;
    else if (finding.verdict === 'false_positive') summary.falsePositive += 1;
    else summary.unverified += 1;

    if (summary.severity[finding.adjustedSeverity] !== undefined) {
      summary.severity[finding.adjustedSeverity] += 1;
    }
  }

  return summary;
}

/**
 * Merge narrative fields onto triaged findings by triageId.
 *
 * @param {object[]} triagedFindings
 * @param {object[]} narratives
 */
export function mergeFindingsWithNarratives(triagedFindings, narratives) {
  const narrativeById = new Map(narratives.map((entry) => [entry.triageId, entry]));

  return triagedFindings.map((finding) => {
    const base = {
      ...finding,
      exploitScenario: null,
      suggestedFix: null,
      fixExplanation: null,
    };

    if (finding.verdict !== 'true_positive') {
      return base;
    }

    const narrative = narrativeById.get(finding.triageId);
    if (!narrative) {
      return {
        ...base,
        fixExplanation: 'AI narrative generation failed',
      };
    }

    return {
      ...base,
      exploitScenario: narrative.exploitScenario,
      suggestedFix: narrative.suggestedFix,
      fixExplanation: narrative.fixExplanation,
    };
  });
}
