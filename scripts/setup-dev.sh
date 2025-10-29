#!/bin/bash
# Initial setup script for development environment

set -e

echo "🚀 Makapix Development Environment Setup"
echo ""

# Check if .env.local exists, if not create from template
if [ ! -f ".env.local" ]; then
    echo "Creating .env.local from template..."
    cp env.local.template .env.local
    echo "✓ Created .env.local"
    echo "⚠️  Please edit .env.local and add your GitHub OAuth credentials"
else
    echo "✓ .env.local already exists"
fi

# Check if .env.remote exists, if not create from template
if [ ! -f ".env.remote" ]; then
    echo "Creating .env.remote from template..."
    cp env.remote.template .env.remote
    echo "✓ Created .env.remote"
    echo "⚠️  Please edit .env.remote and add your GitHub OAuth credentials"
else
    echo "✓ .env.remote already exists"
fi

# Make switch scripts executable
chmod +x scripts/switch-env.sh 2>/dev/null || true
echo "✓ Made scripts executable"

echo ""
echo "📋 Next Steps:"
echo ""
echo "1. Configure GitHub OAuth Apps:"
echo "   - Local: https://github.com/settings/applications/new"
echo "     Homepage: http://localhost"
echo "     Callback: http://localhost/auth/github/callback"
echo ""
echo "   - Remote: https://github.com/settings/applications/new"
echo "     Homepage: https://dev.makapix.club"
echo "     Callback: https://dev.makapix.club/auth/github/callback"
echo ""
echo "2. Configure GitHub Apps:"
echo "   - Local: https://github.com/settings/apps/new"
echo "   - Remote: https://github.com/settings/apps/new"
echo ""
echo "3. Update .env.local with your local GitHub credentials"
echo "4. Update .env.remote with your remote GitHub credentials"
echo ""
echo "5. Switch to your desired environment:"
echo "   make local    # For local development"
echo "   make remote   # For remote development"
echo ""
echo "6. Start the services:"
echo "   make up"
echo ""

