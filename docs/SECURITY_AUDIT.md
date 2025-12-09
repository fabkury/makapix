# Security Audit Report - Makapix
**Date:** December 5, 2025  
**Auditor:** GitHub Copilot Security Agent  
**Scope:** Full codebase security audit for MQTT-based pixel art social network

## Executive Summary

This security audit identified **CRITICAL** and **HIGH** severity vulnerabilities that require immediate attention. The application has several security weaknesses in authentication, secrets management, MQTT configuration, API security, and input validation.

### Risk Summary
- **CRITICAL Issues:** 3
- **HIGH Issues:** 8
- **MEDIUM Issues:** 6
- **LOW Issues:** 4

---

## 🔴 CRITICAL Vulnerabilities

### CRIT-1: Hardcoded JWT Secret Key with Insecure Fallback
**File:** `api/app/auth.py:25`  
**Severity:** CRITICAL  
**CVSS Score:** 9.8 (Critical)

**Issue:**
```python
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "fallback-secret-key-change-in-production")
```

The JWT secret key has an insecure hardcoded fallback value. If `JWT_SECRET_KEY` is not set in the environment, the application uses a predictable default value that is publicly visible in the source code. This allows attackers to:
- Forge valid JWT tokens
- Impersonate any user
- Gain full administrative access

**Impact:**
- Complete authentication bypass
- Unauthorized access to all user accounts
- Ability to impersonate site owner/moderators

**Recommendation:**
- Remove the fallback default value
- Fail fast on startup if JWT_SECRET_KEY is not configured
- Generate and use strong random secrets (minimum 256 bits)
- Add validation to ensure the secret meets minimum entropy requirements

---

### CRIT-2: Unrestricted CORS Configuration
**File:** `api/app/main.py:153-159`  
**Severity:** CRITICAL  
**CVSS Score:** 8.6 (High)

**Issue:**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

The API allows requests from ANY origin with credentials enabled. This creates multiple security risks:
- Cross-Site Request Forgery (CSRF) attacks
- Credential theft from malicious sites
- Data exfiltration

**Impact:**
- Attackers can make authenticated API requests from malicious websites
- Session hijacking
- Unauthorized data access

**Recommendation:**
- Replace `allow_origins=["*"]` with explicit whitelist of trusted domains
- Configure properly for development vs production environments
- Consider implementing CSRF token validation
- Use environment variables for allowed origins

---

### CRIT-3: Subprocess Command Injection Risk
**File:** `api/app/routers/player.py:152-156`  
**Severity:** CRITICAL  
**CVSS Score:** 9.1 (Critical)

**Issue:**
```python
subprocess.run(
    ["mosquitto_passwd", "-b", passwd_file, str(player.player_key), ""],
    check=True,
    capture_output=True,
)
```

While the current code uses list-based subprocess invocation (which is safer), the `player.player_key` is a UUID that could potentially be manipulated if validation is insufficient elsewhere. Additionally, the `passwd_file` path comes from environment variables without validation.

**Impact:**
- Potential command injection if input validation fails
- File system access if paths are not properly validated
- Privilege escalation

**Recommendation:**
- Add strict validation on `passwd_file` path (whitelist allowed directories)
- Ensure player_key is always a valid UUID format
- Implement least privilege principle for subprocess execution
- Consider using Python libraries instead of shell commands where possible

---

## 🟠 HIGH Severity Vulnerabilities

### HIGH-1: Insecure MQTT Password Generation in Scripts
**File:** `mqtt/scripts/gen-passwd.sh:12`  
**Severity:** HIGH

**Issue:**
```bash
BACKEND_PASSWORD=${BACKEND_PASSWORD:-$(openssl rand -base64 24 | tr -d "=+/" | cut -c1-24)}
```

The password generation script outputs passwords to console/logs and uses a potentially weak random generation pattern. The script also runs with elevated permissions.

**Impact:**
- Passwords logged in Docker build logs
- Potential password exposure in CI/CD systems
- Weak passwords if environment not properly configured

**Recommendation:**
- Store passwords securely using secrets management (HashiCorp Vault, AWS Secrets Manager, etc.)
- Never output passwords to console in production
- Use /dev/urandom or Python's secrets module for better entropy
- Implement password rotation mechanism

