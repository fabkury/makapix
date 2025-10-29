# Switch between local and remote development environments (PowerShell)

param(
    [Parameter(Position=0)]
    [ValidateSet('local', 'remote')]
    [string]$Env
)

if (-not $Env) {
    Write-Host "Usage: .\scripts\switch-env.ps1 <local|remote>"
    Write-Host ""
    Write-Host "Current environment:"
    if (Test-Path .env) {
        $currentEnv = Select-String -Path .env -Pattern "^ENVIRONMENT=" | ForEach-Object { $_.Line }
        if ($currentEnv) {
            Write-Host "  $currentEnv"
        } else {
            Write-Host "  Unknown (ENVIRONMENT not set in .env)"
        }
    } else {
        Write-Host "  No .env file found"
    }
    exit 1
}

Write-Host "Switching to $Env environment..." -ForegroundColor Cyan

# Copy environment file
if (-not (Test-Path ".env.$Env")) {
    Write-Host "Error: .env.$Env file not found" -ForegroundColor Red
    exit 1
}

Copy-Item ".env.$Env" .env -Force
Write-Host "Copied .env.$Env to .env" -ForegroundColor Green

# Copy docker-compose override
if (Test-Path "docker-compose.override.yml") {
    Remove-Item "docker-compose.override.yml" -Force
}

if (Test-Path "docker-compose.override.$Env.yml") {
    Copy-Item "docker-compose.override.$Env.yml" docker-compose.override.yml -Force
    Write-Host "Copied docker-compose.override.$Env.yml to docker-compose.override.yml" -ForegroundColor Green
}

# Generate Caddyfile with correct domain
$domain = if ($Env -eq "local") { "localhost" } else { "dev.makapix.club" }

# Generate Caddyfile from template
if (Test-Path "proxy/Caddyfile.template") {
    $template = Get-Content "proxy/Caddyfile.template" -Raw
    $caddyfile = $template -replace '\{\$DOMAIN:localhost\}', $domain
    Set-Content -Path "proxy/Caddyfile" -Value $caddyfile
    Write-Host "Generated proxy/Caddyfile for domain: $domain" -ForegroundColor Green
}

Write-Host ""
Write-Host "Environment switched to: $Env" -ForegroundColor Green
Write-Host ""
Write-Host "Configuration:"
Write-Host "  Domain: $domain"
if ($Env -eq "local") {
    Write-Host "  URL: http://localhost"
} else {
    Write-Host "  URL: https://dev.makapix.club"
}
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Update GitHub OAuth credentials in .env if needed"
Write-Host "  2. Run: docker compose down"
Write-Host "  3. Run: docker compose up -d"
Write-Host ""
Write-Host "GitHub App Configuration:"
Write-Host "  - OAuth App: https://github.com/settings/applications/new"
Write-Host "  - GitHub App: https://github.com/settings/apps/new"
