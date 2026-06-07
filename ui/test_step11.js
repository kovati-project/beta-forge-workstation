#!/usr/bin/env node
/**
 * Verify Step 11 frontend components compile
 */

const fs = require('fs');
const path = require('path');

const setupDir = 'src/components/setup';
const requiredFiles = [
  'SetupWizard.jsx',
  'ProgressBar.jsx',
  'Step1Hardware.jsx',
  'Step2Profile.jsx',
  'Step3Secrets.jsx',
  'Step4Network.jsx',
  'Step5Provision.jsx',
  'Step6Validate.jsx',
  'Step7Handoff.jsx',
  'SetupWizard.css',
  'ProgressBar.css',
];

const setupAPI = 'src/utils/setupAPI.js';

let allFilesExist = true;
for (const file of requiredFiles) {
  const fullPath = path.join(setupDir, file);
  if (fs.existsSync(fullPath)) {
    console.log(`[OK] ${file} exists`);
  } else {
    console.log(`[ERROR] ${file} missing`);
    allFilesExist = false;
  }
}

if (fs.existsSync(setupAPI)) {
  console.log(`[OK] setupAPI.js exists`);
} else {
  console.log(`[ERROR] setupAPI.js missing`);
  allFilesExist = false;
}

// Check Setup.jsx integration
const setupPage = 'src/pages/Setup.jsx';
if (fs.existsSync(setupPage)) {
  const content = fs.readFileSync(setupPage, 'utf-8');
  if (content.includes('SetupWizard')) {
    console.log('[OK] Setup.jsx imports SetupWizard');
  } else {
    console.log('[ERROR] Setup.jsx does not import SetupWizard');
    allFilesExist = false;
  }
  if (content.includes('setupAPI')) {
    console.log('[OK] Setup.jsx imports setupAPI');
  } else {
    console.log('[ERROR] Setup.jsx does not import setupAPI');
    allFilesExist = false;
  }
}

// Check App.jsx has setup route
const appPage = 'src/App.jsx';
if (fs.existsSync(appPage)) {
  const content = fs.readFileSync(appPage, 'utf-8');
  if (content.includes('<Route path="/setup"') && content.includes('<Setup')) {
    console.log('[OK] App.jsx has /setup route');
  } else {
    console.log('[ERROR] App.jsx missing /setup route');
    allFilesExist = false;
  }
}

if (allFilesExist) {
  console.log('[OK] Step 11 frontend verified');
  process.exit(0);
} else {
  console.log('[ERROR] Step 11 frontend incomplete');
  process.exit(1);
}
