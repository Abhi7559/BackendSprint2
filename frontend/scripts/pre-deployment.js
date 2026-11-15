#!/usr/bin/env node

/**
 * scripts/pre-deployment.js
 * 
 * Pre-deployment safety gate for Next.js frontend:
 * 1. Validates all required environment variables:
 *    - Client-side variables (NEXT_PUBLIC_*) bundled into static browser bundle
 *    - Server-side variables (PORT, HOSTNAME, NODE_ENV, etc.) used at runtime
 *    - Reports ALL missing variables by name before exiting (does NOT stop at the first)
 * 2. Verifies backend API reachability (health check probe):
 *    - Connects to backend API endpoint
 *    - Blocks build if the backend service is offline, refused, or times out
 *    - Produces a clear error identifying the unreachable target
 */

const http = require('http');
const https = require('https');
const fs = require('fs');
const path = require('path');

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

// Client-side variables: statically embedded at build-time into JS bundles
const REQUIRED_CLIENT_VARS = [
  'NEXT_PUBLIC_API_URL',
];

// Server-side variables: used only during runtime/SSR/server operations
const REQUIRED_SERVER_VARS = [
  'PORT',
  'HOSTNAME',
];

// Default fallbacks for local build convenience if not explicitly set
const DEFAULTS = {
  PORT: '3000',
  HOSTNAME: '0.0.0.0',
};

// ==============================================================================
// 2. Environment Variable Validation
// ==============================================================================

function validateEnvironmentVariables() {
  console.log('==========================================================');
  console.log('==> [Frontend Pre-Deployment Gate] Step 1: Environment Variables');
  console.log('==========================================================');

  // Apply defaults if absent
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
      // Any HTTP response (even 404 or 401 or 200) proves the server is online and reachable
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
// Main Runner
// ==============================================================================

async function main() {
  validateEnvironmentVariables();

  // If SKIP_BACKEND_CHECK is explicitly set to true (e.g. standalone CI test runs), skip connectivity
  if (process.env.SKIP_BACKEND_CHECK === 'true') {
    console.log('\n[NOTICE] SKIP_BACKEND_CHECK=true detected. Skipping backend reachability probe.');
    console.log('[SUCCESS] Pre-deployment checks completed.');
    process.exit(0);
  }

  console.log('\n==========================================================');
  console.log('==> [Frontend Pre-Deployment Gate] Step 2: Backend Reachability');
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

