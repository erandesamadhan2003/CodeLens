import { sendSuccess, sendPaginated } from '../utils/response.js';
import asyncHandler from '../utils/asyncHandler.js';
import {
  listNotifications,
  markNotificationRead,
  markAllNotificationsRead,
} from '../services/notification.service.js';

/**
 * GET /api/v1/notifications
 * List notifications for the current user.
 */
export const getNotifications = asyncHandler(async (req, res) => {
  const page  = parseInt(req.query.page  || '1', 10);
  const limit = parseInt(req.query.limit || '20', 10);

  const { notifications, total } = await listNotifications(req.user.id, page, limit);
  return sendPaginated(res, notifications, page, limit, total);
});

/**
 * PUT /api/v1/notifications/:notifId/read
 * Mark one notification as read.
 */
export const markRead = asyncHandler(async (req, res) => {
  const { notifId } = req.params;
  const notification = await markNotificationRead(notifId, req.user.id);
  if (!notification) return sendError(res, 'Notification not found', null, 404);
  return sendSuccess(res, notification, 'Notification marked as read');
});

/**
 * PUT /api/v1/notifications/read-all
 * Mark all notifications for the user as read.
 */
export const markAllRead = asyncHandler(async (req, res) => {
  const count = await markAllNotificationsRead(req.user.id);
  return sendSuccess(res, { updated: count }, 'All notifications marked as read');
});
