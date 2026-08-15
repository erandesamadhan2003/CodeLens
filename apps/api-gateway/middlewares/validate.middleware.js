import { ZodError } from 'zod';
import { sendError } from '../utils/response.js';

/**
 * Returns an Express middleware that validates req.body against a Zod schema.
 * On failure, responds with 422 and field-level errors.
 *
 * @param {import('zod').ZodTypeAny} schema
 */
const validate = (schema) => (req, res, next) => {
  try {
    req.body = schema.parse(req.body);
    next();
  } catch (err) {
    if (err instanceof ZodError) {
      const errors = err.errors.map((e) => ({
        field: e.path.join('.'),
        message: e.message,
      }));
      return sendError(res, 'Validation failed', errors, 422);
    }
    next(err);
  }
};

export default validate;
