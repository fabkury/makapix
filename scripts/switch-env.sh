#!/bin/bash
# Switch between local and remote development environments

set -e

ENV=$1

if [ -z "$ENV" ]; then
    echo "Usage: $0 <local|remote>"
    echo ""
    echo "Current environment:"
    if [ -f .env ]; then
        grep "^ENVIRONMENT=" .env || echo "  Unknown (ENVIRONMENT not set in .env)"
    else
        echo "  No .env file found"
    fi
    exit 1
fi

if [ "$ENV" != "local" ] && [ "$ENV" != "remote" ]; then
    echo "Error: Environment must be 'local' or 'remote'"
    exit 1
fi

echo "Switching to $ENV environment..."

# Copy environment file
if [ ! -f ".env.$ENV" ]; then
    echo "Error: .env.$ENV file not found"
    exit 1
fi

cp ".env.$ENV" .env
echo "✓ Copied .env.$ENV to .env"

# Copy docker-compose override
if [ -f "docker-compose.override.yml" ]; then
    rm docker-compose.override.yml
fi

if [ -f "docker-compose.override.$ENV.yml" ]; then
    cp "docker-compose.override.$ENV.yml" docker-compose.override.yml
    echo "✓ Copied docker-compose.override.$ENV.yml to docker-compose.override.yml"
fi

# Generate Caddyfile with correct domain
if [ "$ENV" = "local" ]; then
    DOMAIN="localhost"
else
    DOMAIN="dev.makapix.club"
fi

# Generate Caddyfile from template
if [ -f "proxy/Caddyfile.template" ]; then
    DOMAIN=$DOMAIN envsubst < proxy/Caddyfile.template > proxy/Caddyfile
    echo "✓ Generated proxy/Caddyfile for domain: $DOMAIN"
fi

echo ""
echo "✅ Environment switched to: $ENV"
echo ""
echo "Configuration:"
echo "  Domain: $DOMAIN"
if [ "$ENV" = "local" ]; then
    echo "  URL: http://localhost"
else
    echo "  URL: https://dev.makapix.club"
fi
echo ""
echo "Next steps:"
echo "  1. Update GitHub OAuth credentials in .env if needed"
echo "  2. Run: docker compose down"
echo "  3. Run: docker compose up -d"
echo ""
echo "Don't forget to configure your GitHub Apps:"
echo "  - OAuth App: https://github.com/settings/applications/new"
echo "  - GitHub App: https://github.com/settings/apps/new"

