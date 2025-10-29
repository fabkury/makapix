# Makapix Development Helper Script (PowerShell equivalent of Makefile)
# Usage: .\dev.ps1 <command>

param(
    [Parameter(Position=0)]
    [string]$Command = "help"
)

function Show-Help {
    Write-Host "Makapix Development Commands" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Environment Management:"
    Write-Host "  .\dev.ps1 local          - Switch to local development (localhost)"
    Write-Host "  .\dev.ps1 remote         - Switch to remote development (dev.makapix.club)"
    Write-Host ""
    Write-Host "Docker Commands:"
    Write-Host "  .\dev.ps1 up             - Start all services"
    Write-Host "  .\dev.ps1 down           - Stop all services"
    Write-Host "  .\dev.ps1 restart        - Restart all services"
    Write-Host "  .\dev.ps1 logs           - Show logs for all services"
    Write-Host "  .\dev.ps1 logs-api       - Show logs for API service"
    Write-Host "  .\dev.ps1 logs-web       - Show logs for web service"
    Write-Host ""
    Write-Host "Development:"
    Write-Host "  .\dev.ps1 test           - Run API tests"
    Write-Host "  .\dev.ps1 shell-api      - Open shell in API container"
    Write-Host "  .\dev.ps1 shell-db       - Open PostgreSQL shell"
    Write-Host ""
    Write-Host "Status:"
    Write-Host "  .\dev.ps1 status         - Show current environment and services"
    Write-Host ""
    Write-Host "Cleanup:"
    Write-Host "  .\dev.ps1 clean          - Remove all containers, volumes, and generated files"
}

function Switch-ToLocal {
    & powershell -ExecutionPolicy Bypass -File ./scripts/switch-env.ps1 local
}

function Switch-ToRemote {
    & powershell -ExecutionPolicy Bypass -File ./scripts/switch-env.ps1 remote
}

function Start-Services {
    docker compose up -d
}

function Stop-Services {
    docker compose down
}

function Restart-Services {
    docker compose restart
}

function Show-Logs {
    docker compose logs -f
}

function Show-ApiLogs {
    docker compose logs -f api
}

function Show-WebLogs {
    docker compose logs -f web
}

function Show-ProxyLogs {
    docker compose logs -f proxy
}

function Run-Tests {
    docker compose run --rm api-test
}

function Open-ApiShell {
    docker compose exec api bash
}

function Open-DbShell {
    docker compose exec db psql -U makapix -d makapix
}

function Show-Status {
    Write-Host "Current environment:" -ForegroundColor Cyan
    if (Test-Path .env) {
        $env = Select-String -Path .env -Pattern "^ENVIRONMENT=" | ForEach-Object { $_.Line }
        if ($env) {
            Write-Host "  $env" -ForegroundColor Green
        } else {
            Write-Host "  Unknown (ENVIRONMENT not set in .env)" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  No .env file found" -ForegroundColor Red
    }
    Write-Host ""
    Write-Host "Docker services:" -ForegroundColor Cyan
    docker compose ps
}

function Clean-All {
    Write-Host "Cleaning up containers, volumes, and generated files..." -ForegroundColor Yellow
    docker compose down -v
    if (Test-Path .env) { Remove-Item .env }
    if (Test-Path docker-compose.override.yml) { Remove-Item docker-compose.override.yml }
    if (Test-Path proxy/Caddyfile) { Remove-Item proxy/Caddyfile }
    Write-Host "Cleaned up containers, volumes, and generated files" -ForegroundColor Green
}

# Command router
switch ($Command.ToLower()) {
    "help" { Show-Help }
    "local" { Switch-ToLocal }
    "remote" { Switch-ToRemote }
    "up" { Start-Services }
    "down" { Stop-Services }
    "restart" { Restart-Services }
    "logs" { Show-Logs }
    "logs-api" { Show-ApiLogs }
    "logs-web" { Show-WebLogs }
    "logs-proxy" { Show-ProxyLogs }
    "test" { Run-Tests }
    "shell-api" { Open-ApiShell }
    "shell-db" { Open-DbShell }
    "status" { Show-Status }
    "clean" { Clean-All }
    default {
        Write-Host "Unknown command: $Command" -ForegroundColor Red
        Write-Host ""
        Show-Help
        exit 1
    }
}