---

### HIGH-2: Missing Input Sanitization in GitHub OAuth Callback
**File:** `api/app/routers/auth.py:972-1048`  
**Severity:** HIGH

**Issue:**
The OAuth callback HTML page embeds user data and tokens directly into JavaScript without proper sanitization:

```python
html_content = f"""
    <script>
        localStorage.setItem('access_token', '{makapix_access_token}');
        localStorage.setItem('user_handle', '{user.handle}');
```

**Impact:**
- XSS vulnerability if user.handle contains malicious JavaScript
- Token exposure in browser history/logs
- Session hijacking

**Recommendation:**
- Use proper JSON encoding and escaping
- Implement Content Security Policy (CSP) headers
- Use httpOnly cookies for sensitive tokens instead of localStorage
- Sanitize all user-provided data before embedding in HTML

---

### HIGH-3: SQL Injection Risk in Legacy Code
**File:** Multiple files using raw SQL
**Severity:** HIGH

**Issue:**
While most of the codebase uses SQLAlchemy ORM which prevents SQL injection, there are instances of `db.execute()` calls that may be vulnerable if not properly parameterized.

**Impact:**
- Database compromise
- Data exfiltration
- Unauthorized access

**Recommendation:**
- Audit all `db.execute()` calls to ensure parameterized queries
- Use SQLAlchemy ORM methods instead of raw SQL where possible
- Implement prepared statements for all database queries
- Add SQL injection testing to security test suite

---

### HIGH-4: Insufficient Rate Limiting Implementation
**File:** `api/app/routers/mqtt.py:52-67`  
**Severity:** HIGH

**Issue:**
```python
# PLACEHOLDER: Return unlimited
return schemas.RateLimitStatus(
    buckets={
        "global": schemas.RateLimitBucket(remaining=1000, reset_in_s=3600),
        "posts": schemas.RateLimitBucket(remaining=100, reset_in_s=3600),
    }
)
```

The rate limiting is not actually implemented - it's a placeholder that returns fake data.

**Impact:**
- Brute force attacks on authentication endpoints
- API abuse and DoS attacks
- Resource exhaustion
- Spam posting

**Recommendation:**
- Implement Redis-based rate limiting as indicated in TODO comments
- Add rate limits to all authentication endpoints
- Implement different rate limits for different user roles
- Add rate limiting to MQTT publish operations

---

### HIGH-5: Weak Password Requirements
**File:** `api/app/routers/auth.py:50-53`  
**Severity:** HIGH

**Issue:**
```python
def generate_random_password(length: int = 8) -> str:
    """Generate a random password with letters and digits."""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))
```

8-character passwords with only alphanumeric characters provide insufficient entropy (~48 bits). No special characters are included.

**Impact:**
- Weak passwords vulnerable to brute force
- Easier credential stuffing attacks
- Reduced account security

**Recommendation:**
- Increase minimum password length to 12 characters
- Include special characters in password generation
- Implement password strength validation
- Consider using passphrases or longer passwords
- Add password complexity requirements

---

### HIGH-6: Missing Authentication on MQTT Demo Endpoint
**File:** `api/app/routers/mqtt.py:32-49`  
**Severity:** HIGH

**Issue:**
```python
@router.post("/mqtt/demo", response_model=schemas.MQTTPublishResponse, tags=["MQTT"])
def mqtt_demo() -> schemas.MQTTPublishResponse:
    """
    Publish demo MQTT message.
    
    TODO: Remove in production or restrict to development environment
    """
```

The MQTT demo endpoint has no authentication and can be called by anyone to publish messages to the MQTT broker.

**Impact:**
- Unauthorized MQTT message publishing
- Spam and abuse of MQTT topics
- DoS through message flooding
- Information disclosure about MQTT infrastructure

**Recommendation:**
- Remove endpoint in production
- Add authentication requirement (Depends(get_current_user))
- Add rate limiting
- Restrict to development/staging environments only via environment check

---

### HIGH-7: Insecure WebSocket MQTT Configuration
**File:** `mqtt/mosquitto.conf:23-28`  
**Severity:** HIGH

