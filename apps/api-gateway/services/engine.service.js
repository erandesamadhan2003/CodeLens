import axios from 'axios';
import logger from '../utils/logger.js';

const ENGINE_URLS = {
  infraq:  process.env.INFRAQ_URL  || 'http://infrastructure-engine:8000',
  infilra: process.env.INFILRA_URL || 'http://security-engine:8000',
  depra:   process.env.DEPRA_URL   || 'http://dependency-engine:8000',
  devora:  process.env.DEVORA_URL  || 'http://developer-enginer:8000',
  docryx:  process.env.DOCRYX_URL  || 'http://documentation-engine:8000',
};

/**
 * Send a job payload to a FastAPI engine service via HTTP POST.
 *
 * @param {string} engine  - Engine name
 * @param {object} payload - Job payload
 * @returns {object} Engine response data
 */
export async function callEngine(engine, payload, path = '/analyze') {
  const url = ENGINE_URLS[engine];
  if (!url) throw new Error(`Unknown engine: ${engine}`);

  const endpoint = `${url}${path}`;
  logger.info({ engine, endpoint, runId: payload.runId }, 'Calling engine service');

  const response = await axios.post(endpoint, payload, {
    timeout: 300000, // 5 minutes max per engine
    headers: { 'Content-Type': 'application/json' },
  });

  return response.data;
}

/**
 * Check engine health endpoint.
 *
 * @param {string} engine
 * @returns {boolean}
 */
export async function checkEngineHealth(engine) {
  const url = ENGINE_URLS[engine];
  try {
    const response = await axios.get(`${url}/health`, { timeout: 5000 });
    return response.status === 200;
  } catch {
    return false;
  }
}

export { ENGINE_URLS };
