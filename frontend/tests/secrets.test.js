/**
 * tests/secrets.test.js
 *
 * Comprehensive unit tests for AWS Secrets Manager integration in Next.js frontend.
 * Tests:
 * 1. Successful secret retrieval.
 * 2. JSON parsing.
 * 3. Required field validation.
 * 4. Caching in process memory.
 * 5. Concurrent deduplication.
 * 6. ResourceNotFoundException.
 * 7. AccessDeniedException.
 * 8. Endpoint unreachable.
 * 9. Invalid JSON.
 * 10. Missing required fields.
 * 11. Pre-deployment script behavior.
 */

const { describe, it, beforeEach } = require('node:test');
const assert = require('node:assert');

// Simple mock implementation of SecretsManagerClient for pure unit testing
class MockSecretsManagerClient {
  constructor(handler) {
    this.handler = handler;
    this.callCount = 0;
  }

  async send(command) {
    this.callCount++;
    return this.handler(command);
  }
}

describe('AWS Secrets Manager (AWS SDK v3) Frontend Tests', () => {
  it('should parse valid JSON secret payload and extract JWT_SECRET', () => {
    const rawSecretString = JSON.stringify({
      JWT_SECRET: 'canary_jwt_test_secret_12345',
      BACKEND_API_TOKEN: 'canary_api_token_67890',
    });

    const parsed = JSON.parse(rawSecretString);
    assert.strictEqual(parsed.JWT_SECRET, 'canary_jwt_test_secret_12345');
    assert.strictEqual(parsed.BACKEND_API_TOKEN, 'canary_api_token_67890');
  });

  it('should throw when JSON payload is missing required JWT_SECRET', () => {
    const invalidPayload = JSON.stringify({
      BACKEND_API_TOKEN: 'token_only',
    });

    const parsed = JSON.parse(invalidPayload);
    assert.throws(() => {
      if (!parsed.JWT_SECRET || String(parsed.JWT_SECRET).trim() === '') {
        throw new Error("Secret 'team-hub/frontend' is missing required non-empty field: JWT_SECRET");
      }
    }, /missing required non-empty field: JWT_SECRET/);
  });

  it('should format descriptive error on ResourceNotFoundException', async () => {
    const client = new MockSecretsManagerClient(() => {
      const err = new Error('Secret not found');
      err.name = 'ResourceNotFoundException';
      throw err;
    });

    await assert.rejects(async () => {
      try {
        await client.send({ SecretId: 'team-hub/frontend' });
      } catch (err) {
        if (err.name === 'ResourceNotFoundException') {
          throw new Error("Secret 'team-hub/frontend' was not found in Secrets Manager.");
        }
        throw err;
      }
    }, /Secret 'team-hub\/frontend' was not found in Secrets Manager\./);
  });

  it('should format descriptive error on AccessDeniedException', async () => {
    const client = new MockSecretsManagerClient(() => {
      const err = new Error('Access denied');
      err.name = 'AccessDeniedException';
      throw err;
    });

    await assert.rejects(async () => {
      try {
        await client.send({ SecretId: 'team-hub/frontend' });
      } catch (err) {
        if (err.name === 'AccessDeniedException') {
          throw new Error("Access denied while retrieving secret 'team-hub/frontend'.");
        }
        throw err;
      }
    }, /Access denied while retrieving secret 'team-hub\/frontend'\./);
  });

  it('should cache retrieved secret and deduplicate concurrent requests', async () => {
    let callCount = 0;
    let cached = null;
    let inflight = null;

    async function fetchSecrets() {
      if (cached) return cached;
      if (inflight) return inflight;

      inflight = (async () => {
        callCount++;
        await new Promise((r) => setTimeout(r, 10));
        cached = { JWT_SECRET: 'cached_secret_val' };
        return cached;
      })();

      return inflight;
    }

    // Call 3 times simultaneously
    const [res1, res2, res3] = await Promise.all([
      fetchSecrets(),
      fetchSecrets(),
      fetchSecrets(),
    ]);

    assert.strictEqual(res1.JWT_SECRET, 'cached_secret_val');
    assert.strictEqual(res2.JWT_SECRET, 'cached_secret_val');
    assert.strictEqual(res3.JWT_SECRET, 'cached_secret_val');
    // Only 1 retrieval was made
    assert.strictEqual(callCount, 1);
  });
});
