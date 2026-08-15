import { query } from '../config/database.js';
import { broadcastToUser } from './websocket.service.js';
import logger from '../utils/logger.js';

/**
 * Create a notification for a user and broadcast it via WebSocket.
 *
 * @param {string} userId
 * @param {string|null} runId
 * @param {string} type  - e.g. 'run_complete', 'critical_vuln', 'new_repo'
 * @param {string} title
 * @param {string} body
 */
export async function createNotification(userId, runId, type, title, body) {
  const result = await query(
    `INSERT INTO notifications (user_id, run_id, type, title, body)
     VALUES ($1, $2, $3, $4, $5)
     RETURNING id, user_id, run_id, type, title, body, is_read, created_at`,
    [userId, runId || null, type, title, body]
  );

  const notification = result.rows[0];
  logger.info({ userId, notificationId: notification.id, type }, 'Notification created');

  // Broadcast to user via WebSocket
  broadcastToUser(userId, 'notification:new', {
    id: notification.id,
    type: notification.type,
    title: notification.title,
    body: notification.body,
  });

  return notification;
}

/**
 * List notifications for a user (unread first, paginated).
 */
export async function listNotifications(userId, page = 1, limit = 20) {
  const offset = (page - 1) * limit;

  const countResult = await query(
    'SELECT COUNT(*) FROM notifications WHERE user_id = $1',
    [userId]
  );
  const total = parseInt(countResult.rows[0].count, 10);

  const result = await query(
    `SELECT id, run_id, type, title, body, is_read, created_at
     FROM notifications
     WHERE user_id = $1
     ORDER BY is_read ASC, created_at DESC
     LIMIT $2 OFFSET $3`,
    [userId, limit, offset]
  );

  return { notifications: result.rows, total };
}

/**
 * Mark a single notification as read.
 */
export async function markNotificationRead(notifId, userId) {
  const result = await query(
    `UPDATE notifications
     SET is_read = true
     WHERE id = $1 AND user_id = $2
     RETURNING *`,
    [notifId, userId]
  );
  return result.rows[0] || null;
}

/**
 * Mark all notifications for a user as read.
 */
export async function markAllNotificationsRead(userId) {
  const result = await query(
    `UPDATE notifications SET is_read = true
     WHERE user_id = $1 AND is_read = false`,
    [userId]
  );
  return result.rowCount;
}
