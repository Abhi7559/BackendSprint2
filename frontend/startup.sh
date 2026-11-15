#!/bin/sh
set -e

echo "=========================================================="
echo "==> [Frontend Container] Starting Pre-Deployment Gate"
echo "=========================================================="

# 1. Run Pre-Deployment Check (Environment variables + Backend connectivity)
node scripts/pre-deployment.js

# 2. Run Test Suite
echo "==> [Frontend Container] Running Test Suite..."
npm test

# 3. Start Application
echo "==> [Frontend Container] Starting Next.js: $@"
exec "$@"

