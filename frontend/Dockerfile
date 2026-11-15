# ==============================================================================
# Multi-stage Dockerfile for Next.js Frontend with Enforced Pre-Deployment Gate
# Order: environment check -> connectivity check -> tests -> serve
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Dependencies and Build Stage
# ------------------------------------------------------------------------------
FROM node:20-alpine AS builder

WORKDIR /app

ARG NEXT_PUBLIC_API_URL
ARG PORT=3000
ARG HOSTNAME=0.0.0.0

ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    PORT=$PORT \
    HOSTNAME=$HOSTNAME \
    NODE_ENV=production \
    SKIP_BACKEND_CHECK=true

# Install dependencies first for layer caching
COPY package.json package-lock.json* ./
RUN npm install

# Copy application source code, scripts, and tests
COPY . .

# Enforce build-time gate: 
# 1. prebuild (validates all env vars)
# 2. test (runs full test suite)
# 3. next build (produces optimized bundle)
RUN npm run prebuild && npm test && npm run build

# ------------------------------------------------------------------------------
# Stage 2: Minimal Production Runtime Image
# ------------------------------------------------------------------------------
FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# Copy runtime assets and build output
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/scripts ./scripts
COPY --from=builder /app/tests ./tests
COPY startup.sh /app/startup.sh

RUN chmod +x /app/startup.sh

EXPOSE 3000

# Enforce safety gate on container start
ENTRYPOINT ["/app/startup.sh"]

CMD ["npm", "run", "start"]
