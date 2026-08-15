import axios from 'axios';

const GITHUB_API = 'https://api.github.com';
const GITHUB_OAUTH = 'https://github.com';

const githubHeaders = (accessToken) => ({
  Authorization: `Bearer ${accessToken}`,
  Accept: 'application/vnd.github.v3+json',
  'X-GitHub-Api-Version': '2022-11-28',
  'User-Agent': 'CodeLens-Platform',
});

/**
 * Exchange a GitHub OAuth code for an access token.
 */
export async function exchangeCodeForToken(code) {
  const response = await axios.post(
    `${GITHUB_OAUTH}/login/oauth/access_token`,
    {
      client_id: process.env.GITHUB_CLIENT_ID,
      client_secret: process.env.GITHUB_CLIENT_SECRET,
      code,
    },
    { headers: { Accept: 'application/json' } }
  );
  if (response.data.error) {
    throw new Error(`GitHub OAuth error: ${response.data.error_description}`);
  }
  return response.data.access_token;
}

/**
 * Get the authenticated GitHub user's profile.
 */
export async function getAuthenticatedUser(accessToken) {
  const response = await axios.get(`${GITHUB_API}/user`, {
    headers: githubHeaders(accessToken),
  });
  return response.data;
}

/**
 * Get the authenticated user's repositories.
 */
export async function getUserRepos(accessToken, page = 1, perPage = 30) {
  const response = await axios.get(`${GITHUB_API}/user/repos`, {
    headers: githubHeaders(accessToken),
    params: { sort: 'updated', per_page: perPage, page },
  });
  return response.data;
}

/**
 * Get a single repository by owner and name.
 */
export async function getRepo(accessToken, owner, repo) {
  const response = await axios.get(`${GITHUB_API}/repos/${owner}/${repo}`, {
    headers: githubHeaders(accessToken),
  });
  return response.data;
}

/**
 * Get the latest commit on a branch.
 */
export async function getLatestCommit(accessToken, owner, repo, branch) {
  const response = await axios.get(
    `${GITHUB_API}/repos/${owner}/${repo}/commits/${branch}`,
    { headers: githubHeaders(accessToken) }
  );
  return {
    sha: response.data.sha,
    message: response.data.commit.message,
    authorName: response.data.commit.author.name,
  };
}

/**
 * Create a GitHub webhook on a repository.
 */
export async function createWebhook(accessToken, owner, repo, webhookUrl, secret) {
  const response = await axios.post(
    `${GITHUB_API}/repos/${owner}/${repo}/hooks`,
    {
      name: 'web',
      active: true,
      events: ['push', 'pull_request'],
      config: {
        url: webhookUrl,
        content_type: 'json',
        secret,
        insecure_ssl: '0',
      },
    },
    { headers: githubHeaders(accessToken) }
  );
  return response.data;
}

/**
 * Delete a GitHub webhook from a repository.
 */
export async function deleteWebhook(accessToken, owner, repo, webhookId) {
  await axios.delete(
    `${GITHUB_API}/repos/${owner}/${repo}/hooks/${webhookId}`,
    { headers: githubHeaders(accessToken) }
  );
}

/**
 * Compare two commits and return file-level patches.
 */
export async function compareCommits(accessToken, owner, repo, base, head) {
  const response = await axios.get(
    `${GITHUB_API}/repos/${owner}/${repo}/compare/${base}...${head}`,
    { headers: githubHeaders(accessToken) }
  );
  return response.data;
}

/**
 * Collect unique changed file paths from a push webhook commits array.
 */
export function collectChangedFiles(commits = []) {
  const files = new Set();
  for (const commit of commits) {
    for (const key of ['added', 'modified', 'removed']) {
      for (const filePath of commit[key] || []) {
        files.add(filePath);
      }
    }
  }
  return [...files];
}

/**
 * Map GitHub compare API files to documentation-engine diff payload shape.
 */
export function mapCompareFilesToDiffs(files = []) {
  return files.map((file) => ({
    filename: file.filename,
    patch: file.patch || '',
    status: file.status === 'added' ? 'added'
      : file.status === 'removed' ? 'removed'
      : 'modified',
  }));
}

/**
 * Get a user's email addresses from GitHub.
 */
export async function getUserEmails(accessToken) {
  const response = await axios.get(`${GITHUB_API}/user/emails`, {
    headers: githubHeaders(accessToken),
  });
  const primary = response.data.find((e) => e.primary && e.verified);
  return primary ? primary.email : null;
}
