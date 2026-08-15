import { ZodError } from 'zod';
import logger from '../utils/logger.js';
import { sendError } from '../utils/response.js';

const errorMiddleware = (err, req, res, _next) => {
  const reqId = req.id || 'unknown';

  // Zod validation errors → 422
  if (err instanceof ZodError) {
    const errors = err.errors.map((e) => ({
      field: e.path.join('.'),
      message: e.message,
    }));
    logger.warn({ reqId, errors }, 'Validation error');
    return sendError(res, 'Validation failed', errors, 422);
  }

  // JWT errors → 401
  if (err.name === 'JsonWebTokenError' || err.name === 'TokenExpiredError') {
    logger.warn({ reqId, err: err.message }, 'JWT error');
    return sendError(res, 'Invalid token', null, 401);
  }

  // PostgreSQL unique violation → 409
  if (err.code === '23505') {
    logger.warn({ reqId, detail: err.detail }, 'DB unique violation');
    return sendError(res, 'Resource already exists', null, 409);
  }

  // PostgreSQL foreign key violation → 400
  if (err.code === '23503') {
    logger.warn({ reqId, detail: err.detail }, 'DB foreign key violation');
    return sendError(res, 'Referenced resource does not exist', null, 400);
  }

  // Everything else → 500
  logger.error({ reqId, err }, 'Unhandled error');

  const message =
    process.env.NODE_ENV === 'production'
      ? 'Internal server error'
      : err.message;

  return sendError(res, message, null, err.statusCode || 500);
};

export default errorMiddleware;
