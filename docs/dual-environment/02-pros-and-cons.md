# Dual-Environment Architecture: Pros and Cons

This document analyzes the proposed architecture where two environments (EA: production, EB: development) run on the same VPS.

## Proposed Architecture Summary

- **EA (Production)**: `https://makapix.club/` - Live site, real users
- **EB (Development)**: `https://development.makapix.club/` - Dev/staging site
- Both share the same VPS but have completely isolated:
  - Databases (EB gets 10% sample of EA data)
  - Vault storage (separate directories)
  - Docker networks
  - Container instances

## Pros

### 1. Realistic Testing Environment

**Benefit**: EB mirrors production closely since it runs on identical hardware and OS.

- Same kernel, CPU architecture, memory constraints
- Same network latency characteristics
- Issues caused by production-specific conditions are more likely to surface
- Database performance characteristics match production

### 2. Cost Efficiency

**Benefit**: No additional infrastructure costs.

- Single VPS hosts both environments
- No need for separate cloud instances, load balancers, or CDN configurations
- Shared TLS certificate management via Caddy
- Reduced operational overhead (one server to maintain)

### 3. Simplified Deployment Pipeline

**Benefit**: "Flip the switch" deployment from EB to EA.

- Code is already on the same machine
- Database migrations tested on realistic data before production
- File changes can be applied atomically
- Rollback is straightforward (switch back)

### 4. Representative Sample Data

**Benefit**: 10% user cohort provides realistic test scenarios.

- Real content variety (images, comments, reactions)
- Actual relationship patterns (follows, notifications)
- Edge cases that synthetic data wouldn't capture
- Statistics and analytics behave realistically

### 5. Reduced Context Switching

**Benefit**: Developers work with familiar production-like data.

- No need to maintain separate mock data sets
- Real user handles and content for testing
- Actual file sizes and formats for performance testing

## Cons

### 1. Resource Contention

**Risk**: EB competes with EA for CPU, memory, disk I/O.

| Resource | Impact |
|----------|--------|
| CPU | EB background tasks could spike during EA peak hours |
| Memory | Both PostgreSQL instances compete for buffer cache |
| Disk I/O | Database writes, file uploads, log rotation |
| Network | Same network interface for all traffic |

**Mitigation strategies**:
- Use cgroups/Docker resource limits to cap EB
- Schedule EB-intensive operations during off-peak hours
- Monitor resource usage and set alerts

### 2. Single Point of Failure

**Risk**: VPS failure affects both environments.

- Hardware failure takes down production AND development
- OS updates require coordinated downtime
- Disk full condition affects both databases
- Network outage impacts everything

**Mitigation strategies**:
- Regular backups to external storage
- Consider read replica on separate hardware for DR
- Automated monitoring and alerting

### 3. Data Sampling Complexity

**Risk**: 10% sample may not capture all edge cases.

| Challenge | Description |
|-----------|-------------|
| Orphaned references | Comments from users not in sample set |
| Incomplete relationships | Partial follow graphs |
| Statistics skew | Aggregate stats don't match reality |
| File synchronization | Need to copy corresponding artwork files |

**Mitigation strategies**:
- Include users referenced by the sampled users
- Accept some data inconsistency in EB
- Document known limitations for developers

### 4. Production Data in Non-Production Environment

**Risk**: Privacy and security concerns.

- Real email addresses in development database
- Actual content (some may be private/unlisted)
- Authentication tokens and session data
- GDPR/privacy compliance considerations

**Mitigation strategies**:
- Anonymize emails during sample copy (user123@dev.local)
- Regenerate all authentication tokens
- Consider excluding private/unlisted content
- Document data handling in privacy policy

### 5. Configuration Drift

**Risk**: EB and EA configurations diverge over time.

- Different .env files can accumulate differences
- Database schema may drift if migrations applied inconsistently
- Docker image versions might differ
- MQTT topics or certificate handling could diverge

**Mitigation strategies**:
- Use environment-specific compose overrides, not separate files
- Script the "flip" process to ensure consistency
- Version control all configuration

### 6. Complexity in Database Migration Testing

**Risk**: Migrations that work on EB sample may fail on full EA data.

- 10% sample might not include problematic rows
- Performance characteristics differ (smaller dataset)
- Constraint violations may only appear at scale
- Indexes behave differently with different data volumes

**Mitigation strategies**:
- Test migrations on larger samples before production
- Have rollback plans for every migration
- Monitor migration execution time

### 7. MQTT/Real-time Isolation Challenges

**Risk**: Topic namespacing and certificate management complexity.

- Need separate MQTT brokers or topic prefixes
- Player devices might connect to wrong environment
- WebSocket connections need proper routing
- Certificate authorities and revocation lists

**Mitigation strategies**:
- Use environment prefix in topics (`dev/makapix/...` vs `makapix/...`)
- Separate MQTT containers with different ports
- Careful subdomain-based routing

### 8. Vault Storage Duplication

**Risk**: Disk space doubles for artwork storage.

- All sampled users' artwork must be copied
- Original and upscaled variants both needed
- No deduplication possible (different directories)
- Sync must be repeated on each sample refresh

**Mitigation strategies**:
- Use filesystem-level deduplication (btrfs, ZFS)
- Only copy files for sampled posts
- Consider symbolic links for read-only access (with caveats)

### 9. OAuth/External Service Configuration

**Risk**: External services may not support multiple environments.

- GitHub OAuth needs separate app registration
- Email service (Resend) may have rate limits
- Future integrations face same issue

**Mitigation strategies**:
- Register separate OAuth apps for EB
- Use dedicated email domain/sender for EB
- Document all external service dependencies

### 10. Cognitive Load

**Risk**: Developers must keep environments straight.

- Which database am I querying?
- Which docker-compose project is running?
- Which .env file is active?
- Accidental commands against wrong environment

**Mitigation strategies**:
- Clear naming conventions
- Different shell prompts per environment
- Confirmation prompts for destructive operations
- Visual indicators in development UI

## Summary Matrix

| Aspect | Pro | Con |
|--------|-----|-----|
| Cost | Single VPS, no extra infra | - |
| Realism | Same hardware, real data | Resource contention |
| Testing | Migrations tested on realistic data | 10% sample may miss edge cases |
| Deployment | Simple "flip" process | Configuration drift risk |
| Security | - | Production data in dev |
| Reliability | - | Single point of failure |
| Complexity | Familiar production-like environment | MQTT, OAuth, vault complexity |
| Storage | - | Doubled disk usage |

## Recommendation

The dual-environment architecture is **viable** for a single-VPS project like Makapix, particularly given the cost constraints. However, success depends on:

1. **Strict resource limits** for EB to protect EA
2. **Thorough anonymization** of production data
3. **Automated sampling scripts** with proper FK handling
4. **Clear operational procedures** to prevent environment confusion
5. **External backup strategy** to mitigate single-point-of-failure risk

The trade-offs are acceptable for a project of this scale, but the team should be aware of the risks and plan mitigation strategies before implementation.
