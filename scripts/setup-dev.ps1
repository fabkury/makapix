# Initial setup script for development environment (PowerShell)

Write-Host "🚀 Makapix Development Environment Setup" -ForegroundColor Cyan
Write-Host ""

# Check if .env.local exists, if not create from template
if (-not (Test-Path ".env.local")) {
    Write-Host "Creating .env.local from template..."
    Copy-Item env.local.template .env.local
    Write-Host "✓ Created .env.local" -ForegroundColor Green
    Write-Host "⚠️  Please edit .env.local and add your GitHub OAuth credentials" -ForegroundColor Yellow
} else {
    Write-Host "✓ .env.local already exists" -ForegroundColor Green
}

# Check if .env.remote exists, if not create from template
if (-not (Test-Path ".env.remote")) {
    Write-Host "Creating .env.remote from template..."
    Copy-Item env.remote.template .env.remote
    Write-Host "✓ Created .env.remote" -ForegroundColor Green
    Write-Host "⚠️  Please edit .env.remote and add your GitHub OAuth credentials" -ForegroundColor Yellow
} else {
    Write-Host "✓ .env.remote already exists" -ForegroundColor Green
}

Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Configure GitHub OAuth Apps:"
Write-Host "   - Local: https://github.com/settings/applications/new"
Write-Host "     Homepage: http://localhost"
Write-Host "     Callback: http://localhost/auth/github/callback"
Write-Host ""
Write-Host "   - Remote: https://github.com/settings/applications/new"
Write-Host "     Homepage: https://dev.makapix.club"
Write-Host "     Callback: https://dev.makapix.club/auth/github/callback"
Write-Host ""
Write-Host "2. Configure GitHub Apps:"
Write-Host "   - Local: https://github.com/settings/apps/new"
Write-Host "   - Remote: https://github.com/settings/apps/new"
Write-Host ""
Write-Host "3. Update .env.local with your local GitHub credentials"
Write-Host "4. Update .env.remote with your remote GitHub credentials"
Write-Host ""
Write-Host "5. Switch to your desired environment:"
Write-Host "   make local"
Write-Host "   make remote"
Write-Host ""
Write-Host "6. Start the services:"
Write-Host "   make up"
Write-Host ""

