# Alternative Architectures

This document explores alternative approaches to achieving development/staging environments on a single VPS, comparing their tradeoffs against the proposed dual-environment architecture.

---

## Alternative A: Shared Services with Separate Databases

### Description

Run a single set of services (Caddy, MQTT, Redis) but separate databases and vault storage per environment.

```
┌─────────────────────────────────────────────────┐
│                    Caddy                        │
│  makapix.club → api-prod, web-prod              │
│  dev.makapix.club → api-dev, web-dev            │
└───────────────────┬─────────────────────────────┘
                    │
    ┌───────────────┼───────────────┐
    │               │               │
┌───▼───┐      ┌───▼───┐      ┌────▼────┐
│api-prod│     │api-dev│      │  MQTT   │ (shared)
└───┬───┘      └───┬───┘      └─────────┘
    │               │
┌───▼───┐      ┌───▼───┐
│db-prod│      │db-dev │ (separate databases)
└───────┘      └───────┘
```

### Tradeoffs

| Aspect | Advantage | Disadvantage |
|--------|-----------|--------------|
| Resource usage | Fewer containers, less memory | N/A |
| Isolation | Database separation | Shared Redis could leak cached data |
| Complexity | Simpler Caddy config | MQTT topic collision risk |
| MQTT | Single broker to manage | Needs topic namespacing |
| Vault | Can share vault with subdirectories | Accidental cross-environment file access |

### When to Choose

- When VPS memory is constrained
- When MQTT isolation isn't critical
- When vault files can safely be shared

---

## Alternative B: Docker Compose Profiles

### Description

Use Docker Compose profiles to toggle between environments on the same stack.

```yaml
services:
  api:
    profiles: ["prod"]
    environment:
      - DB_DATABASE=makapix

  api-dev:
    profiles: ["dev"]
    environment:
      - DB_DATABASE=makapix_dev
```

**Usage:**
```bash
docker compose --profile prod up -d    # Start production
docker compose --profile dev up -d     # Start development
```

### Tradeoffs

| Aspect | Advantage | Disadvantage |
|--------|-----------|--------------|
| Simplicity | Single compose file | Only one environment at a time |
| Resource usage | Full resources for active env | Cannot run both simultaneously |
| Testing | Clean environment switches | No parallel testing |
| Deployment | Clear separation | "Flip" requires downtime |

### When to Choose

- When only one environment needs to run at a time
- When developers don't need parallel access
- For simple staging/production toggle

---

## Alternative C: Branch-Based Deployments

### Description

Use Git branches to manage environments. Production runs `main`, development runs `develop`.

```
/opt/makapix-prod/     (clone of main branch)
/opt/makapix-dev/      (clone of develop branch)
```

Each has its own docker-compose stack.

### Tradeoffs

| Aspect | Advantage | Disadvantage |
|--------|-----------|--------------|
| Code isolation | Complete separation | Disk space for two clones |
| Git workflow | Matches branch strategy | Merge conflicts affect both |
| Configuration | Independent .env files | Configuration drift |
| Deployment | `git pull && rebuild` per env | Manual coordination |

### When to Choose

- When development and production code differs significantly
- When feature branches need isolated testing
- When you want complete independence

---

## Alternative D: Port-Based Environment Separation

### Description

Instead of subdomains, use different ports for each environment.

```
https://makapix.club/        → Production (port 443)
https://makapix.club:8443/   → Development (port 8443)
```

### Tradeoffs

| Aspect | Advantage | Disadvantage |
|--------|-----------|--------------|
| DNS | No additional DNS records | Non-standard URLs |
| Certificates | Single wildcard cert | Port may be blocked by firewalls |
| Simplicity | Minimal Caddy config | Confusing for users |
| Security | Can IP-restrict dev port | Exposes port to internet |

### When to Choose

- When subdomain DNS is problematic
- For quick temporary testing
- When developer access is IP-restricted anyway

---

## Alternative E: Namespace-Based Isolation (Single Database)

### Description

Use database schemas (PostgreSQL namespaces) instead of separate databases.

```sql
CREATE SCHEMA production;
CREATE SCHEMA development;

SET search_path TO production;  -- For prod API
SET search_path TO development; -- For dev API
```

### Tradeoffs

