import jwt from 'jsonwebtoken';
import { query } from '../config/database.js';
import { sendError } from '../utils/response.js';
import logger from '../utils/logger.js';

const authMiddleware = async (req, res, next) => {
  try {
    const authHeader = req.headers.authorization;
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return sendError(res, 'Authorization header missing or malformed', null, 401);
    }

    const token = authHeader.split(' ')[1];
    const decoded = jwt.verify(token, process.env.JWT_SECRET);

    const result = await query(
      'SELECT id, github_id, username, email, avatar_url, plan, created_at FROM users WHERE id = $1',
      [decoded.userId]
    );

    if (result.rows.length === 0) {
      return sendError(res, 'User not found', null, 401);
    }

    req.user = result.rows[0];
    logger.debug({ userId: req.user.id, reqId: req.id }, 'Auth middleware: user attached');
    next();
  } catch (err) {
    if (err.name === 'JsonWebTokenError' || err.name === 'TokenExpiredError') {
      return sendError(res, 'Invalid or expired token', null, 401);
    }
    next(err);
  }
};

export default authMiddleware;
