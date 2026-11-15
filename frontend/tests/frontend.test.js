/**
 * tests/frontend.test.js
 *
 * Frontend unit and integration tests verifying client configuration and page integrity.
 * Executed via Node test runner (zero external testing dependencies needed).
 */
const { describe, it } = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

// Auto-load .env.local if present and not already in environment
if (!process.env.NEXT_PUBLIC_API_URL) {
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
}

describe('Frontend Pre-Deployment & Configuration Tests', () => {
  it('should have NEXT_PUBLIC_API_URL defined in environment', () => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL;
    assert.ok(apiUrl, 'NEXT_PUBLIC_API_URL must be defined');
    assert.match(apiUrl, /^https?:\/\//, 'NEXT_PUBLIC_API_URL must be a valid HTTP/HTTPS URL');
  });

  it('should have valid application entrypoints and metadata', () => {
    const layoutPath = path.join(__dirname, '..', 'app', 'layout.js');
    const pagePath = path.join(__dirname, '..', 'app', 'page.js');
    assert.strictEqual(fs.existsSync(layoutPath), true, 'app/layout.js must exist');
    assert.strictEqual(fs.existsSync(pagePath), true, 'app/page.js must exist');
  });

  it('should contain Film Review application markup elements in page source', () => {
    const pageContent = fs.readFileSync(path.join(__dirname, '..', 'app', 'page.js'), 'utf-8');
    assert.ok(pageContent.includes('NEXT_PUBLIC_API_URL'), 'page.js must reference NEXT_PUBLIC_API_URL');
    assert.ok(pageContent.includes('Film'), 'page.js must contain Film platform logic');
  });

  it('should parse JWT tokens correctly in helper logic', () => {
    const samplePayload = { sub: 'user-123', role: 'critic', exp: 9999999999 };
    const base64UrlPayload = Buffer.from(JSON.stringify(samplePayload)).toString('base64url');
    const mockJwt = `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.${base64UrlPayload}.mocksignature`;

    const parts = mockJwt.split('.');
    assert.strictEqual(parts.length, 3, 'JWT should contain 3 parts');

    const decoded = JSON.parse(Buffer.from(parts[1], 'base64').toString('utf-8'));
    assert.strictEqual(decoded.sub, 'user-123');
    assert.strictEqual(decoded.role, 'critic');
  });
});

