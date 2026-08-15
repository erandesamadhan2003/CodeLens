import jwt from 'jsonwebtoken';
import { query } from '../config/database.js';
import { exchangeCodeForToken, getAuthenticatedUser, getUserEmails } from '../services/github.service.js';
import { encrypt } from '../utils/crypto.js';
import { sendSuccess, sendError } from '../utils/response.js';
import asyncHandler from '../utils/asyncHandler.js';
import logger from '../utils/logger.js';

/**
 * GET /api/v1/auth/github
 * Redirect browser to GitHub OAuth authorization page.
 */
export const redirectToGitHub = asyncHandler(async (req, res) => {
  const params = new URLSearchParams({
    client_id: process.env.GITHUB_CLIENT_ID,
    scope: 'repo,user:email,admin:repo_hook',
    redirect_uri: `${process.env.GITHUB_WEBHOOK_BASE_URL}/api/v1/auth/github/callback`,
  });
  res.redirect(`https://github.com/login/oauth/authorize?${params.toString()}`);
});

/**
 * GET /api/v1/auth/github/callback
 * Handle OAuth callback: exchange code → token → upsert user → issue JWT.
 */
export const handleGitHubCallback = asyncHandler(async (req, res) => {
  const { code } = req.query;
  if (!code) return sendError(res, 'Missing OAuth code', null, 400);

  const accessToken = await exchangeCodeForToken(code);
  const githubUser  = await getAuthenticatedUser(accessToken);

  let email = githubUser.email;
  if (!email) {
    email = await getUserEmails(accessToken);
  }

  const encryptedToken = encrypt(accessToken);

  const result = await query(
    `INSERT INTO users (github_id, username, email, avatar_url, github_access_token, github_token_scope)
     VALUES ($1, $2, $3, $4, $5, $6)
     ON CONFLICT (github_id) DO UPDATE SET
       username = EXCLUDED.username,
       email = EXCLUDED.email,
       avatar_url = EXCLUDED.avatar_url,
       github_access_token = EXCLUDED.github_access_token,
       github_token_scope = EXCLUDED.github_token_scope,
       updated_at = NOW()
     RETURNING id, github_id, username, email, avatar_url, plan, created_at`,
    [
      String(githubUser.id),
      githubUser.login,
      email,
      githubUser.avatar_url,
      encryptedToken,
      'repo,user:email,admin:repo_hook',
    ]
  );

  const user = result.rows[0];
  const jwtToken = jwt.sign(
    { userId: user.id, githubId: user.github_id, username: user.username, plan: user.plan },
    process.env.JWT_SECRET,
    { expiresIn: process.env.JWT_EXPIRES_IN || '7d' }
  );

  logger.info({ userId: user.id, username: user.username }, 'User authenticated via GitHub');
  res.redirect(`${process.env.FRONTEND_URL}/auth/callback?token=${jwtToken}`);
});

/**
 * GET /api/v1/auth/me
 * Return current user profile.
 */
export const getMe = asyncHandler(async (req, res) => {
  return sendSuccess(res, req.user, 'User profile retrieved');
});

/**
 * POST /api/v1/auth/logout
 * JWT is stateless — client drops token. Return 200.
 */
export const logout = asyncHandler(async (req, res) => {
  return sendSuccess(res, null, 'Logged out successfully');
});