| Aspect | Advantage | Disadvantage |
|--------|-----------|--------------|
| Resource usage | Single PostgreSQL instance | Shared connection pool |
| Data sampling | Can COPY between schemas | Complex FK handling |
| Migrations | Must run on both schemas | Schema drift possible |
| Isolation | Logical separation | Same database, same users |

### When to Choose

- When database memory is the primary constraint
- When cross-environment queries are needed
- For simpler backup/restore

---

## Alternative F: Container-Level Resource Limits Only

### Description

Run both environments as proposed, but with strict cgroup resource limits to prevent EB from impacting EA.

```yaml
services:
  api-dev:
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 512M
        reservations:
          memory: 256M
```

### Tradeoffs

| Aspect | Advantage | Disadvantage |
|--------|-----------|--------------|
| Protection | EA protected from EB spikes | EB performance degraded |
| Simplicity | Standard Docker feature | Requires tuning |
| Monitoring | Clear resource boundaries | May mask real issues |

### When to Choose

- As an enhancement to any dual-environment approach
- When EA stability is paramount
- When EB performance is less critical

---

## Alternative G: Snapshot-Based Testing

### Description

Instead of a running development environment, create database snapshots for testing.

```bash
# Create snapshot from production
pg_dump makapix > snapshot.sql

# Restore to local development
psql makapix_test < snapshot.sql

# Run tests, discard
dropdb makapix_test
```

### Tradeoffs

| Aspect | Advantage | Disadvantage |
|--------|-----------|--------------|
| Resource usage | No persistent dev environment | Manual snapshot management |
| Data freshness | Point-in-time snapshots | No live development URL |
| Testing | Full production data available | No persistent staging site |
| Workflow | CI/CD friendly | Developers can't browse dev site |

### When to Choose

- When primary need is migration testing, not UI testing
- For CI/CD pipeline integration
- When developers don't need persistent dev access

---

## Alternative H: Feature Flags Instead of Environments

### Description

Deploy everything to production, but gate new features behind flags.

```python
if feature_flags.is_enabled("new_upload_flow", user):
    return new_upload_handler()
else:
    return legacy_upload_handler()
```

### Tradeoffs

| Aspect | Advantage | Disadvantage |
|--------|-----------|--------------|
| Simplicity | Single environment | Feature flag complexity |
| Testing | Test in production | Risk of flag misconfig |
| Rollout | Gradual rollout possible | Technical debt accumulates |
| Database | No separate database | Schema changes still risky |

### When to Choose

- When features don't require schema changes
- For A/B testing and gradual rollouts
- When migration risk is low

---

## Comparison Matrix

| Alternative | Parallel Run | Data Isolation | Resource Efficiency | Schema Testing | Implementation Complexity |
|-------------|--------------|----------------|---------------------|----------------|---------------------------|
| **Proposed (EB/EA)** | Yes | Full | Medium | Yes | High |
| **A: Shared Services** | Yes | Database only | High | Yes | Medium |
| **B: Profiles** | No | Full | High | Yes | Low |
| **C: Branch-Based** | Yes | Full | Low | Yes | Medium |
| **D: Port-Based** | Yes | Full | Medium | Yes | Low |
| **E: Schema-Based** | Yes | Schema-level | Very High | Yes | Medium |
| **F: Resource Limits** | Yes | Full | Medium | Yes | High |
| **G: Snapshots** | No | Full | Very High | Yes | Medium |
| **H: Feature Flags** | N/A | None | Very High | No | Medium |

---

## Recommendations by Use Case

### If primary goal is migration testing:
→ **Alternative G: Snapshot-Based Testing** + CI integration

### If primary goal is staging site for stakeholders:
→ **Proposed dual-environment** or **Alternative D: Port-Based**

### If memory is severely constrained:
→ **Alternative E: Schema-Based** or **Alternative B: Profiles**

### If development workflow is the priority:
→ **Alternative C: Branch-Based** with independent stacks

### For lowest complexity:
→ **Alternative A: Shared Services** with topic namespacing

---

## Hybrid Approach

A practical implementation might combine several alternatives:

1. **Proposed architecture** (full dual-environment) for staging
2. **Resource limits (F)** to protect production
3. **Snapshots (G)** for CI/CD testing
4. **Feature flags (H)** for low-risk features

This provides flexibility while managing risk and resource constraints.
