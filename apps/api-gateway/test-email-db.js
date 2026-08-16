import 'dotenv/config';
import { checkAndAlertCriticalFindings } from './services/alert.service.js';

async function testAlertService() {
  console.log('Testing checkAndAlertCriticalFindings...');
  
  // Use the exact UUID from the database
  const userId = 'd8e127ee-a74f-4e3f-809c-ae60300498d5';
  
  const mockResult = {
    findings: [
      { severity: 'CRITICAL', message: 'Test DB Integration Critical Finding' }
    ]
  };
  
  try {
    await checkAndAlertCriticalFindings(userId, 'TestRepo/CodeLens', 'main', 'test-engine', mockResult);
    console.log('checkAndAlertCriticalFindings completed without throwing errors.');
  } catch (err) {
    console.error('Error:', err);
  }
}

testAlertService().then(() => {
  // Give it a second to flush logs
  setTimeout(() => process.exit(0), 2000);
});
