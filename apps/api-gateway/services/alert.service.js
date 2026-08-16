import { query } from '../config/database.js';
import { sendCriticalAlertEmail } from './email.service.js';
import logger from '../utils/logger.js';

/**
 * Checks an engine's result for CRITICAL or HIGH findings, and emails the user if found.
 * @param {string} userId - The user ID from DB
 * @param {string} repoFullName - e.g., 'username/repo'
 * @param {string} branch - The branch that was scanned
 * @param {string} engine - e.g., 'infilra', 'depra'
 * @param {Object} result - The result_data object returned from the engine
 */
export async function checkAndAlertCriticalFindings(userId, repoFullName, branch, engine, result) {
  try {
    if (!result || !Array.isArray(result.findings)) {
      return;
    }

    // Filter findings
    const criticalFindings = result.findings.filter(
      (f) => f.severity === 'CRITICAL' || f.severity === 'HIGH'
    );

    if (criticalFindings.length === 0) {
      return;
    }

    logger.info({ userId, repoFullName, engine, count: criticalFindings.length }, 'Critical findings detected, preparing alert');

    // Get the user's email
    const userQuery = await query('SELECT email FROM users WHERE id = $1', [userId]);
    if (userQuery.rows.length === 0) {
      logger.warn({ userId }, 'User not found for alert email');
      return;
    }

    const userEmail = userQuery.rows[0].email;
    
    // Send email
    await sendCriticalAlertEmail(userEmail, repoFullName, branch, engine, criticalFindings);
  } catch (error) {
    logger.error({ error: error.message, engine, repoFullName }, 'Failed to check and alert critical findings');
  }
}
