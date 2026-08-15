import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import morgan from 'morgan';
import { v4 as uuidv4 } from 'uuid';
import { createRequire } from 'module';

import logger from '../utils/logger.js';
import errorMiddleware from '../middlewares/error.middleware.js';
import router from '../routes/index.js';

const app = express();

// ── Security headers ────────────────────────────────────────────────────
app.use(helmet());

// ── CORS ────────────────────────────────────────────────────────────────
app.use(
  cors({
    origin: process.env.FRONTEND_URL || 'http://localhost:5173',
    credentials: true,
    methods: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
    allowedHeaders: ['Content-Type', 'Authorization', 'X-Request-Id'],
  })
);

// ── Request ID ──────────────────────────────────────────────────────────
app.use((req, _res, next) => {
  req.id = uuidv4();
  next();
});

// ── HTTP logging ─────────────────────────────────────────────────────────
app.use(
  morgan('combined', {
    stream: { write: (msg) => logger.info(msg.trim()) },
  })
);

// ── Body parsers ─────────────────────────────────────────────────────────
// NOTE: The webhook route uses express.raw() — applied at route level only.
// All other routes use json().
app.use(express.json({ limit: '1mb' }));
app.use(express.urlencoded({ extended: true }));

// ── Health check (no auth) ───────────────────────────────────────────────
import { testConnection } from '../config/database.js';
import redis from '../config/redis.js';

app.get('/health', async (_req, res) => {
  try {
    await testConnection();
    await redis.ping();
    res.json({
      status: 'ok',
      db: 'connected',
      redis: 'connected',
      timestamp: new Date().toISOString(),
    });
  } catch (err) {
    res.status(503).json({
      status: 'error',
      message: err.message,
      timestamp: new Date().toISOString(),
    });
  }
});

// ── API routes ────────────────────────────────────────────────────────────
app.use('/api/v1', router);

// ── Global error handler ──────────────────────────────────────────────────
app.use(errorMiddleware);

export default app;
