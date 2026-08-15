/**
 * Shared Gemini API client and helpers for Infilra AI stages.
 */

import 'dotenv/config';
import { GoogleGenerativeAI } from '@google/generative-ai';
import logger from '../utils/logger.js';

export const DEFAULT_GEMINI_MODEL = 'gemini-2.5-flash-lite';

let genAI = null;

/**
 * Fail fast when the worker process starts without Gemini credentials.
 */
export function assertGeminiConfigured() {
  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey || !apiKey.trim()) {
    const message = 'GEMINI_API_KEY is not set — Infilra AI triage will run with mock fallbacks';
    logger.warn(message);
    return;
  }

  genAI = new GoogleGenerativeAI(apiKey);
  const modelName = getGeminiModelName();
  logger.info({ model: modelName }, 'Gemini client configured');
}

export function getGeminiModelName() {
  return process.env.GEMINI_MODEL || DEFAULT_GEMINI_MODEL;
}

export function getGeminiClient() {
  if (!genAI) {
    throw new Error('gemini_not_configured');
  }
  return genAI;
}

/**
 * Create a Gemini model with structured JSON output for a given schema.
 *
 * @param {object} responseSchema
 */
export function createStructuredGeminiModel(responseSchema) {
  return getGeminiClient().getGenerativeModel({
    model: getGeminiModelName(),
    generationConfig: {
      responseMimeType: 'application/json',
      responseSchema,
    },
  });
}

export function chunk(items, size) {
  const batches = [];
  for (let i = 0; i < items.length; i += size) {
    batches.push(items.slice(i, i + size));
  }
  return batches;
}

export function isFatalGeminiError(err) {
  const status = err?.status ?? err?.response?.status;
  if (status === 401 || status === 403) return true;

  const message = String(err?.message || '').toLowerCase();
  return (
    message.includes('api key not valid') ||
    message.includes('api_key_invalid') ||
    message.includes('permission denied') ||
    message.includes('unauthenticated')
  );
}

export function isConnectivityError(err) {
  const message = String(err?.message || '').toLowerCase();
  return (
    message.includes('fetch failed') ||
    message.includes('network') ||
    message.includes('econnrefused') ||
    message.includes('etimedout') ||
    message.includes('socket hang up')
  );
}
