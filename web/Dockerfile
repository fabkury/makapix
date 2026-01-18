# =============================================================================
# Makapix Web - Production Dockerfile
# =============================================================================
#
# This Dockerfile creates an OPTIMIZED PRODUCTION BUILD of the Next.js frontend.
# It is used by:
#   - deploy/stack/docker-compose.yml (production at makapix.club)
#
# DO NOT use this for local development. Use the root docker-compose.yml instead,
# which overrides the CMD to run `npm run dev` with hot reload.
#
# Why production mode matters:
#   - Mobile browsers can fail with styled-jsx errors in dev mode
#   - Production builds are ~5x smaller (~165MB vs ~877MB)
#   - Startup time is ~100ms vs ~1000ms+
#   - Pre-compiled assets avoid webpack race conditions
#
# Build context: Repository root (not web/ directory)
# Usage: docker build -f web/Dockerfile -t stack-web .
#
# =============================================================================

FROM node:20-alpine AS base

WORKDIR /app

RUN apk add --no-cache libc6-compat curl

# -----------------------------------------------------------------------------
# Stage 1: Install dependencies
# -----------------------------------------------------------------------------
FROM base AS deps
COPY web/package.json web/package-lock.json ./
COPY web/scripts ./scripts
RUN npm ci

# -----------------------------------------------------------------------------
# Stage 2: Build the application
# -----------------------------------------------------------------------------
FROM base AS builder
COPY --from=deps /app/node_modules ./node_modules
COPY web/package.json web/tsconfig.json web/next.config.mjs web/.eslintrc.cjs web/.prettierrc ./
COPY web/scripts ./scripts
COPY web/src ./src
COPY web/public ./public

# webpxmux ships its WASM binary in node_modules. We must serve it from Next.js public assets
# so the browser can fetch it at runtime (used by the WebP animation WASM fallback).
RUN mkdir -p public/wasm && cp node_modules/webpxmux/dist/webpxmux.wasm public/wasm/webpxmux.wasm

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# NEXT_PUBLIC_* env vars must be present at build time (baked into JS bundles).
# Override these with --build-arg when building for different environments.
ARG NEXT_PUBLIC_API_BASE_URL=https://makapix.club
ARG NEXT_PUBLIC_MQTT_WS_URL=wss://makapix.club/mqtt
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
ENV NEXT_PUBLIC_MQTT_WS_URL=$NEXT_PUBLIC_MQTT_WS_URL

RUN npm run build

# -----------------------------------------------------------------------------
# Stage 3: Production runtime (minimal image)
# -----------------------------------------------------------------------------
FROM base AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Need su-exec so we can do one-time root initialization (for persistent volumes)
# and then drop privileges for the actual Next.js server.
RUN apk add --no-cache su-exec

# Security: Run as non-root user (after init)
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public

# Set up the prerender cache directory
RUN mkdir .next
RUN chown nextjs:nodejs .next

# Copy the standalone server and static assets
# See: https://nextjs.org/docs/advanced-features/output-file-tracing
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

# Also keep a copy of the current build's static assets in the image layer so we can
# sync them into a persistent volume at runtime (without deleting older chunks).
COPY --from=builder /app/.next/static /opt/next-static

COPY web/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Run entrypoint as root so it can initialize/chown mounted volumes, then drop to nextjs.
USER root

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# Run the standalone Next.js server (NOT `npm run dev`)
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["node", "server.js"]
