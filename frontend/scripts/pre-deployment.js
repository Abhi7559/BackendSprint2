#!/usr/bin/env node

/**
 * scripts/pre-deployment.js
 * 
 * Pre-deployment safety gate for Next.js frontend:
 * 1. Validates required environment variables (client vs server).
 * 2. Verifies backend API reachability (health check probe).
 * 3. Verifies AWS Secrets Manager / Floci reachability & validates the secret payload.
 * 
 * Reuses the SDK client connection pattern (validating secret name, required fields, etc.).
 * Never logs or exposes sensitive credential values.
 */

const http = require('http');
const https = require('https');
const fs = require('fs');
const path = require('path');
const { SecretsManagerClient, GetSecretValueCommand } = require('@aws-sdk/client-secrets-manager');

// Auto-load .env.local if present and not already in environment
const envLocalPath = path.join(__dirname, '..', '.env.local');
if (fs.existsSync(envLocalPath)) {
  const lines = fs.readFileSync(envLocalPath, 'utf-8').split('\n');
  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed && !trimmed.startsWith('#') && trimmed.includes('=')) {
      const [k, ...v] = trimmed.split('=');
      if (k.trim() && !process.env[k.trim()]) {
        process.env[k.trim()] = v.join('=').trim();
      }
    }
  }
}

// ==============================================================================
// 1. Environment Variable Specifications
// ==============================================================================

const REQUIRED_CLIENT_VARS = [
  'NEXT_PUBLIC_API_URL',
];

const REQUIRED_SERVER_VARS = [
  'PORT',
  'HOSTNAME',
];

const DEFAULTS = {
  PORT: '3000',
  HOSTNAME: '0.0.0.0',
  AWS_SECRETS_ENDPOINT_URL: 'http://localhost:4566',
  AWS_DEFAULT_REGION: 'us-east-1',
  AWS_SECRET_ID: 'team-hub/frontend',
  AWS_ACCESS_KEY_ID: 'test',
  AWS_SECRET_ACCESS_KEY: 'test',
};

// ==============================================================================
// 2. Environment Variable Validation
// ==============================================================================

function validateEnvironmentVariables() {
  console.log('==========================================================');
  console.log('==> [Frontend Pre-Deployment Gate] Step 1: Environment Variables');
  console.log('==========================================================');

  for (const [key, value] of Object.entries(DEFAULTS)) {
    if (!process.env[key]) {
      process.env[key] = value;
    }
  }

  const missingClient = [];
  const missingServer = [];

  for (const varName of REQUIRED_CLIENT_VARS) {
    const val = process.env[varName];
    if (!val || val.trim() === '') {
      missingClient.push(varName);
    }
  }

  for (const varName of REQUIRED_SERVER_VARS) {
    const val = process.env[varName];
    if (!val || val.trim() === '') {
      missingServer.push(varName);
    }
  }

  const allMissing = [...missingClient, ...missingServer];

  if (allMissing.length > 0) {
    console.error('----------------------------------------------------------');
    console.error('[FATAL] Pre-deployment check failed: Missing required environment variables!');
    console.error('----------------------------------------------------------');
    
    if (missingClient.length > 0) {
      console.error('\nMissing Client-Side Variables (NEXT_PUBLIC_*):');
      missingClient.forEach((v) => console.error(`  - ${v} (Required for static client bundle generation)`));
    }
    
    if (missingServer.length > 0) {
      console.error('\nMissing Server-Side Variables:');
      missingServer.forEach((v) => console.error(`  - ${v} (Required for server runtime execution)`));
    }

    console.error('\nAborting build. Refusing to produce a broken build bundle.');
    console.error('----------------------------------------------------------');
    process.exit(1);
  }

  console.log('[SUCCESS] All required environment variables are present:');
  REQUIRED_CLIENT_VARS.forEach((v) => console.log(`  ✓ ${v} = ${process.env[v]}`));
  REQUIRED_SERVER_VARS.forEach((v) => console.log(`  ✓ ${v} = ${process.env[v]}`));
}

// ==============================================================================
// 3. Backend API Connectivity Check
// ==============================================================================

function checkBackendReachability(urlStr, timeoutMs = 5000) {
  return new Promise((resolve, reject) => {
    let parsedUrl;
    try {
      parsedUrl = new URL(urlStr);
    } catch (err) {
      return reject(new Error(`Invalid URL format: "${urlStr}"`));
    }

    const client = parsedUrl.protocol === 'https:' ? https : http;
    const reqOptions = {
      protocol: parsedUrl.protocol,
      hostname: parsedUrl.hostname,
      port: parsedUrl.port || (parsedUrl.protocol === 'https:' ? 443 : 80),
      path: '/health',
      method: 'GET',
      timeout: timeoutMs,
    };

    console.log(`--> [Pre-Deployment] Checking Backend API connectivity at: ${parsedUrl.origin}`);

    const req = client.request(reqOptions, (res) => {
      resolve({ status: res.statusCode });
    });

    req.on('timeout', () => {
      req.destroy();
      reject(new Error(`Connection timed out after ${timeoutMs}ms while contacting ${parsedUrl.origin}`));
    });

    req.on('error', (err) => {
      reject(new Error(`Failed to connect to backend at ${parsedUrl.origin}: ${err.message}`));
    });

    req.end();
  });
}

