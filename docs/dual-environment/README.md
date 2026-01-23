# Dual-Environment Architecture Documentation

This folder contains analysis and planning documents for implementing a dual-environment architecture for Makapix, where both production (EA) and development (EB) environments run on a single VPS.

## Documents

### [01-current-architecture.md](./01-current-architecture.md)
Overview of the existing Makapix infrastructure including services, networks, databases, and configuration.

### [02-pros-and-cons.md](./02-pros-and-cons.md)
Detailed analysis of advantages and disadvantages of the proposed dual-environment approach.

### [03-alternative-architectures.md](./03-alternative-architectures.md)
Exploration of alternative approaches with tradeoff comparisons, including:
- Shared services with separate databases
- Docker Compose profiles
- Branch-based deployments
- Port-based separation
- Schema-based isolation
- Feature flags

### [04-technical-implementation.md](./04-technical-implementation.md)
Technical details for implementation including:
- Docker Compose structure
- Network isolation
- Data sampling strategy
- Vault file synchronization
- Caddy configuration
- MQTT isolation
- "Flip the switch" deployment process

## Proposed Architecture Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                         Single VPS                               │
├─────────────────────────────┬───────────────────────────────────┤
│     EA (Production)         │        EB (Development)            │
│   makapix.club              │   development.makapix.club         │
├─────────────────────────────┼───────────────────────────────────┤
│ • makapix-prod-api          │ • makapix-dev-api                  │
│ • makapix-prod-web          │ • makapix-dev-web                  │
│ • makapix-prod-db           │ • makapix-dev-db                   │
│ • makapix-prod-worker       │ • makapix-dev-worker               │
│ • makapix-prod-mqtt         │ • makapix-dev-mqtt                 │
│ • /mnt/vault-1/             │ • /mnt/vault-dev/                  │
├─────────────────────────────┴───────────────────────────────────┤
│                    Shared: Caddy (routing), caddy_net            │
└─────────────────────────────────────────────────────────────────┘
```

## Key Decisions Required

1. **Container naming strategy**: Environment prefix vs separate compose projects
2. **Database approach**: Separate containers vs single PostgreSQL with multiple databases
3. **MQTT isolation**: Separate brokers vs topic namespacing
4. **Data sampling frequency**: On-demand vs scheduled
5. **Resource allocation**: How much to reserve for development

## Intended Workflow

1. EB database is populated with 10% sample of EA users and their content
2. Developers implement features and test migrations in EB
3. Testing occurs at `https://development.makapix.club/`
4. When ready, code is deployed to EA with production migrations

## Next Steps

1. Review this documentation
2. Make decisions on key architectural choices
3. Create implementation tasks
4. Implement in phases:
   - Phase 1: Docker Compose restructuring
   - Phase 2: Data sampling tooling
   - Phase 3: Caddy routing for subdomains
   - Phase 4: MQTT and OAuth configuration
   - Phase 5: Documentation and operational procedures
