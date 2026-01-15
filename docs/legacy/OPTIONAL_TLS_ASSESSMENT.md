# Optional TLS Implementation Assessment for Makapix Club

**Date:** 2025-12-17  
**Version:** 1.0  
**Status:** Awaiting Approval

## Executive Summary

This document assesses the feasibility of implementing **optional TLS** for both MQTT connections and HTTPS downloads in Makapix Club. The system would support:

1. **MQTT connections**: Client can choose TLS (port 8883) or non-TLS (port 1883)
2. **Downloads**: Client can choose HTTPS or HTTP

**Bottom Line:** Implementation is feasible with moderate effort. The main challenges are security considerations, client configuration complexity, and maintaining backward compatibility.

---

## Table of Contents

1. [Current Implementation Analysis](#1-current-implementation-analysis)
2. [Proposed Architecture](#2-proposed-architecture)
3. [Implementation Approach](#3-implementation-approach)
4. [Security Considerations](#4-security-considerations)
5. [Open Questions](#5-open-questions)
6. [Risk Assessment](#6-risk-assessment)
7. [Effort Estimation](#7-effort-estimation)
8. [Recommendations](#8-recommendations)

---

## 1. Current Implementation Analysis

### 1.1 MQTT Current State

**Current Architecture:**

```
Mosquitto MQTT Broker
├── Port 1883: Internal (password auth, no TLS) - Docker network only
├── Port 8883: mTLS (client certificates) - External, for physical players
└── Port 9001: WebSocket (password auth, no TLS) - External, for web clients
```

**Current Configuration (`mqtt/mosquitto.conf`):**
- Port 1883: Internal API server communication (no TLS, network isolation)
- Port 8883: mTLS with client certificates (CN = player_key)
- Port 9001: WebSocket for browsers (currently no TLS)

**Current Components:**

1. **Mosquitto Configuration** (`mqtt/mosquitto.conf`)
   - Three listeners configured
   - ACL file for permissions
   - Password file for authentication
   - Certificate files for mTLS

2. **API Server Publisher** (`api/app/mqtt/publisher.py`)
   - Connects to internal port 1883
   - Uses `MQTT_TLS_ENABLED` environment variable
   - Supports optional TLS via `MQTT_CA_FILE`

3. **MQTT Bootstrap Endpoint** (`api/app/routers/mqtt.py`)
   - Returns connection info to clients
   - Currently hardcoded: `tls=False` for WebSocket

4. **Web Client** (`web/src/hooks/mqtt-client.ts`)
   - Connects via WebSocket to port 9001
   - Uses `NEXT_PUBLIC_MQTT_WS_URL` (ws:// or wss://)

### 1.2 Downloads Current State

**Current Architecture:**

All downloads go through HTTPS via Caddy reverse proxy:

```
Client Request (HTTPS)
    ↓
Caddy Reverse Proxy (TLS termination)
    ↓
FastAPI (HTTP internally)
    ↓
File Response from Vault
```

**Current Endpoints:**

1. `/d/{public_sqid}` - Download by public Sqids ID
2. `/download/{storage_key}` - Download by UUID (legacy)

**Current Implementation (`api/app/routers/artwork.py`):**
- Uses FastAPI `FileResponse`
- Direct file serving from vault
- No TLS awareness (relies on reverse proxy)

**Artwork URL Format:**
- Relative: `/api/vault/a1/b2/c3/{uuid}.png`
- Clients construct full URLs: `https://dev.makapix.club/api/vault/...`

---

## 2. Proposed Architecture

### 2.1 MQTT Optional TLS

**Option A: Dual Port Configuration (Recommended)**

```
Mosquitto MQTT Broker
├── Port 1883: Non-TLS (password auth) - Internal and optional external
├── Port 8883: TLS with optional mTLS
│   ├── Server TLS certificate (always required)
│   └── Client certificates (optional based on configuration)
└── Port 9001: WebSocket (supports both ws:// and wss://)
    └── Client chooses protocol based on URL scheme
```

**Option B: Single Port with STARTTLS**
- More complex to implement
- Less clear to clients
- Not recommended for this use case

**Recommendation: Option A** - Clearer separation, easier to configure and troubleshoot

### 2.2 Download Optional TLS

**Option A: Separate HTTP/HTTPS Ports (Infrastructure Change)**

```
Caddy Reverse Proxy
├── Port 80: HTTP (no TLS) → FastAPI
└── Port 443: HTTPS (TLS) → FastAPI
```

**Option B: Client URL Choice (Application Level)**

Clients construct URLs based on preference:
- HTTPS: `https://dev.makapix.club/d/{sqid}`
- HTTP: `http://dev.makapix.club/d/{sqid}`

**Option C: API Provides Both URLs**

Bootstrap/metadata endpoints return both:
```json
{
  "art_url_secure": "https://dev.makapix.club/api/vault/...",
  "art_url_insecure": "http://dev.makapix.club/api/vault/..."
}
```

**Recommendation: Option C** - Most flexible, backward compatible, infrastructure-agnostic

---

## 3. Implementation Approach

### 3.1 MQTT Changes

#### Phase 1: Mosquitto Configuration

**File:** `mqtt/mosquitto.conf`

```conf
# Internal listener (no TLS, within docker network only)
listener 1883 0.0.0.0
allow_anonymous false
acl_file /mosquitto/config/acls
password_file /mosquitto/config/passwords

# External non-TLS listener (optional, for development/testing)
# Disabled by default in production
# listener 1884 0.0.0.0
# allow_anonymous false
# acl_file /mosquitto/config/acls
# password_file /mosquitto/config/passwords

# TLS listener (server cert + optional client certs)
listener 8883 0.0.0.0
cafile /mosquitto/certs/ca.crt
certfile /mosquitto/certs/server.crt
keyfile /mosquitto/certs/server.key
# Make client certificates optional
require_certificate ${MQTT_REQUIRE_CLIENT_CERT:-true}
use_identity_as_username ${MQTT_USE_CERT_USERNAME:-true}
tls_version tlsv1.2
crlfile /mosquitto/certs/crl.pem

# WebSocket listener (supports ws:// and wss://)
listener 9001 0.0.0.0
protocol websockets
# Optional TLS for WebSocket
# If set, enables wss://
# cafile /mosquitto/certs/ca.crt
# certfile /mosquitto/certs/server.crt
# keyfile /mosquitto/certs/server.key
```

**Environment Variables to Add:**
- `MQTT_REQUIRE_CLIENT_CERT` - Default: `true` (can be set to `false`)
- `MQTT_USE_CERT_USERNAME` - Default: `true`
- `MQTT_ENABLE_EXTERNAL_NON_TLS` - Default: `false`

#### Phase 2: Bootstrap Endpoint Enhancement

**File:** `api/app/schemas.py`

```python
class MQTTBootstrap(BaseModel):
    """MQTT broker bootstrap info with connection options."""
    
    # Secure connection (preferred)
    host: str
    port: int
    tls: bool
    
    # Insecure connection (optional fallback)
    insecure_host: str | None = None
    insecure_port: int | None = None
    insecure_tls: bool = False
    
    # WebSocket options
    ws_url: str | None = None  # wss:// URL
    ws_url_insecure: str | None = None  # ws:// URL
    
    topics: dict[str, str]  # {new_posts: "posts/new/#"}
```

**File:** `api/app/routers/mqtt.py`

```python
@router.get("/mqtt/bootstrap", response_model=schemas.MQTTBootstrap)
def mqtt_bootstrap() -> schemas.MQTTBootstrap:
    """
    MQTT broker bootstrap info with secure and insecure options.
    """
    public_host = os.getenv("MQTT_PUBLIC_HOST", "dev.makapix.club")
    
    # Secure connection (default)
    secure_port = int(os.getenv("MQTT_PUBLIC_PORT", "8883"))
    
    # Insecure connection (optional)
    insecure_enabled = os.getenv("MQTT_ENABLE_EXTERNAL_NON_TLS", "false").lower() == "true"
    insecure_port = int(os.getenv("MQTT_PUBLIC_INSECURE_PORT", "1884")) if insecure_enabled else None
    
    # WebSocket options
    ws_port = int(os.getenv("MQTT_WS_PORT", "9001"))
    ws_tls_enabled = os.getenv("MQTT_WS_TLS_ENABLED", "false").lower() == "true"
    
    return schemas.MQTTBootstrap(
        host=public_host,
        port=secure_port,
        tls=True,
        insecure_host=public_host if insecure_enabled else None,
        insecure_port=insecure_port,
        insecure_tls=False,
        ws_url=f"wss://{public_host}:{ws_port}" if ws_tls_enabled else None,
        ws_url_insecure=f"ws://{public_host}:{ws_port}",
        topics={"new_posts": "posts/new/#"},
    )
```

#### Phase 3: Physical Player Support

**Documentation Updates Required:**

1. `docs/MQTT_PROTOCOL.md` - Add section on connection options
2. `docs/MQTT_PLAYER_API.md` - Document bootstrap response changes
3. `docs/PHYSICAL_PLAYER.md` - Add configuration examples

**Player Firmware Considerations:**

Players would need to:
1. Call `/mqtt/bootstrap` to get connection options
2. Choose TLS or non-TLS based on:
   - Device capability
   - Network constraints
   - Security requirements
3. Implement fallback logic (try TLS first, fall back to non-TLS)

#### Phase 4: Web Client Updates

**File:** `web/src/hooks/mqtt-client.ts`

Currently hardcoded to use `NEXT_PUBLIC_MQTT_WS_URL`. Would need to:

1. Fetch bootstrap endpoint
2. Choose ws:// or wss:// based on:
   - User preference
   - Browser capabilities
   - Environment

### 3.2 Download Changes

#### Phase 1: Schema Updates

**File:** `api/app/mqtt/schemas.py`

```python
class ArtworkInfo(BaseModel):
    """Artwork information with URL options."""
    storage_key: str
    art_url: str  # Secure URL (HTTPS) - default
    art_url_insecure: str | None = None  # Insecure URL (HTTP) - optional
    canvas: str
    width: int
    height: int
    frame_count: int
    has_transparency: bool
```

#### Phase 2: URL Generation

**File:** `api/app/vault.py` or new helper module

```python
def get_artwork_url(storage_key: UUID, extension: str, secure: bool = True) -> str:
    """
    Get artwork URL with optional security.
    
    Args:
        storage_key: UUID of the artwork
        extension: File extension
        secure: Whether to use HTTPS (True) or HTTP (False)
    
    Returns:
        Full URL to artwork
    """
    # Hash-based folder structure
    hash_value = hashlib.sha256(str(storage_key).encode()).hexdigest()
    chunk1 = hash_value[0:2]
    chunk2 = hash_value[2:4]
    chunk3 = hash_value[4:6]
    
    # Construct path
    path = f"/api/vault/{chunk1}/{chunk2}/{chunk3}/{storage_key}{extension}"
    
    # Get base URL from environment
    base_url_secure = os.getenv("BASE_URL", "https://dev.makapix.club")
    base_url_insecure = os.getenv("BASE_URL_INSECURE", "http://dev.makapix.club")
    
    base_url = base_url_secure if secure else base_url_insecure
    return f"{base_url}{path}"
```

#### Phase 3: Post Response Updates

**File:** `api/app/routers/posts.py`

Update post creation to include both URLs:

```python
# After saving to vault
art_url_secure = get_artwork_url(post.storage_key, extension, secure=True)
art_url_insecure = get_artwork_url(post.storage_key, extension, secure=False)

# Store primary (secure) URL in database
post.art_url = art_url_secure
```

#### Phase 4: MQTT Player Request Responses

**File:** `api/app/mqtt/player_requests.py`

Update `_build_post_response()` to include both URLs:

```python
return ArtworkInfo(
    storage_key=str(post.storage_key),
    art_url=post.art_url or "",  # Secure URL
    art_url_insecure=get_artwork_url(post.storage_key, extension, secure=False),
    canvas=post.canvas or "",
    width=int(post.width or 0),
    height=int(post.height or 0),
    frame_count=int(post.frame_count or 1),
    has_transparency=...,
)
```

### 3.3 Environment Configuration

**New Environment Variables:**

```bash
# MQTT Configuration
MQTT_ENABLE_EXTERNAL_NON_TLS=false  # Enable non-TLS external listener
MQTT_PUBLIC_INSECURE_PORT=1884      # Non-TLS external port
MQTT_REQUIRE_CLIENT_CERT=true       # Require client certs on TLS port
MQTT_USE_CERT_USERNAME=true         # Use CN from cert as username
MQTT_WS_TLS_ENABLED=false           # Enable TLS on WebSocket

# Download URLs
BASE_URL=https://dev.makapix.club   # Secure base URL
BASE_URL_INSECURE=http://dev.makapix.club  # Insecure base URL (optional)
```

**Template Updates:**

1. `env.local.template` - Add new variables with local defaults
2. `env.remote.template` - Add new variables with production defaults
3. `.env.example` - Document new variables

---

## 4. Security Considerations

### 4.1 MQTT Security

**Risks of Non-TLS MQTT:**

1. **Eavesdropping**: Messages can be intercepted and read
2. **Credential Theft**: Usernames/passwords sent in clear text
3. **Message Tampering**: Messages can be modified in transit
4. **Man-in-the-Middle**: Attacker can impersonate broker or client

**Mitigations:**

1. **Default to TLS**: Non-TLS should be opt-in, not default
2. **Strong Passwords**: Enforce minimum password requirements
3. **Network Isolation**: Limit non-TLS to trusted networks only
4. **Rate Limiting**: Prevent brute force attacks
5. **Monitoring**: Log all non-TLS connections
6. **Firewall Rules**: Restrict non-TLS port to specific IP ranges (if possible)

**Authentication Strategy:**

- **Port 1883 (internal)**: Password auth, network isolation
- **Port 1884 (external non-TLS)**: Password auth, ACLs, rate limiting
- **Port 8883 (TLS)**: mTLS with optional fallback to password auth
- **Port 9001 (WebSocket)**: Password auth, token-based

### 4.2 Download Security

**Risks of HTTP Downloads:**

1. **Eavesdropping**: Artwork can be intercepted
2. **Tampering**: Files can be modified in transit
3. **Cache Poisoning**: Attackers can inject malicious content

**Mitigations:**

1. **Hash Verification**: Clients should verify SHA256 hash
   - Already implemented in `expected_hash` field
   - Players should verify before displaying
2. **Content-Type Validation**: Strict MIME type checking
3. **Monitoring**: Track HTTP vs HTTPS usage
4. **Recommendations**: Encourage HTTPS in documentation

### 4.3 Production Recommendations

**For Production Environment:**

1. **Disable Non-TLS MQTT by default**
   - Only enable for specific use cases
   - Document security implications clearly

2. **Redirect HTTP to HTTPS for downloads**
   - Configure Caddy to redirect
   - Only allow HTTP for specific clients via query parameter

3. **Client Education**
   - Document when non-TLS is appropriate
   - Provide security best practices
   - Warn about risks in UI

4. **Monitoring and Alerting**
   - Log all non-TLS connections
   - Alert on unusual patterns
   - Track adoption of secure vs insecure options

---

## 5. Open Questions

### 5.1 Business/Product Questions

1. **Use Cases**: What are the specific scenarios where clients need non-TLS connections?
   - Embedded devices with limited TLS support?
   - Development/testing environments?
   - Legacy hardware?
   - Network restrictions?

2. **User Experience**: How should clients choose between TLS and non-TLS?
   - Automatic fallback?
   - Manual configuration?
   - Environment-based?
   - Performance-based?

3. **Backward Compatibility**: How do we handle existing clients?
   - Should they automatically get both options?
   - Do we need a migration period?
   - How do we communicate changes?

4. **Default Behavior**: What should be the default?
   - Always try TLS first?
   - Allow override via configuration?
   - Different defaults for different client types?

### 5.2 Technical Questions

1. **Mosquitto Configuration**: 
   - Should we use dynamic listeners (if supported)?
   - How to handle certificate rotation?
   - Should we support STARTTLS?

2. **WebSocket TLS**:
   - Should wss:// be enabled by default?
   - Does it require separate certificates?
   - How does this interact with Caddy?

3. **Download URLs**:
   - Should we always return both URLs in responses?
   - Or only when explicitly requested?
   - How does this affect caching?

4. **Performance**:
   - What is the overhead of TLS vs non-TLS?
   - Should we implement connection pooling?
   - Do we need separate rate limits?

5. **Monitoring**:
   - What metrics should we track?
   - How do we differentiate secure vs insecure usage?
   - What alerts should we configure?

### 5.3 Infrastructure Questions

1. **Firewall Rules**:
   - Should non-TLS ports be restricted by IP?
   - Do we need separate security groups?
   - How to configure on different cloud providers?

2. **Load Balancing**:
   - If we use load balancers, how do they handle:
     - TLS termination?
     - MQTT protocol?
     - WebSocket upgrades?

3. **Deployment**:
   - Blue/green deployment strategy?
   - How to test changes without impacting production?
   - Rollback plan?

---

## 6. Risk Assessment

### 6.1 Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Breaking existing clients | Medium | High | Backward compatibility, phased rollout |
| Security vulnerabilities | Medium | Critical | Default to secure, thorough testing |
| Performance degradation | Low | Medium | Load testing, monitoring |
| Configuration complexity | High | Medium | Clear documentation, validation |
| Certificate management issues | Medium | High | Automated renewal, monitoring |

### 6.2 Security Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Credential theft (non-TLS) | High | High | Strong passwords, rate limiting |
| Content tampering | Medium | High | Hash verification, monitoring |
| Man-in-the-Middle | High | Critical | Encourage TLS, client validation |
| Misconfiguration | High | High | Configuration validation, defaults |

### 6.3 Operational Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Support burden | High | Medium | Documentation, self-service tools |
| Monitoring gaps | Medium | Medium | Comprehensive metrics, alerting |
| Upgrade complexity | Medium | High | Staged rollout, rollback plan |

---

## 7. Effort Estimation

### 7.1 Development Effort

| Component | Complexity | Effort (hours) | Notes |
|-----------|------------|----------------|-------|
| Mosquitto configuration | Low | 4 | Update conf, test locally |
| Bootstrap endpoint | Low | 8 | Update schema, endpoint, tests |
| MQTT publisher updates | Low | 4 | Environment variable handling |
| Download URL generation | Medium | 8 | New helper functions, tests |
| Post creation updates | Low | 4 | Include both URLs |
| MQTT player responses | Medium | 8 | Update schemas, responses |
| Web client updates | Medium | 12 | Fetch bootstrap, choose URL |
| Environment templates | Low | 2 | Update templates, document |
| **Subtotal Development** | | **50** | |

### 7.2 Documentation Effort

| Document | Effort (hours) | Notes |
|----------|----------------|-------|
| MQTT_PROTOCOL.md | 4 | Add connection options section |
| MQTT_PLAYER_API.md | 4 | Update bootstrap, responses |
| PHYSICAL_PLAYER.md | 4 | Add configuration examples |
| DEPLOYMENT.md | 2 | Document environment variables |
| SECURITY_SETUP_GUIDE.md | 4 | Security considerations |
| **Subtotal Documentation** | **18** | |

### 7.3 Testing Effort

| Test Type | Effort (hours) | Notes |
|-----------|----------------|-------|
| Unit tests | 12 | Bootstrap, URL generation |
| Integration tests | 16 | MQTT connections, downloads |
| Security tests | 8 | TLS validation, attack scenarios |
| Performance tests | 8 | Load testing both modes |
| Manual testing | 16 | Physical player simulation |
| **Subtotal Testing** | **60** | |

### 7.4 Total Effort

| Category | Hours |
|----------|-------|
| Development | 50 |
| Documentation | 18 |
| Testing | 60 |
| Buffer (20%) | 26 |
| **Total** | **154** |

**Estimated Timeline:** 3-4 weeks (1 developer, full-time)

---

## 8. Recommendations

### 8.1 Implementation Recommendations

1. **Phased Approach**
   - Phase 1: MQTT optional TLS (2 weeks)
   - Phase 2: Download optional HTTP (1 week)
   - Phase 3: Documentation and client updates (1 week)

2. **Security-First**
   - Default to secure options
   - Non-TLS requires explicit opt-in
   - Clear warnings in documentation and UI

3. **Backward Compatibility**
   - Maintain existing endpoints
   - Add new optional fields
   - Graceful fallback for old clients

4. **Testing Strategy**
   - Comprehensive unit tests
   - Integration tests with real MQTT broker
   - Security penetration testing
   - Performance baseline and comparison

5. **Documentation**
   - Update all relevant docs
   - Add migration guide
   - Include security best practices
   - Provide configuration examples

### 8.2 Alternative Approaches

**Alternative 1: TLS-Only (Simplest)**
- Don't implement non-TLS option
- Provide assistance for clients to support TLS
- Lower complexity, higher security
- May exclude some legacy devices

**Alternative 2: Application-Level Encryption**
- Keep non-TLS MQTT
- Encrypt message payloads at application level
- More complex to implement
- Doesn't protect metadata

**Alternative 3: VPN/Tunneling**
- Require VPN for non-TLS connections
- Offload security to network layer
- Additional infrastructure complexity
- May not be feasible for all clients

### 8.3 Next Steps (If Approved)

1. **Answer Open Questions** - Get clarity on use cases and requirements
2. **Create Detailed Design** - Low-level design for each component
3. **Prototype** - Build proof-of-concept for MQTT configuration
4. **Security Review** - Get security team sign-off
5. **Implementation** - Follow phased approach
6. **Testing** - Comprehensive test coverage
7. **Documentation** - Update all relevant docs
8. **Beta Testing** - Limited rollout to select clients
9. **Full Rollout** - Gradual migration of all clients
10. **Monitoring** - Track adoption and issues

---

## Appendix A: Configuration Examples

### A.1 Production Environment (.env.remote)

```bash
# MQTT Configuration - Production (Secure by default)
MQTT_ENABLE_EXTERNAL_NON_TLS=false
MQTT_PUBLIC_HOST=makapix.club
MQTT_PUBLIC_PORT=8883
MQTT_REQUIRE_CLIENT_CERT=true
MQTT_WS_TLS_ENABLED=true
MQTT_WS_PORT=9001

# Download URLs - Production
BASE_URL=https://makapix.club
# BASE_URL_INSECURE not set (HTTP disabled)
```

### A.2 Development Environment (.env.local)

```bash
# MQTT Configuration - Development (Allow both)
MQTT_ENABLE_EXTERNAL_NON_TLS=true
MQTT_PUBLIC_HOST=localhost
MQTT_PUBLIC_PORT=8883
MQTT_PUBLIC_INSECURE_PORT=1884
MQTT_REQUIRE_CLIENT_CERT=false
MQTT_WS_TLS_ENABLED=false
MQTT_WS_PORT=9001

# Download URLs - Development
BASE_URL=https://localhost
BASE_URL_INSECURE=http://localhost
```

### A.3 Testing Environment

```bash
# MQTT Configuration - Testing (Insecure for rapid iteration)
MQTT_ENABLE_EXTERNAL_NON_TLS=true
MQTT_PUBLIC_HOST=test.makapix.club
MQTT_PUBLIC_PORT=8883
MQTT_PUBLIC_INSECURE_PORT=1884
MQTT_REQUIRE_CLIENT_CERT=false
MQTT_WS_TLS_ENABLED=false

# Download URLs - Testing
BASE_URL=https://test.makapix.club
BASE_URL_INSECURE=http://test.makapix.club
```

---

## Appendix B: Client Implementation Examples

### B.1 Physical Player (Python/MicroPython)

```python
import paho.mqtt.client as mqtt
import requests
import json

# Step 1: Fetch bootstrap configuration
response = requests.get("https://dev.makapix.club/api/mqtt/bootstrap")
config = response.json()

# Step 2: Choose connection based on device capabilities
use_tls = True  # or False based on device support

if use_tls:
    host = config["host"]
    port = config["port"]
    use_ssl = config["tls"]
else:
    # Fallback to insecure if available
    if config["insecure_host"]:
        host = config["insecure_host"]
        port = config["insecure_port"]
        use_ssl = False
    else:
        raise Exception("Non-TLS not available")

# Step 3: Connect
client = mqtt.Client(client_id=f"player-{player_key}")

if use_ssl:
    # Load certificates
    client.tls_set(
        ca_certs="ca.crt",
        certfile="client.crt",
        keyfile="client.key"
    )
else:
    # Use password authentication
    client.username_pw_set(player_key, password)

client.connect(host, port, keepalive=60)
client.loop_start()
```

### B.2 Web Client (TypeScript)

```typescript
import mqtt from 'mqtt';

// Fetch bootstrap configuration
const response = await fetch('/api/mqtt/bootstrap');
const config = await response.json();

// Prefer secure WebSocket if available
const brokerUrl = config.ws_url || config.ws_url_insecure;

if (!brokerUrl) {
  throw new Error('No WebSocket URL available');
}

// Connect
const client = mqtt.connect(brokerUrl, {
  clientId: `web-${userId}-${Math.random()}`,
  username: userId,
  password: authToken,
  protocolVersion: 5,
});
```

### B.3 Download with Fallback

```python
import requests
import hashlib

def download_artwork(post_data, prefer_secure=True):
    """Download artwork with optional fallback to HTTP."""
    
    # Choose URL based on preference and availability
    if prefer_secure:
        url = post_data["art_url"]
    else:
        url = post_data.get("art_url_insecure", post_data["art_url"])
    
    # Download
    response = requests.get(url)
    
    if response.status_code != 200:
        # Try fallback if preferred URL failed
        if prefer_secure and "art_url_insecure" in post_data:
            print("Secure download failed, trying HTTP...")
            url = post_data["art_url_insecure"]
            response = requests.get(url)
    
    if response.status_code != 200:
        raise Exception(f"Download failed: {response.status_code}")
    
    # Verify hash
    content = response.content
    actual_hash = hashlib.sha256(content).hexdigest()
    expected_hash = post_data.get("expected_hash")
    
    if expected_hash and actual_hash != expected_hash:
        raise Exception("Hash mismatch - possible tampering!")
    
    return content
```

---

## Appendix C: Monitoring and Metrics

### C.1 Recommended Metrics

**MQTT Metrics:**
- Connection attempts by protocol (TLS vs non-TLS)
- Connection success/failure rates
- Active connections by protocol
- Message throughput by protocol
- Authentication failures by protocol
- Certificate errors

**Download Metrics:**
- Requests by protocol (HTTP vs HTTPS)
- Response times by protocol
- Bandwidth usage by protocol
- 404 rates
- Hash verification failures

### C.2 Alert Conditions

1. **High non-TLS usage** - Alert if >20% of connections are non-TLS
2. **Authentication failures** - Alert if >5% failure rate
3. **Hash mismatches** - Alert on any hash verification failures
4. **Certificate expiration** - Alert 30 days before expiry
5. **Unusual traffic patterns** - Alert on sudden changes

---

## Conclusion

**Feasibility:** ✅ Feasible with moderate effort

**Recommended Approach:**
1. Implement MQTT optional TLS first (higher complexity)
2. Follow with download optional HTTP (simpler)
3. Maintain security-first approach
4. Provide clear migration path for clients

**Critical Success Factors:**
1. Clear answers to open questions
2. Strong security defaults
3. Comprehensive documentation
4. Thorough testing
5. Client education and support

**Decision Required:** 
Please review this assessment and answer the open questions in Section 5. Once approved, we can proceed with detailed design and implementation.
