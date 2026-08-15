import { WebSocketServer } from 'ws';
import jwt from 'jsonwebtoken';
import logger from '../utils/logger.js';

// Map of userId → Set<WebSocket>
const connections = new Map();

let wss = null;

/**
 * Attach a WebSocket server to the existing HTTP server.
 * Verifies JWT from query string on connection.
 *
 * @param {import('http').Server} httpServer
 */
export function initWebSocketServer(httpServer) {
  wss = new WebSocketServer({ noServer: true });

  httpServer.on('upgrade', (req, socket, head) => {
    const url = new URL(req.url, `http://${req.headers.host}`);
    const token = url.searchParams.get('token');

    if (!token) {
      socket.write('HTTP/1.1 401 Unauthorized\r\n\r\n');
      socket.destroy();
      return;
    }

    let decoded;
    try {
      decoded = jwt.verify(token, process.env.JWT_SECRET);
    } catch {
      socket.write('HTTP/1.1 401 Unauthorized\r\n\r\n');
      socket.destroy();
      return;
    }

    wss.handleUpgrade(req, socket, head, (ws) => {
      ws.userId = decoded.userId;
      wss.emit('connection', ws, req);
    });
  });

  wss.on('connection', (ws) => {
    const { userId } = ws;
    logger.info({ userId }, 'WebSocket client connected');

    // Register connection
    if (!connections.has(userId)) {
      connections.set(userId, new Set());
    }
    connections.get(userId).add(ws);

    // Handle pong responses
    ws.isAlive = true;
    ws.on('pong', () => {
      ws.isAlive = true;
    });

    ws.on('message', (data) => {
      try {
        const msg = JSON.parse(data.toString());
        if (msg.type === 'ping') {
          ws.send(JSON.stringify({ type: 'pong' }));
        }
      } catch {
        // Ignore unparseable messages
      }
    });

    ws.on('close', () => {
      logger.info({ userId }, 'WebSocket client disconnected');
      const userSockets = connections.get(userId);
      if (userSockets) {
        userSockets.delete(ws);
        if (userSockets.size === 0) {
          connections.delete(userId);
        }
      }
    });

    ws.on('error', (err) => {
      logger.error({ userId, err }, 'WebSocket error');
    });

    // Send welcome event
    ws.send(JSON.stringify({ event: 'connected', data: { userId } }));
  });

  // Heartbeat every 30s — remove dead connections
  const heartbeat = setInterval(() => {
    wss.clients.forEach((ws) => {
      if (!ws.isAlive) {
        logger.warn({ userId: ws.userId }, 'WebSocket heartbeat failed, terminating');
        return ws.terminate();
      }
      ws.isAlive = false;
      ws.ping();
    });
  }, 30000);

  wss.on('close', () => clearInterval(heartbeat));

  logger.info('WebSocket server initialized');
  return wss;
}

/**
 * Broadcast a JSON event to all WebSocket connections for a given userId.
 *
 * @param {string} userId
 * @param {string} event  - Event name, e.g. 'engine:complete'
 * @param {object} data   - Event payload
 */
export function broadcastToUser(userId, event, data) {
  const userSockets = connections.get(userId);
  if (!userSockets || userSockets.size === 0) return;

  const message = JSON.stringify({ event, data });
  userSockets.forEach((ws) => {
    if (ws.readyState === ws.OPEN) {
      ws.send(message);
    }
  });
}

/**
 * Get active connection count for a user.
 */
export function getUserConnectionCount(userId) {
  return connections.get(userId)?.size || 0;
}
