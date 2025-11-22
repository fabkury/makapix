# Migration Guide: Old Stack to Monorepo Structure

This guide helps you migrate from the old `/opt/makapix-stack` setup to the new monorepo structure.

## What Changed

- CTA site moved from `/opt/makapix-cta` → `apps/cta/` (in repo)
- Stack config moved from `/opt/makapix-stack` → `deploy/stack/` (in repo)
- All paths are now relative to the monorepo root

## Migration Steps

### 1. Backup Current Setup

```bash
# Backup the current .env file
cp /opt/makapix-stack/.env /opt/makapix/deploy/stack/.env

# Backup current stats
cp /opt/makapix-stack/cta-stats.csv /opt/makapix/deploy/stack/cta-stats.csv 2>/dev/null || true
```

### 2. Stop Current Services

```bash
cd /opt/makapix-stack
docker compose down
```

### 3. Verify New Structure

```bash
cd /opt/makapix/deploy/stack
docker compose config  # Should validate without errors
```

### 4. Start Services from New Location

```bash
cd /opt/makapix/deploy/stack
docker compose up -d
```

### 5. Verify Services Are Running

```bash
docker compose ps
docker logs caddy
docker logs makapix-cta
docker logs makapix-dev
```

### 6. Test Websites

- CTA: https://makapix.club
- Dev: https://dev.makapix.club

### 7. Clean Up Old Directories (After Verification)

**Only after confirming everything works:**

```bash
# Remove old directories (they're now in the repo)
rm -rf /opt/makapix-stack
rm -rf /opt/makapix-cta
```

## Rollback (If Needed)

If something goes wrong, you can rollback:

```bash
cd /opt/makapix-stack
docker compose up -d
```

Then investigate and fix issues before trying again.

