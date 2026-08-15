import 'dotenv/config';
import http from 'http';
import app from './config/app.js';
import { testConnection } from './config/database.js';
import { testRedisConnection } from './config/redis.js';
import { initWebSocketServer } from './services/websocket.service.js';
import logger from './utils/logger.js';

// Import workers — starts all 5 BullMQ workers in same process (dev)
import './workers/index.js';

const PORT = parseInt(process.env.PORT || '3001', 10);

async function start() {
  try {
    // Verify connectivity before accepting traffic
    await testConnection();
    await testRedisConnection();

    // Create HTTP server from Express app
    const server = http.createServer(app);

    // Attach WebSocket server on the same port
    initWebSocketServer(server);

    server.listen(PORT, () => {
      logger.info(
        { port: PORT, env: process.env.NODE_ENV || 'development' },
        `CodeLens API Gateway running on port ${PORT}`
      );
    });

    // Graceful shutdown
    const shutdown = async (signal) => {
      logger.info({ signal }, 'Shutdown signal received');
      server.close(() => {
        logger.info('HTTP server closed');
        process.exit(0);
      });
    };

    process.on('SIGTERM', () => shutdown('SIGTERM'));
    process.on('SIGINT',  () => shutdown('SIGINT'));

  } catch (err) {
    logger.fatal({ err }, 'Fatal startup error');
    process.exit(1);
  }
}

start();
