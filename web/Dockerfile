# =============================================================================
# Makapix Web - Production Dockerfile
# =============================================================================
#
# This Dockerfile creates an OPTIMIZED PRODUCTION BUILD of the Next.js frontend.
# It is used by:
#   - deploy/stack/docker-compose.yml (VPS staging at dev.makapix.club)
#   - Future production deployments
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

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# NEXT_PUBLIC_* env vars must be present at build time (baked into JS bundles).
# Override these with --build-arg when building for different environments.
ARG NEXT_PUBLIC_API_BASE_URL=https://dev.makapix.club
ARG NEXT_PUBLIC_MQTT_WS_URL=wss://dev.makapix.club:9001
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

# Security: Run as non-root user
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

USER nextjs

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# Run the standalone Next.js server (NOT `npm run dev`)
CMD ["node", "server.js"]
