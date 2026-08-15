import authMiddleware from './auth.middleware.js';
import apiKeyMiddleware from './apiKey.middleware.js';

const multiAuthMiddleware = (req, res, next) => {
  const authHeader = req.headers.authorization;
  const apiKeyHeader = req.headers['x-api-key'];

  // If x-api-key is present, use apiKeyMiddleware
  if (apiKeyHeader) {
    return apiKeyMiddleware(req, res, next);
  }

  // If Authorization: Bearer <token> is present, check token format
  if (authHeader && authHeader.startsWith('Bearer ')) {
    const token = authHeader.split(' ')[1];
    
    // JWT tokens typically have 3 parts separated by dots
    if (token.split('.').length === 3) {
      return authMiddleware(req, res, next);
    }
    
    // Otherwise, assume it's an API key
    return apiKeyMiddleware(req, res, next);
  }

  // If neither, fallback to authMiddleware to return the standard 401 error
  return authMiddleware(req, res, next);
};

export default multiAuthMiddleware;