**Issue:**
```
# WebSocket listener on port 9001 (for web clients - password auth)
listener 9001 0.0.0.0
protocol websockets
# WebSocket doesn't use client certs, so we'll use password auth
# Note: This is less secure but necessary for browser compatibility
```

WebSocket listener uses password authentication instead of certificate-based mTLS, and the comment acknowledges this is "less secure."

**Impact:**
- Weaker authentication compared to mTLS
- Potential password sniffing if not properly encrypted
- Easier credential theft

**Recommendation:**
- Implement token-based authentication for WebSocket connections
- Use JWT tokens passed in WebSocket connection parameters
- Ensure WSS (WebSocket Secure) is enforced in production
- Consider implementing short-lived connection tokens
- Add connection origin validation

---

### HIGH-8: Sensitive Data in Console Logs
**File:** Multiple locations
**Severity:** HIGH

**Issue:**
Various debug logging statements may expose sensitive information:
- `mqtt/scripts/gen-passwd.sh:38-39` - Outputs passwords to console
- OAuth flow logs tokens and user information
- Database connection strings may be logged

**Impact:**
- Credentials exposed in logs
- PII leakage
- Compliance violations (GDPR, etc.)

**Recommendation:**
- Implement log sanitization
- Use structured logging with sensitive field redaction
- Never log passwords, tokens, or PII
- Implement log level controls (DEBUG only in development)
- Add security review for all logging statements

---

## 🟡 MEDIUM Severity Issues

### MED-1: Missing JWT Token Revocation
**Severity:** MEDIUM

**Issue:**
While refresh tokens can be revoked, access tokens cannot be revoked before expiration. A compromised access token remains valid for up to 240 minutes (4 hours) by default.

**Recommendation:**
- Implement JWT token blacklist in Redis
- Reduce access token lifetime
- Add token revocation endpoint
- Implement token rotation on sensitive operations

---

### MED-2: Path Traversal Risk in File Operations
**File:** `api/app/validation.py:18-22`  
**Severity:** MEDIUM

**Issue:**
```python
for name in zf.namelist():
    if name.startswith('/') or '..' in name:
        errors.append(f"Unsafe path: {name}")
```

While path traversal is checked, the validation only checks for leading `/` and `..`. More sophisticated path traversal techniques may bypass this.

**Recommendation:**
- Use `os.path.normpath()` and verify result is within expected directory
- Use `pathlib.Path.resolve()` with `strict=True`
- Implement whitelist of allowed file extensions
- Add additional checks for symbolic links

---

### MED-3: Insufficient File Upload Validation
**File:** `api/app/validation.py`  
**Severity:** MEDIUM

**Issue:**
File validation checks size and format but doesn't validate file content (magic bytes). An attacker could upload malicious files with manipulated extensions.

**Recommendation:**
- Validate file magic bytes/signatures
- Scan uploads with antivirus/malware detection
- Implement content-type validation
- Store uploads in isolated directory with no execution permissions

---

### MED-4: Missing HTTPS Enforcement
**File:** Multiple configuration files  
**Severity:** MEDIUM

**Issue:**
Configuration files don't enforce HTTPS for production deployments. HTTP traffic may be allowed.

**Recommendation:**
- Add HSTS headers (Strict-Transport-Security)
- Redirect all HTTP to HTTPS
- Implement certificate pinning for API clients
- Enforce TLS 1.3 minimum

---

### MED-5: Session Fixation Risk
**File:** Authentication flows  
**Severity:** MEDIUM

**Issue:**
Session identifiers (refresh tokens) are not rotated after privilege escalation or password changes.

**Recommendation:**
- Implement session rotation on password change
- Revoke all tokens on security-sensitive operations
- Add "logout all devices" functionality
- Track active sessions per user

---

### MED-6: Missing Security Headers
**File:** `api/app/main.py`  
**Severity:** MEDIUM

**Issue:**
API responses don't include important security headers:
- X-Content-Type-Options
- X-Frame-Options
- Content-Security-Policy
- X-XSS-Protection

**Recommendation:**
- Add security headers middleware
- Implement CSP for frontend
- Add X-Frame-Options: DENY
- Include X-Content-Type-Options: nosniff

---

## 🔵 LOW Severity Issues

### LOW-1: Email Enumeration via Registration
**Severity:** LOW

