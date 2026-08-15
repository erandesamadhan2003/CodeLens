/**
 * Gemini-based exploit narrative and fix suggestions for triaged findings.
 */

import { SchemaType } from '@google/generative-ai';
import {
  chunk,
  createStructuredGeminiModel,
  getGeminiClient,
  isFatalGeminiError,
} from './gemini-client.service.js';
import logger from '../utils/logger.js';

const BATCH_SIZE = 5;

const batchNarrativeSchema = {
  type: SchemaType.OBJECT,
  properties: {
    results: {
      type: SchemaType.ARRAY,
      items: {
        type: SchemaType.OBJECT,
        properties: {
          triageId: { type: SchemaType.INTEGER },
          exploitScenario: { type: SchemaType.STRING },
          suggestedFix: { type: SchemaType.STRING },
          fixExplanation: { type: SchemaType.STRING },
        },
        required: ['triageId', 'exploitScenario', 'suggestedFix', 'fixExplanation'],
      },
    },
  },
  required: ['results'],
};

let narrativeModel = null;

function getNarrativeModel() {
  if (!narrativeModel) {
    narrativeModel = createStructuredGeminiModel(batchNarrativeSchema);
  }
  return narrativeModel;
}

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
    reasoning: finding.reasoning ?? '',
    adjustedSeverity: finding.adjustedSeverity,
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
    'You are a senior security engineer writing actionable review comments for confirmed vulnerabilities.',
    'Each finding below was triaged as a true positive.',
    'For each finding, return exploitScenario, suggestedFix, and fixExplanation matched by triageId.',
    '',
    'exploitScenario: 2-4 concrete sentences. Name the actual input, parameter, endpoint, or code path',
    'when inferable from context — not generic boilerplate.',
    'suggestedFix: corrected code snippet or short diff for THIS instance using real names from the snippet.',
    'fixExplanation: one sentence on why the fix works.',
    '',
    'FINDINGS:',
    ...serialized,
  ].join('\n');
}

function failedNarrativeResult(triageId) {
  return {
    triageId,
    exploitScenario: null,
    suggestedFix: null,
    fixExplanation: 'AI narrative generation failed',
  };
}

function parseBatchResponse(text, batch) {
  const parsed = JSON.parse(text);
  const results = Array.isArray(parsed) ? parsed : parsed?.results;

  if (!Array.isArray(results)) {
    throw new Error('gemini_narrative_response_not_array');
  }

  const byId = new Map();
  for (const entry of results) {
    if (typeof entry?.triageId !== 'number') continue;
    byId.set(entry.triageId, entry);
  }

  return batch.map((finding) => {
    const entry = byId.get(finding.triageId);
    if (!entry) {
      return failedNarrativeResult(finding.triageId);
    }

    const exploitScenario =
      typeof entry.exploitScenario === 'string' && entry.exploitScenario.trim()
        ? entry.exploitScenario.trim()
        : null;
    const suggestedFix =
      typeof entry.suggestedFix === 'string' && entry.suggestedFix.trim()
        ? entry.suggestedFix.trim()
        : null;
    const fixExplanation =
      typeof entry.fixExplanation === 'string' && entry.fixExplanation.trim()
        ? entry.fixExplanation.trim()
        : 'AI narrative generation failed';

    if (!exploitScenario || !suggestedFix) {
      return failedNarrativeResult(finding.triageId);
    }

    return {
      triageId: finding.triageId,
      exploitScenario,
      suggestedFix,
      fixExplanation,
    };
  });
}

async function callGeminiBatch(batch) {
  const prompt = buildBatchPrompt(batch);
  const result = await getNarrativeModel().generateContent(prompt);
  const text = result.response.text();

  if (!text) {
    throw new Error('gemini_narrative_empty_response');
  }

  return parseBatchResponse(text, batch);
}

