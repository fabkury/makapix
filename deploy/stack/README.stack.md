# Makapix Compose stack

The stack uses `docker-compose.yml` together with an environment overlay, an environment file, and a Compose project name. Run Make commands from the repository root so all four are selected consistently.

- [Deployment and operations](../../docs/deployment.md): fresh-host prerequisites, environment configuration, service-specific commands, backups, and recovery.
- [Development](../../docs/development.md): development helper, tests, migrations, and contribution workflow.
- [Architecture](../../docs/architecture.md): service relationships.

## Common commands

From `/opt/makapix` for production, or `/opt/makapix-dev` for development:

```bash
make ps
make logs-api
make rebuild
```

`make rebuild` builds first and then recreates changed services. `make deploy` also pulls the environment's branch. Bare `docker compose up` or `docker compose exec` does not supply the required overlay/project settings; use the helpers in the linked guides for service-specific work.

## Artwork serving

Caddy serves vault files directly from read-only mounts using site blocks in [`caddy/Caddyfile.global`](caddy/Caddyfile.global). The `vault` containers are placeholders; no HTTP server runs inside them.

Both HTTP and HTTPS are available on the vault subdomains. Websites should use HTTPS. New players should use the `art_url` supplied by the API. Example:

```text
https://vault.makapix.club/21/32/{storage_key}.png
```

The shard path is opaque and may have a different depth for older files. The legacy `/api/vault/...` FastAPI mount has been removed; use the vault subdomain.

Caddy is shared and owned by the production stack. Changes to the global configuration or proxy labels must be applied through that stack. See the deployment guide before changing routing or certificates.
