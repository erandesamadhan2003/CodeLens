import { Queue } from 'bullmq';
import redis from './redis.js';

const defaultJobOptions = {
  attempts: 3,
  backoff: { type: 'exponential', delay: 5000 },
  removeOnComplete: { count: 100 },
  removeOnFail: { count: 200 },
};

const queueOptions = {
  connection: redis,
  defaultJobOptions,
};

export const infraqQueue   = new Queue('codelens-infraq',   queueOptions);
export const infilraQueue  = new Queue('codelens-infilra',  queueOptions);
export const infilraAiQueue = new Queue('codelens-infilra-ai', queueOptions);
export const depraQueue    = new Queue('codelens-depra',    queueOptions);
export const devoraQueue   = new Queue('codelens-devora',   queueOptions);
export const docryxQueue   = new Queue('codelens-docryx',   queueOptions);

export const queues = {
  infraq:  infraqQueue,
  infilra: infilraQueue,
  infilraAi: infilraAiQueue,
  depra:   depraQueue,
  devora:  devoraQueue,
  docryx:  docryxQueue,
};

export default queues;