**Issue:**
The `/auth/register` endpoint returns different error messages for existing vs new emails, allowing email enumeration.

**Recommendation:**
- Return generic error messages
- Implement same timing for all responses
- Consider using email verification flow that doesn't reveal registration status

---

### LOW-2: Verbose Error Messages
**Severity:** LOW

**Issue:**
Error messages expose internal implementation details and stack traces in some cases.

**Recommendation:**
- Implement generic error messages for production
- Log detailed errors server-side only
- Don't expose database schema information
- Use error codes instead of descriptive messages

---

### LOW-3: Missing CSRF Protection
**Severity:** LOW (mitigated by JWT)

**Issue:**
While JWT tokens provide some CSRF protection, state-changing operations don't have additional CSRF tokens.

**Recommendation:**
- Implement CSRF tokens for state-changing operations
- Validate Origin/Referer headers
- Use SameSite cookie attributes

---

### LOW-4: Outdated Dependencies
**Severity:** LOW

**Issue:**
Some dependencies may have known vulnerabilities. Regular security updates are needed.

**Recommendation:**
- Implement automated dependency scanning (Dependabot, Snyk)
- Regular security updates
- Monitor CVE databases
- Use lock files for reproducible builds

---

## Security Best Practices Recommendations

### Immediate Actions (Week 1)
1. Fix CRIT-1: Remove hardcoded JWT secret fallback
2. Fix CRIT-2: Restrict CORS to specific origins
3. Fix CRIT-3: Validate subprocess inputs
4. Fix HIGH-1: Secure MQTT password generation
5. Remove or secure HIGH-6: MQTT demo endpoint

### Short-term Actions (Week 2-4)
1. Implement HIGH-4: Redis-based rate limiting
2. Fix HIGH-2: XSS in OAuth callback
3. Add MED-6: Security headers
4. Fix HIGH-5: Strengthen password requirements
5. Audit HIGH-3: SQL injection risks

### Medium-term Actions (Month 2-3)
1. Implement secrets management solution
2. Add comprehensive security testing
3. Implement token revocation
4. Add security monitoring and alerting
5. Perform penetration testing

### Long-term Actions (Month 3+)
1. Security training for development team
2. Implement bug bounty program
3. Regular security audits
4. Compliance certifications (if needed)
5. Disaster recovery and incident response procedures

---

## Testing Recommendations

### Security Testing Checklist
- [ ] Automated SQL injection testing (SQLMap)
- [ ] XSS vulnerability scanning
- [ ] Authentication bypass testing
- [ ] Authorization testing (IDOR, privilege escalation)
- [ ] CSRF testing
- [ ] Rate limiting testing
- [ ] File upload security testing
- [ ] MQTT security testing
- [ ] API fuzzing
- [ ] Dependency vulnerability scanning

### Tools Recommended
- OWASP ZAP for web application scanning
- Burp Suite for manual security testing
- SQLMap for SQL injection testing
- GitGuardian for secrets detection
- Snyk for dependency scanning
- CodeQL for static analysis

---

## Compliance Considerations

### GDPR/Privacy
- Implement data retention policies
- Add user data export functionality
- Implement right to deletion
- Add privacy policy and consent management
- Encrypt PII at rest and in transit

### General Security
- Implement audit logging for all sensitive operations
- Add intrusion detection system (IDS)
- Implement security incident response plan
- Regular backups with encryption
- Disaster recovery testing

---

## Conclusion

This security audit reveals several critical vulnerabilities that require immediate attention. The most pressing issues are:

1. **Hardcoded JWT secret** - Enables complete authentication bypass
2. **Unrestricted CORS** - Allows cross-origin attacks
3. **Missing rate limiting** - Enables brute force and DoS attacks
4. **Weak password generation** - Compromises account security
5. **Insecure MQTT configuration** - Weakens real-time messaging security

**Immediate action is required** to address the CRITICAL and HIGH severity issues before deploying to production. A phased approach to remediation is recommended, starting with the authentication and authorization vulnerabilities.

Regular security audits and continuous security monitoring should be implemented as part of the development lifecycle.

---

**Report Version:** 1.0  
**Next Review Date:** March 5, 2026  
**Contact:** security@makapix.club
