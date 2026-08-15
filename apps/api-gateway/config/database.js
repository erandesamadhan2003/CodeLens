import pg from 'pg';
import logger from '../utils/logger.js';

const { Pool } = pg;

const pool = new Pool({
  host: process.env.DB_HOST || 'localhost',
  port: parseInt(process.env.DB_PORT || '5432', 10),
  database: process.env.DB_NAME || 'codelens',
  user: process.env.DB_USER || 'user',
  password: process.env.DB_PASSWORD || 'password',
  min: parseInt(process.env.DB_POOL_MIN || '2', 10),
  max: parseInt(process.env.DB_POOL_MAX || '10', 10),
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 10000,
});

pool.on('error', (err) => {
  logger.error({ err }, 'PostgreSQL pool error');
});

/**
 * Test the database connection. Throws if unable to connect.
 */
export async function testConnection() {
  const client = await pool.connect();
  try {
    await client.query('SELECT 1');
    logger.info('PostgreSQL connection established');
  } finally {
    client.release();
  }
}

/**
 * Execute a parameterised query against the pool.
 *
 * @param {string} text   - SQL query string with $1, $2 placeholders
 * @param {Array}  params - Parameter values
 * @returns {pg.QueryResult}
 */
export async function query(text, params = []) {
  const start = Date.now();
  const result = await pool.query(text, params);
  const duration = Date.now() - start;
  logger.debug({ query: text, duration, rows: result.rowCount }, 'DB query executed');
  return result;
}

/**
 * Get a client from the pool for transactions.
 * Caller is responsible for calling client.release().
 */
export async function getClient() {
  return pool.connect();
}

export default pool;
