import 'dotenv/config';
import { sendCriticalAlertEmail } from './services/email.service.js';

async function testEmail() {
  console.log('Testing email dispatch...');
  const success = await sendCriticalAlertEmail(
    'harshaagarwal820@gmail.com', // To
    'TestRepo/CodeLens', // Repo Name
    'main', // Branch
    'test-engine', // Engine
    [
      { severity: 'CRITICAL', message: 'Test Critical Vulnerability 1' },
      { severity: 'HIGH', message: 'Test High Vulnerability 2' }
    ] // Findings
  );
  console.log('Email send success:', success);
}

testEmail().catch(console.error);
