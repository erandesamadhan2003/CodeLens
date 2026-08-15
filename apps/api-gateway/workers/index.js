import 'dotenv/config';
import '../config/database.js'; // Ensure pool is initialized
import infraqWorker  from './infraq.worker.js';
import infilraWorker from './infilra.worker.js';
import infilraAiWorker from './infilra-ai.worker.js';
import depraWorker   from './depra.worker.js';
import devoraWorker  from './devora.worker.js';
import docryxWorker  from './docryx.worker.js';
import logger from '../utils/logger.js';

const workers = [
  { name: 'infraq',  worker: infraqWorker  },
  { name: 'infilra', worker: infilraWorker },
  { name: 'infilra-ai', worker: infilraAiWorker },
  { name: 'depra',   worker: depraWorker   },
  { name: 'devora',  worker: devoraWorker  },
  { name: 'docryx',  worker: docryxWorker  },
];

workers.forEach(({ name }) => logger.info({ engine: name }, 'BullMQ worker started'));

// Graceful shutdown
process.on('SIGTERM', async () => {
  logger.info('SIGTERM received — closing workers...');
  await Promise.all(workers.map(({ worker }) => worker.close()));
  process.exit(0);
});

process.on('SIGINT', async () => {
  logger.info('SIGINT received — closing workers...');
  await Promise.all(workers.map(({ worker }) => worker.close()));
  process.exit(0);
});

export default workers;