async function narrativeBatchWithRetry(batch) {
  try {
    return await callGeminiBatch(batch);
  } catch (firstError) {
    logger.warn(
      { err: firstError, batchSize: batch.length, triageIds: batch.map((f) => f.triageId) },
      'Gemini narrative batch failed — retrying once'
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

/**
 * Generate exploit narratives and fix suggestions for true-positive findings.
 *
 * @param {object[]} trueFindings - Triaged findings with verdict true_positive.
 * @returns {Promise<object[]>} Narrative results keyed by triageId.
 */
export async function generateNarratives(trueFindings) {
  if (!Array.isArray(trueFindings) || trueFindings.length === 0) {
    return [];
  }

  try {
    getGeminiClient();
  } catch (err) {
    logger.error({ err }, 'Gemini narrative skipped — client not configured');
    return trueFindings.map((finding) => failedNarrativeResult(finding.triageId));
  }

  const batches = chunk(trueFindings, BATCH_SIZE);
  const narrativeById = new Map();

  for (const batch of batches) {
    try {
      const narratives = await narrativeBatchWithRetry(batch);
      narratives.forEach((entry) => narrativeById.set(entry.triageId, entry));
    } catch (err) {
      if (isFatalGeminiError(err)) {
        logger.error(
          { err, batchSize: batch.length, triageIds: batch.map((f) => f.triageId) },
          'Gemini narrative skipped — auth error; continuing with triage-only data'
        );
        return trueFindings.map((finding) => failedNarrativeResult(finding.triageId));
      }

      logger.error(
        { err, batchSize: batch.length, triageIds: batch.map((f) => f.triageId) },
        'Gemini narrative batch failed after retry — marking batch as failed'
      );

      batch.forEach((finding) => {
        narrativeById.set(finding.triageId, failedNarrativeResult(finding.triageId));
      });
    }
  }

  return trueFindings.map(
    (finding) => narrativeById.get(finding.triageId) || failedNarrativeResult(finding.triageId)
  );
}

/**
 * Count true-positive findings that received a generated exploit narrative.
 *
 * @param {object[]} findings
 */
export function countNarrativesGenerated(findings) {
  return findings.filter(
    (finding) => finding.verdict === 'true_positive' && finding.exploitScenario != null
  ).length;
}

const SEVERITY_ORDER = ['critical', 'high', 'medium', 'low'];

const executiveSummarySchema = {
  type: SchemaType.OBJECT,
  properties: {
    headline: { type: SchemaType.STRING },
    topPriority: { type: SchemaType.INTEGER },
    oneLinePerSeverity: { type: SchemaType.STRING },
  },
  required: ['headline', 'topPriority', 'oneLinePerSeverity'],
};

let executiveSummaryModel = null;

function getExecutiveSummaryModel() {
  if (!executiveSummaryModel) {
    executiveSummaryModel = createStructuredGeminiModel(executiveSummarySchema);
  }
  return executiveSummaryModel;
}

function countTruePositiveSeverity(mergedFindings) {
  const severity = { critical: 0, high: 0, medium: 0, low: 0 };

  for (const finding of mergedFindings) {
    if (finding.verdict !== 'true_positive') continue;
    if (severity[finding.adjustedSeverity] !== undefined) {
      severity[finding.adjustedSeverity] += 1;
    }
  }

  return severity;
}

function countVerdicts(mergedFindings) {
  let truePositive = 0;
  let falsePositive = 0;
  let unverified = 0;

  for (const finding of mergedFindings) {
    if (finding.verdict === 'true_positive') truePositive += 1;
    else if (finding.verdict === 'false_positive') falsePositive += 1;
    else unverified += 1;
  }

  return { truePositive, falsePositive, unverified };
}

function formatOneLinePerSeverity(severityCounts) {
  return SEVERITY_ORDER
    .map((level) => `${severityCounts[level]} ${level}`)
    .join(' · ');
}

function pickTopPriorityTriageId(truePositives) {
  for (const level of SEVERITY_ORDER) {
    const match = truePositives.find((finding) => finding.adjustedSeverity === level);
    if (match) return match.triageId;
  }
  return null;
}

function buildExecutiveSummaryInput(mergedFindings) {
  const verdictCounts = countVerdicts(mergedFindings);
  const severityCounts = countTruePositiveSeverity(mergedFindings);
  const truePositivesWithNarrative = mergedFindings.filter(
    (finding) =>
      finding.verdict === 'true_positive' &&
      typeof finding.exploitScenario === 'string' &&
      finding.exploitScenario.trim()
  );

  const findingSummaries = truePositivesWithNarrative.map((finding) => ({
    triageId: finding.triageId,
    ruleId: finding.ruleId ?? finding.rule_id,
    adjustedSeverity: finding.adjustedSeverity,
    exploitScenario: finding.exploitScenario.trim().split(/\.\s/)[0],
  }));

  return {
    verdictCounts,
    severityCounts,
    findingSummaries,
  };
}

/**
 * Locally computed executive summary fallback when Gemini is unavailable.
 *
 * @param {object[]} mergedFindings
 */
export function buildLocalExecutiveSummary(mergedFindings) {
  const severityCounts = countTruePositiveSeverity(mergedFindings);
  const truePositives = mergedFindings.filter((finding) => finding.verdict === 'true_positive');
  const oneLinePerSeverity = formatOneLinePerSeverity(severityCounts);

  if (truePositives.length === 0) {
    return {
      headline: 'No exploitable issues found in this scan.',
      topPriority: null,
      oneLinePerSeverity,
    };
  }

  const criticalCount = severityCounts.critical;
  const highCount = severityCounts.high;

  let headline;
  if (criticalCount > 0) {
    headline = `${criticalCount} critical, exploitable issues — fix before your next deploy.`;
  } else if (highCount > 0) {
    headline = `${highCount} high-severity issues found — review before deploy.`;
  } else {
    headline = `${truePositives.length} exploitable issues found — review recommended.`;
  }

  return {
    headline,
    topPriority: pickTopPriorityTriageId(truePositives),
    oneLinePerSeverity,
  };
}

function buildExecutiveSummaryPrompt(summaryInput) {
  return [
    'Write a terse dashboard status line for a security scan.',
    'headline: one specific actionable sentence, under 15 words.',
    'topPriority: triageId of the single most urgent true_positive finding, or use -1 if none.',
    'oneLinePerSeverity: short breakdown like "2 critical · 1 high · 3 medium · 4 low".',
    '',
    'SCAN SUMMARY:',
    JSON.stringify(summaryInput),
  ].join('\n');
}

function parseExecutiveSummaryResponse(text, mergedFindings) {
  const parsed = JSON.parse(text);
  const truePositives = mergedFindings.filter((finding) => finding.verdict === 'true_positive');

  const headline =
    typeof parsed?.headline === 'string' && parsed.headline.trim()
      ? parsed.headline.trim()
      : buildLocalExecutiveSummary(mergedFindings).headline;

  let topPriority = null;
  if (typeof parsed?.topPriority === 'number' && parsed.topPriority >= 0) {
    const exists = truePositives.some((finding) => finding.triageId === parsed.topPriority);
    topPriority = exists ? parsed.topPriority : pickTopPriorityTriageId(truePositives);
  } else if (parsed?.topPriority === null || parsed?.topPriority === -1) {
    topPriority = null;
  } else {
    topPriority = pickTopPriorityTriageId(truePositives);
  }

  const oneLinePerSeverity =
    typeof parsed?.oneLinePerSeverity === 'string' && parsed.oneLinePerSeverity.trim()
      ? parsed.oneLinePerSeverity.trim()
      : formatOneLinePerSeverity(countTruePositiveSeverity(mergedFindings));

  return { headline, topPriority, oneLinePerSeverity };
}

async function callExecutiveSummaryGemini(mergedFindings) {
  const summaryInput = buildExecutiveSummaryInput(mergedFindings);
  const prompt = buildExecutiveSummaryPrompt(summaryInput);
  const result = await getExecutiveSummaryModel().generateContent(prompt);
  const text = result.response.text();

  if (!text) {
    throw new Error('gemini_executive_summary_empty_response');
  }

  return parseExecutiveSummaryResponse(text, mergedFindings);
}

async function executiveSummaryWithRetry(mergedFindings) {
  try {
    return await callExecutiveSummaryGemini(mergedFindings);
  } catch (firstError) {
    logger.warn({ err: firstError }, 'Gemini executive summary failed — retrying once');

    try {
      return await callExecutiveSummaryGemini(mergedFindings);
    } catch (retryError) {
      throw retryError;
    }
  }
}

/**
 * Generate a one-line executive summary over fully merged findings.
 *
 * @param {object[]} mergedFindings
 * @returns {Promise<{ headline: string, topPriority: number|null, oneLinePerSeverity: string }>}
 */
export async function generateExecutiveSummary(mergedFindings) {
  if (!Array.isArray(mergedFindings)) {
    return buildLocalExecutiveSummary([]);
  }

  try {
    getGeminiClient();
    return await executiveSummaryWithRetry(mergedFindings);
  } catch (err) {
    logger.error({ err }, 'Gemini executive summary failed — using local fallback');
    return buildLocalExecutiveSummary(mergedFindings);
  }
}
