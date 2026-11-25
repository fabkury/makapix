# Deployment and Operations

Run Makapix Club on a configured Linux host using Docker Compose. The repository's standard deployment has separate production and development stacks with a shared Caddy reverse proxy.

## Environments

| Resource | Production | Development |
|----------|------------|-------------|
| Checkout | `/opt/makapix` | `/opt/makapix-dev` |
| Branch | `main` | `develop` |
| Web hostname | `makapix.club` | `development.makapix.club` |
| Vault hostname | `vault.makapix.club` | `vault-dev.makapix.club` |
| Compose project | `makapix-prod` | `makapix-dev` |
| Environment file | `deploy/stack/.env.prod` | `deploy/stack/.env.dev` |
| Database volume | `makapix_pg_data` (external) | `makapix-dev_pg_data` |
| Vault directory | `/mnt/vault-1` | `/mnt/vault-dev` |
| External MQTT mTLS port | 8883 | 8884 |

The Makefile selects production only from `/opt/makapix`; other working directories select development. It supplies the base Compose file, overlay, environment file, and project name together.

## Initial setup checklist

A fresh installation needs more than `git clone` and `make up`:

1. Install Git, GNU Make, Docker Engine, and Compose V2 on the host.
2. Clone the production checkout and, if needed, a separate `develop` checkout.
3. Configure DNS and the hostnames in Compose/Caddy for your installation. The project's public domains will not route to an unrelated host.
4. Prepare the vault directories and required external Docker resources. Inspect the `volumes` and `networks` sections of the [base Compose file](../deploy/stack/docker-compose.yml) and the environment overlay before creating them.
5. Configure all required secrets and environment variables. The templates are incomplete examples; reconcile them with Compose, API startup settings, and [security operations](security/operations.md).
6. Prepare MQTT CA, broker certificates, and configuration under `mqtt/`. See [MQTT certificates](#mqtt-certificates).
7. Validate the resolved Compose configuration, then start the production stack before development because Caddy is production-owned.
8. Verify health, HTTPS, artwork delivery, and backup monitoring before opening the service to users.

The base Compose file references `deploy/stack/.env` through service `env_file` entries; the development overlay also references `.env.dev`. `--env-file` supplies Compose variable substitution and does not remove service-level `env_file` requirements. Ensure every referenced file exists and contains the intended environment's values.

## Environment configuration

| Category | Important variables |
|----------|---------------------|
| Database | `DB_ADMIN_USER`, `DB_ADMIN_PASSWORD`, `DB_API_WORKER_USER`, `DB_API_WORKER_PASSWORD`, `DB_DATABASE` |
| Authentication | `JWT_SECRET_KEY`, token lifetimes, `WEBAUTHN_RP_ID` |
| MQTT | `MQTT_PASSWORD`, certificate paths and broker settings |
| OAuth and email | GitHub/Apple provider settings as enabled, `RESEND_API_KEY`, `RESEND_FROM_EMAIL` |
| Vault | `VAULT_LOCATION`, `VAULT_HOST_PATH`, `VAULT_PUBLIC_BASE_URL` |
| Proxy | `CADDY_DOCKER_PROXY_TAG`, `ACME_EMAIL`, configured hostnames |
| Identifiers and analytics | `SQIDS_ALPHABET`, `MAKAPIX_IP_HASH_SALT` |

Do not change `SQIDS_ALPHABET` on an existing installation: it determines public identifiers. Keep secrets out of Git. Consult [security operations](security/operations.md) for rotation procedures.

## Service-specific commands

Run Make commands from the intended repository root. For operations not covered by Make, define a helper for that environment. This example targets production:

```bash
cd /opt/makapix
mpxprod() {
  docker compose --project-directory deploy/stack \
    -f deploy/stack/docker-compose.yml \
    -f deploy/stack/docker-compose.prod.yml \
    --env-file deploy/stack/.env.prod -p makapix-prod "$@"
}
mpxprod config --quiet
make up
make ps
```

For development, use the helper in [Development](development.md). Avoid bare `docker compose` commands that omit the overlay or project name.

## Services and networking

| Service | Purpose |
|---------|---------|
| `db` | PostgreSQL database |
| `cache` | Redis application cache and rate-limit state |
| `broker` | Separate Redis instance for Celery queues/results; uses `noeviction` |
| `mqtt` | Mosquitto for player messaging |
| `api` | FastAPI backend |
| `worker` | Celery worker and Beat scheduler |
| `web` | Next.js frontend |
| `caddy` | Shared reverse proxy, HTTPS, and vault file serving |
| `vault`, `www-redirect` | Placeholder containers used by the stack; the vault is served by Caddy |
| `redis` | Edge Redis service |

`internal` separates each environment's backend services. `caddy_net` is shared so the production-owned proxy can reach both environments. Caddy serves the vault directories through explicit site blocks in `deploy/stack/caddy/Caddyfile.global`; application routing also uses Docker labels.

| Host ports | Exposure |
|------------|----------|
| 80, 443 | Public HTTP/HTTPS through Caddy |
| 8883 / 8884 | Public MQTT with mTLS, production / development |
| 1883 / 1884 | Loopback-only plain MQTT, production / development |
| 5432 / 5433 | Loopback-only PostgreSQL, production / development |

Caddy is disabled in the development overlay. Proxy configuration changes take effect through the production checkout, not by restarting a development Caddy service.

## MQTT certificates

The tooling in `mqtt/config/scripts/gen-certs.sh` generates CA and broker material under `mqtt/certs/`. On an established installation, preserve the existing CA and follow the renewal procedure rather than regenerating trust material as a routine fix.

The API issues player client certificates during registration. Default validity is 1095 days, with renewal available within 90 days of expiry or after expiry. See [player certificate renewal](player/registration.md#certificate-renewal). Celery maintains the certificate revocation list (CRL).

## Backups

Automated backup tooling lives in [`deploy/backup/`](../deploy/backup/README.md). It dumps the production database and backs up the vault and irreplaceable configuration/secrets with encrypted restic snapshots to Backblaze B2. The installer schedules the job for **10:30 UTC daily**, with monitoring and periodic retention/integrity checks.

Repository tooling does not prove a particular host has a healthy backup. Check installed scheduling, job logs, recent snapshots, and monitoring:

```bash
sudo makapix-restic snapshots
journalctl -t makapix-backup
```

Use the [restore runbook](backups/RESTORE.md) for recovery and drills. Do not restore directly over a live database as an exploratory check. Provider VM backups do not substitute for backups of separately attached vault volumes.

## Updates and rollback

Run the application checks in development before merging or deploying; see [Development](development.md#development-to-production).

```bash
cd /opt/makapix
make deploy
```

`make deploy` pulls `main`, builds images **before** touching running services, then recreates changed containers and prunes build cache with reserved space. A failed build leaves the existing stack running. API startup applies migrations.

For rollback, inspect the deployed commit and migrations first. Rebuilding an earlier commit restores code only; it does not undo database changes. Use a compatible migration/recovery plan and the backup runbook when data restoration is needed. Avoid `make deploy` while testing an older checkout because it pulls the branch again.

## Monitoring and troubleshooting

With the production helper defined:

```bash
make ps
mpxprod logs --tail=100 api worker mqtt
curl https://makapix.club/api/health
df -h
docker system df
docker stats --no-stream
mpxprod exec cache redis-cli INFO memory
mpxprod exec broker redis-cli INFO memory
```

For database inspection, open `make shell-db` and run read-only queries such as:

```sql
SELECT pg_size_pretty(pg_database_size(current_database()));
SELECT count(*) FROM pg_stat_activity;
```

- **Startup failure:** inspect missing variables, required files, mounts, and port conflicts before rebuilding.
- **TLS failure:** inspect the production Caddy logs and DNS. Restarting Caddy is not a forced certificate renewal.
- **Disk pressure:** inspect vault growth, Docker images/build cache, and logs. Do not use volume-pruning commands as a generic repair; volumes can contain data.
- **Player connection failure:** check the correct environment's MQTT port, certificate validity, CA trust, and broker logs.
- **Memory pressure:** inspect actual container usage and overlay limits before changing resource allocation.

See [scheduled tasks](reference/scheduled-tasks.md) for maintenance timing and [Architecture](architecture.md) for data flow.
