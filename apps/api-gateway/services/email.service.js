import nodemailer from 'nodemailer';
import logger from '../utils/logger.js';

let transporter = null;

function getTransporter() {
  if (!transporter) {
    if (!process.env.SMTP_HOST || !process.env.SMTP_USER) {
      logger.warn('SMTP configuration is missing. Emails will not be sent.');
      return null;
    }
    
    transporter = nodemailer.createTransport({
      host: process.env.SMTP_HOST,
      port: parseInt(process.env.SMTP_PORT || '587', 10),
      secure: process.env.SMTP_PORT === '465',
      auth: {
        user: process.env.SMTP_USER,
        pass: process.env.SMTP_PASS,
      },
    });
  }
  return transporter;
}

/**
 * Sends a critical alert email.
 * @param {string} userEmail - The email address to send to.
 * @param {string} repoFullName - e.g., 'username/repo'.
 * @param {string} branch - The branch that was scanned.
 * @param {string} engine - The engine that found the issue (e.g., 'infilra').
 * @param {Array} criticalFindings - Array of finding objects with severity HIGH or CRITICAL.
 */
export async function sendCriticalAlertEmail(userEmail, repoFullName, branch, engine, criticalFindings) {
  const mailer = getTransporter();
  if (!mailer) return false;

  if (!userEmail) {
    logger.warn({ repoFullName }, 'Cannot send alert email: no user email provided');
    return false;
  }

  const findingCount = criticalFindings.length;
  const findingPlural = findingCount === 1 ? 'Finding' : 'Findings';

  const htmlBody = `
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
      <h2 style="color: #ef4444;">🚨 Critical Security Alert</h2>
      <p>CodeLens detected <strong>${findingCount}</strong> critical or high-severity ${findingPlural.toLowerCase()} in your repository.</p>
      
      <table style="width: 100%; text-align: left; margin-bottom: 20px; border-collapse: collapse;">
        <tr><th style="padding: 8px; border-bottom: 1px solid #ddd;">Repository</th><td style="padding: 8px; border-bottom: 1px solid #ddd;">${repoFullName}</td></tr>
        <tr><th style="padding: 8px; border-bottom: 1px solid #ddd;">Branch</th><td style="padding: 8px; border-bottom: 1px solid #ddd;">${branch || 'Unknown'}</td></tr>
        <tr><th style="padding: 8px; border-bottom: 1px solid #ddd;">Scanner</th><td style="padding: 8px; border-bottom: 1px solid #ddd;">${engine}</td></tr>
      </table>

      <h3>Issues Detected:</h3>
      <ul style="padding-left: 20px;">
        ${criticalFindings.slice(0, 5).map(f => `
          <li style="margin-bottom: 10px;">
            <strong style="color: ${f.severity === 'CRITICAL' ? '#991b1b' : '#c2410c'};">[${f.severity}]</strong> 
            ${f.message || f.title || 'Unknown issue'}
          </li>
        `).join('')}
        ${findingCount > 5 ? `<li>...and ${findingCount - 5} more.</li>` : ''}
      </ul>

      <p style="margin-top: 30px;">
        <a href="${process.env.FRONTEND_URL || 'http://localhost:8080'}" style="background-color: #ef4444; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; font-weight: bold;">
          View Full Report on CodeLens
        </a>
      </p>
    </div>
  `;

  const mailOptions = {
    from: process.env.SMTP_FROM || 'CodeLens Alerts <alerts@codelens.dev>',
    to: userEmail,
    subject: `[ACTION REQUIRED] Critical Issues found in ${repoFullName}`,
    html: htmlBody,
  };

  try {
    const info = await mailer.sendMail(mailOptions);
    logger.info({ userEmail, repoFullName, engine, messageId: info.messageId }, 'Critical alert email sent');
    return true;
  } catch (error) {
    logger.error({ userEmail, repoFullName, engine, error: error.message }, 'Failed to send critical alert email');
    return false;
  }
}
