import { NextResponse } from 'next/server';
import { getFrontendSecrets } from '../../../../lib/secrets.server';

/**
 * Server-side route handler using getFrontendSecrets() from lib/secrets.server.
 * Ensures sensitive secrets never leak to the client bundle.
 */
export async function GET() {
  try {
    const secrets = await getFrontendSecrets();
    // Verify secret is accessible without ever returning the secret value in the response
    return NextResponse.json({
      status: 'authenticated',
      hasJwtSecret: Boolean(secrets.JWT_SECRET),
      hasApiToken: Boolean(secrets.BACKEND_API_TOKEN),
      timestamp: new Date().toISOString(),
    });
  } catch (error: any) {
    return NextResponse.json(
      { error: error?.message || 'Failed to retrieve server secrets' },
      { status: 500 }
    );
  }
}
