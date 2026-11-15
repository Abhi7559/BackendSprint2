import "server-only";

import {
  SecretsManagerClient,
  GetSecretValueCommand,
} from "@aws-sdk/client-secrets-manager";

/**
 * lib/secrets.server.ts
 *
 * Dedicated Server-Only module for retrieving, validating, and caching
 * secrets from AWS Secrets Manager (or local Floci emulator).
 *
 * Enforced as server-only via `import "server-only"`.
 * Any attempt to import this into client-side code will fail at build-time.
 */

export interface AppFrontendSecrets {
  JWT_SECRET: string;
  BACKEND_API_TOKEN?: string;
}

// In-memory process cache
let cachedSecrets: AppFrontendSecrets | null = null;
let inflightPromise: Promise<AppFrontendSecrets> | null = null;

// Dedicated Secrets Manager Client instance
function createSecretsClient(): SecretsManagerClient {
  const endpoint =
    process.env.AWS_SECRETS_ENDPOINT_URL ||
    process.env.FLOCI_ENDPOINT_URL ||
    "http://localhost:4566";
  const region = process.env.AWS_DEFAULT_REGION || "us-east-1";
  const accessKeyId = process.env.AWS_ACCESS_KEY_ID || "test";
  const secretAccessKey = process.env.AWS_SECRET_ACCESS_KEY || "test";

  return new SecretsManagerClient({
    endpoint,
    region,
    credentials: {
      accessKeyId,
      secretAccessKey,
    },
  });
}

/**
 * Retrieve secrets from AWS Secrets Manager / Floci.
 * Caches successfully retrieved secrets in process memory.
 * Prevents concurrent duplicate requests via promise deduplication.
 */
export async function getFrontendSecrets(
  forceRefresh = false
): Promise<AppFrontendSecrets> {
  if (cachedSecrets && !forceRefresh) {
    return cachedSecrets;
  }

  // Prevent duplicate concurrent requests while an operation is in flight
  if (inflightPromise && !forceRefresh) {
    return inflightPromise;
  }

  const secretId = process.env.AWS_SECRET_ID || "team-hub/frontend";
  const client = createSecretsClient();

  inflightPromise = (async () => {
    let response;
    try {
      const command = new GetSecretValueCommand({ SecretId: secretId });
      response = await client.send(command);
    } catch (error: any) {
      const errorName = error?.name || "UnknownError";
      let message = `Failed to retrieve secret '${secretId}': ${error?.message || error}`;

      if (errorName === "ResourceNotFoundException") {
        message = `Secret '${secretId}' was not found in Secrets Manager.`;
      } else if (
        errorName === "AccessDeniedException" ||
        errorName === "AccessDenied"
      ) {
        message = `Access denied while retrieving secret '${secretId}'.`;
      } else if (
        error?.code === "ECONNREFUSED" ||
        error?.message?.includes("fetch failed") ||
        error?.message?.includes("connect")
      ) {
        message = `Unable to connect to Secrets Manager endpoint while retrieving '${secretId}'.`;
      }

      // Do NOT cache failures
      cachedSecrets = null;
      throw new Error(message);
    } finally {
      inflightPromise = null;
    }

    if (!response || !response.SecretString) {
      throw new Error(`Secret '${secretId}' returned an empty SecretString.`);
    }

    let parsed: any;
    try {
      parsed = JSON.parse(response.SecretString);
    } catch (parseError: any) {
      throw new Error(
        `Secret '${secretId}' contains invalid JSON: ${parseError.message}`
      );
    }

    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      throw new Error(
        `Secret '${secretId}' payload must be a JSON object (key-value dictionary).`
      );
    }

    // Validate required fields
    const missingFields: string[] = [];
    if (!parsed.JWT_SECRET || String(parsed.JWT_SECRET).trim() === "") {
      missingFields.push("JWT_SECRET");
    }

    if (missingFields.length > 0) {
      throw new Error(
        `Secret '${secretId}' is missing required non-empty field(s): ${missingFields.join(", ")}`
      );
    }

    cachedSecrets = {
      JWT_SECRET: String(parsed.JWT_SECRET).trim(),
      BACKEND_API_TOKEN: parsed.BACKEND_API_TOKEN
        ? String(parsed.BACKEND_API_TOKEN).trim()
        : undefined,
    };

    return cachedSecrets;
  })();

  return inflightPromise;
}

/**
 * Testing helper to reset process memory cache
 */
export function _resetSecretsCache(): void {
  cachedSecrets = null;
  inflightPromise = null;
}
