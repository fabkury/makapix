# =============================================================================
# Piskel Editor - Makapix Integration Build
# =============================================================================
# This Dockerfile builds the Piskel pixel art editor with Makapix-specific
# customizations and serves it via Caddy.
# =============================================================================

# Build stage
FROM node:18-alpine AS builder

WORKDIR /app

# Install grunt-cli globally for build
RUN npm install -g grunt-cli

# Copy package files first for layer caching
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build production version
RUN grunt build

# Verify build succeeded
RUN test -f dest/prod/index.html || (echo "Build failed: index.html not found" && exit 1)

# =============================================================================
# Production stage - lightweight static file server
# =============================================================================
FROM caddy:2-alpine

# Copy built files from builder
COPY --from=builder /app/dest/prod /srv

# Copy Caddyfile for standalone mode
# Note: When using caddy-docker-proxy, this Caddyfile is NOT used.
# The proxy generates config from container labels.
# This is only here for standalone/local testing.
COPY Caddyfile /etc/caddy/Caddyfile

EXPOSE 80

