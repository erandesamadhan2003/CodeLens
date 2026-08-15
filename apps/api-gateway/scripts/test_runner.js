import axios from 'axios';
import jwt from 'jsonwebtoken';
import pg from 'pg';
import { v4 as uuidv4 } from 'uuid';

import { encrypt } from '../utils/crypto.js';

const { Pool } = pg;

const JWT_SECRET = process.env.JWT_SECRET || 'your-super-secret-jwt-key-min-32-chars-here';
const DB_URL = process.env.DATABASE_URL || 'postgresql://user:password@localhost:5432/codelens';
const API_URL = 'http://localhost:3001/api/v1';

const pool = new Pool({ connectionString: DB_URL });

async function setup() {
  const userId = uuidv4();
  const repoIdValid = uuidv4();
  const repoIdInvalid = uuidv4();

  const dummyToken = encrypt('ghp_dummytokenfortesting');

  // Create User
  await pool.query(`
    INSERT INTO users (id, github_id, username, email, github_access_token) 
    VALUES ($1, $2, 'testuser', 'test@example.com', $3)
  `, [userId, uuidv4(), dummyToken]);

  // Create Valid Repo
  await pool.query(`
    INSERT INTO repositories (id, user_id, github_repo_id, owner, name, full_name, clone_url, default_branch)
    VALUES ($1, $2, $3, 'test', 'valid', 'test/valid', 'https://github.com/octocat/Hello-World.git', 'master')
  `, [repoIdValid, userId, uuidv4()]);

  // Create Invalid Repo
  await pool.query(`
    INSERT INTO repositories (id, user_id, github_repo_id, owner, name, full_name, clone_url, default_branch)
    VALUES ($1, $2, $3, 'test', 'invalid', 'test/invalid', 'https://github.com/codelens/does-not-exist.git', 'main')
  `, [repoIdInvalid, userId, uuidv4()]);

  const token = jwt.sign({ userId: userId, username: 'testuser' }, JWT_SECRET, { expiresIn: '1h' });
  
  return { userId, repoIdValid, repoIdInvalid, token };
}

async function triggerRun(repoId, token, commitSha = 'dummy-sha') {
  try {
    const payload = { repoId, engines: ['infraq'] };
    if (commitSha) payload.commitSha = commitSha;
    
    const res = await axios.post(`${API_URL}/runs`, payload, {
      headers: { Authorization: `Bearer ${token}` }
    });
    const runId = res.data?.data?.id;
    console.log(`Triggered run for repo ${repoId}. Run ID: ${runId}`);
    return runId;
  } catch (error) {
    console.error(`Error triggering run:`, error.response?.data || error.message);
    return null;
  }
}

async function checkStatus(runId) {
    const res = await pool.query('SELECT status FROM analysis_runs WHERE id = $1', [runId]);
    return res.rows[0]?.status;
}

async function run() {
  console.log('Setting up database...');
  const { userId, repoIdValid, repoIdInvalid, token } = await setup();
  console.log(`User created. Token: ${token}`);

  console.log('\n--- Case 1: Valid Repository ---');
  const run1 = await triggerRun(repoIdValid, token, 'master');
  
  console.log('\n--- Case 2: Invalid Repository URL ---');
  const run2 = await triggerRun(repoIdInvalid, token, 'main');
  
  console.log('\n--- Case 3: Invalid Commit SHA ---');
  const run3 = await triggerRun(repoIdValid, token, '0000000000000000000000000000000000000000');
  
  console.log('\n--- Case 7: Duplicate Job ---');
  const run4 = await triggerRun(repoIdValid, token, 'master');
  
  console.log('\nRuns triggered. Please monitor the API Gateway and worker logs for progress.');
  console.log('To test Python Unavailable (Case 4), stop the infrastructure-engine container: docker compose stop infrastructure-engine');
  console.log('To test Redis Unavailable (Case 5), stop the redis container: docker compose stop redis');
}

run().then(() => {
    console.log('Finished triggering tests.');
    process.exit(0);
}).catch(console.error);
