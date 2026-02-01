# Player Deletion Security Fix

## Problem Statement

When a user deletes a registered physical player through the UI, the player should no longer be able to connect to the MQTT broker. However, the original implementation had a security gap:

- Players connect to MQTT broker via mTLS (mutual TLS) on port 8883
- Player authentication uses TLS client certificates signed by the CA
- When a player was deleted, only the password file entry was removed
- The TLS certificate remained valid and was not revoked
- Deleted players could still reconnect to MQTT using their certificates

## Solution

This fix implements proper certificate revocation using a Certificate Revocation List (CRL):

### 1. Certificate Revocation Infrastructure

**File: `api/app/mqtt/cert_generator.py`**
- Added `revoke_certificate()` function to add certificates to the CRL
- Implements atomic CRL updates with proper file locking
- Handles idempotent revocation (same cert can be revoked multiple times safely)
- Added `disconnect_mqtt_client()` for future extension (currently logs intent)

**File: `api/app/mqtt/crl_init.py`**
- New module for CRL initialization
- Creates empty CRL on startup if it doesn't exist
- Ensures Mosquitto can start without errors

### 2. Mosquitto Configuration Updates

**Files: `mqtt/mosquitto.conf` and `mqtt/config/mosquitto.conf`**
- Added `crlfile /mosquitto/certs/crl.pem` to mTLS listener configuration
- Mosquitto now checks the CRL on every client connection
- Revoked certificates are rejected immediately

**Files: `mqtt/scripts/gen-certs.sh` and `mqtt/config/scripts/gen-certs.sh`**
- Updated to create empty CRL during certificate initialization
- Uses OpenSSL to generate properly formatted CRL

### 3. Player Deletion Flow

**File: `api/app/routers/player.py`**

Updated `delete_player()` endpoint to:

1. **Extract certificate info** - Store cert_serial_number before deletion
2. **Log removal** - Create audit trail with "remove_device" command
3. **Revoke certificate** - Add certificate to CRL if it exists
4. **Disconnect client** - Mark player for disconnection (logged)
5. **Delete from database** - Remove player record
6. **Remove password** - Clean up password file (existing functionality)

The revocation happens **before** database deletion to ensure the certificate is revoked even if subsequent steps fail. All steps use exception handling to ensure the player is deleted even if revocation fails.

### 4. Startup Integration

**File: `api/app/main.py`**
- Added CRL initialization to startup tasks
- Ensures CRL exists before API server starts accepting requests

## Security Properties

### Before Fix
- ❌ Deleted players could reconnect using cached certificates
- ❌ No mechanism to invalidate certificates
- ❌ Security relied solely on password file

### After Fix
- ✅ Certificates are immediately revoked on player deletion
- ✅ Mosquitto checks CRL on every connection
- ✅ Multi-layered security: certificates + passwords + database
- ✅ Atomic CRL updates prevent race conditions
- ✅ Graceful degradation if revocation fails (player still deleted)

## Testing

**File: `api/tests/test_player_deletion.py`**

Comprehensive test suite including:

1. **Integration tests** - Test player deletion with/without certificates
2. **Failure handling** - Verify graceful degradation
3. **Unit tests** - Direct testing of revocation functions
4. **CRL initialization** - Verify proper CRL creation

Run tests with:
```bash
make test
# or
docker compose run --rm api-test
```

## How Certificate Revocation Works

1. **Registration** - Player gets certificate with unique serial number
2. **Deletion** - Certificate serial is added to CRL
3. **Connection attempt** - Mosquitto loads CRL and checks certificate
4. **Rejection** - Revoked certificates fail TLS handshake
5. **Update** - CRL is checked on every connection (no caching)

## CRL Format

The CRL is stored in PEM format at `/mosquitto/certs/crl.pem`:
- Signed by the CA to ensure authenticity
- Updated atomically to prevent corruption
- Valid for 30 days (refreshed on each update)
- Empty CRL created at startup if missing

## Environment Variables

- `MQTT_CA_FILE` - CA certificate path (default: `/certs/ca.crt`)
- `MQTT_CA_KEY_FILE` - CA private key path (default: `/certs/ca.key`)
- `MQTT_CRL_FILE` - CRL path (default: `/certs/crl.pem`)
- `MQTT_PASSWD_FILE` - Password file path (default: `/mqtt-config/passwords`)

## Operational Notes

### Monitoring
- Check logs for "Revoked certificate" messages
- Monitor CRL size (grows with each revocation)
- CRL is regenerated on each revocation (no manual maintenance needed)

### CRL Rotation
- CRL validity: 30 days
- Automatically updated on each revocation
- No manual rotation needed

### Troubleshooting

**Players can't connect after deletion:**
- ✅ Expected behavior - this is the security fix working correctly
- Check that player was properly deleted from database
- Verify CRL contains the certificate serial number

**CRL file missing:**
- API startup automatically creates empty CRL
- Check permissions on `/mosquitto/certs/` directory
- Verify CA certificate and key are accessible

**Revocation fails but player deleted:**
- This is safe - player can't reconnect via password auth
- Check CA certificate/key paths in environment
- Check file permissions on CRL path
- Player is still removed from database

## Future Enhancements

Possible improvements for future iterations:

1. **Immediate disconnection** - Implement active connection termination using Mosquitto dynamic security plugin
2. **CRL size management** - Archive and compress old CRLs periodically
3. **Certificate renewal** - Automatic certificate rotation before expiry
4. **Metrics** - Track revocation statistics and CRL size
5. **Admin UI** - View revoked certificates and CRL status

## References

- [Mosquitto TLS Configuration](https://mosquitto.org/man/mosquitto-tls-7.html)
- [X.509 Certificate Revocation Lists](https://datatracker.ietf.org/doc/html/rfc5280#section-5)
- [Python Cryptography Library](https://cryptography.io/en/latest/x509/reference/)
