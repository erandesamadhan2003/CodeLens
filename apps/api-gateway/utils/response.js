/**
 * Standard API response helpers for consistent response shapes.
 */

export function success(data = null, message = 'Success', statusCode = 200) {
  return {
    statusCode,
    body: {
      success: true,
      message,
      data,
      timestamp: new Date().toISOString(),
    },
  };
}

export function error(message = 'Internal server error', errors = null, statusCode = 500) {
  return {
    statusCode,
    body: {
      success: false,
      message,
      errors,
      timestamp: new Date().toISOString(),
    },
  };
}

export function paginated(data, page, limit, total) {
  return {
    statusCode: 200,
    body: {
      success: true,
      data,
      pagination: {
        page: parseInt(page, 10),
        limit: parseInt(limit, 10),
        total,
        totalPages: Math.ceil(total / limit),
      },
      timestamp: new Date().toISOString(),
    },
  };
}

/**
 * Send a success response.
 */
export function sendSuccess(res, data, message = 'Success', statusCode = 200) {
  const { body } = success(data, message, statusCode);
  return res.status(statusCode).json(body);
}

/**
 * Send an error response.
 */
export function sendError(res, message = 'Internal server error', errors = null, statusCode = 500) {
  const { body } = error(message, errors, statusCode);
  return res.status(statusCode).json(body);
}

/**
 * Send a paginated response.
 */
export function sendPaginated(res, data, page, limit, total) {
  const { body, statusCode } = paginated(data, page, limit, total);
  return res.status(statusCode).json(body);
}