// ==============================================================================
// 4. AWS Secrets Manager Validation Check
// ==============================================================================

async function checkSecretsManager() {
  const secretId = process.env.AWS_SECRET_ID || 'team-hub/frontend';
  const endpoint = process.env.AWS_SECRETS_ENDPOINT_URL || 'http://localhost:4566';
  const region = process.env.AWS_DEFAULT_REGION || 'us-east-1';

  console.log('\n==========================================================');
  console.log('==> [Frontend Pre-Deployment Gate] Step 2: Secrets Manager Check');
  console.log('==========================================================');
  console.log(`--> Checking Secrets Manager endpoint at: ${endpoint}`);
  console.log(`--> Verifying secret existence: '${secretId}'`);

  const client = new SecretsManagerClient({
    endpoint,
    region,
    credentials: {
      accessKeyId: process.env.AWS_ACCESS_KEY_ID || 'test',
      secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY || 'test',
    },
  });

  let response;
  try {
    const command = new GetSecretValueCommand({ SecretId: secretId });
    response = await client.send(command);
  } catch (err) {
    const errorName = err?.name || 'Error';
    let msg = `Secrets Manager check failed for secret '${secretId}': ${err.message}`;

    if (errorName === 'ResourceNotFoundException') {
      msg = `Secret '${secretId}' was not found in Secrets Manager.`;
    } else if (errorName === 'AccessDeniedException' || errorName === 'AccessDenied') {
      msg = `Access denied while retrieving secret '${secretId}'.`;
    } else if (err.code === 'ECONNREFUSED' || err.message?.includes('fetch failed')) {
      msg = `Unable to connect to Secrets Manager endpoint at '${endpoint}' while retrieving '${secretId}'.`;
    }

    console.error('----------------------------------------------------------');
    console.error(`[FATAL] ${msg}`);
    console.error('----------------------------------------------------------');
    process.exit(1);
  }

  if (!response || !response.SecretString) {
    console.error(`[FATAL] Secret '${secretId}' has no SecretString content.`);
    process.exit(1);
  }

  let parsed;
  try {
    parsed = JSON.parse(response.SecretString);
  } catch (e) {
    console.error(`[FATAL] Secret '${secretId}' contains invalid JSON: ${e.message}`);
    process.exit(1);
  }

  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    console.error(`[FATAL] Secret '${secretId}' payload must be a JSON object.`);
    process.exit(1);
  }

  if (!parsed.JWT_SECRET || String(parsed.JWT_SECRET).trim() === '') {
    console.error(`[FATAL] Secret '${secretId}' is missing required non-empty field: JWT_SECRET`);
    process.exit(1);
  }

  console.log(`[SUCCESS] Secret '${secretId}' retrieved and validated successfully.`);
}

// ==============================================================================
// Main Runner
// ==============================================================================

async function main() {
  validateEnvironmentVariables();

  // If SKIP_PREDEPLOYMENT_NETWORK_CHECKS is set (e.g. during standalone Docker image build), skip external calls
  if (process.env.SKIP_BACKEND_CHECK === 'true' || process.env.SKIP_PREDEPLOYMENT_NETWORK_CHECKS === 'true') {
    console.log('\n[NOTICE] Network probes skipped (build-time isolation flag set).');
    console.log('[SUCCESS] Pre-deployment checks completed.');
    process.exit(0);
  }

  // 1. Check Secrets Manager
  await checkSecretsManager();

  // 2. Check Backend API Reachability
  console.log('\n==========================================================');
  console.log('==> [Frontend Pre-Deployment Gate] Step 3: Backend Reachability');
  console.log('==========================================================');

  const apiUrl = process.env.NEXT_PUBLIC_API_URL;

  try {
    const result = await checkBackendReachability(apiUrl);
    console.log(`[SUCCESS] Backend API is reachable! (HTTP status: ${result.status})`);
    console.log('==========================================================');
    console.log('==> [Frontend Pre-Deployment Gate] All checks passed successfully!');
    console.log('==========================================================\n');
    process.exit(0);
  } catch (err) {
    console.error('----------------------------------------------------------');
    console.error(`[FATAL] Critical External Service Check Failed!`);
    console.error(`Target Service: Backend API (${apiUrl})`);
    console.error(`Error Details:  ${err.message}`);
    console.error('----------------------------------------------------------');
    console.error('Next.js build aborted: Cannot build frontend against an unreachable backend.');
    console.error('Please ensure the Backend API container/service is running and healthy.');
    console.error('----------------------------------------------------------');
    process.exit(1);
  }
}

main();
