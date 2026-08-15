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
export const depraQueue    = new Queue('codelens-depra',    queueOptions);
export const devoraQueue   = new Queue('codelens-devora',   queueOptions);
export const docryxQueue   = new Queue('codelens-docryx',   queueOptions);
export const documentationEngineQueue = new Queue('documentation-engine', queueOptions);
export const dependencyEngineQueue = new Queue('dependency-engine', queueOptions);

export const queues = {
  infraq:  infraqQueue,
  infilra: infilraQueue,
  depra:   depraQueue,
  devora:  devoraQueue,
  docryx:  docryxQueue,
  documentationEngine: documentationEngineQueue,
  dependencyEngine: dependencyEngineQueue,
};

export default queues;
