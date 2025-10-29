# Prompt for VPS AI - Debug Publishing Failure

Copy and paste this to the AI model on your VPS:

---

## Context

I'm running the Makapix application on this VPS at `/opt/makapix`. A user successfully logged in via GitHub OAuth and installed the GitHub App, but when they tried to publish artwork, the job failed with:

```
Job ID: 17832c55-5434-4f87-b4df-f1c387266b64
Status: failed
❌ Publishing failed. Check the logs for details.
```

## What I need you to do:

1. **Check the worker logs** for this specific job ID to identify the error:
   ```bash
   cd /opt/makapix
   docker compose logs worker | grep -A 50 "17832c55-5434-4f87-b4df-f1c387266b64"
   ```

2. **Check the API logs** for any related errors:
   ```bash
   docker compose logs api | grep -A 20 -B 20 "17832c55-5434-4f87-b4df-f1c387266b64"
   ```

3. **Check recent worker logs** (last 100 lines) for any errors:
   ```bash
   docker compose logs --tail 100 worker
   ```

4. **Common issues to check:**
   - GitHub App credentials (GITHUB_APP_ID, GITHUB_APP_PRIVATE_KEY in .env)
   - GitHub App permissions (needs Contents: Read & Write, Pages: Read & Write)
   - GitHub App installation binding to user account
   - Network connectivity issues
   - ZIP file processing errors
   - Repository creation/access errors

5. **Check the environment variables are correct:**
   ```bash
   docker compose exec api env | grep GITHUB_APP
   ```

6. **After identifying the error**, please:
   - Explain what the error is
   - Provide the solution
   - Apply the fix if it's a configuration issue
   - Restart the necessary services

7. **Test the fix** by asking me to retry the upload.

## Additional diagnostic commands:

```bash
# Check if all services are healthy
docker compose ps

# Check database for the job status
docker compose exec db psql -U makapix -d makapix -c "SELECT id, status, error_message FROM relay_jobs WHERE id = '17832c55-5434-4f87-b4df-f1c387266b64';"

# Check if worker is processing tasks
docker compose logs --tail 50 worker | grep -i "task"

# Verify GitHub App configuration
docker compose exec api python -c "
import os
print('GITHUB_APP_ID:', os.getenv('GITHUB_APP_ID'))
print('GITHUB_APP_PRIVATE_KEY exists:', 'yes' if os.getenv('GITHUB_APP_PRIVATE_KEY') else 'no')
print('GITHUB_APP_PRIVATE_KEY length:', len(os.getenv('GITHUB_APP_PRIVATE_KEY', '')) if os.getenv('GITHUB_APP_PRIVATE_KEY') else 0)
"
```

## Expected output format:

Please provide:
1. **Root cause:** What caused the failure
2. **Error details:** The specific error message from logs
3. **Solution:** What needs to be fixed
4. **Commands executed:** What you did to fix it
5. **Verification:** How to verify the fix worked

---

## Quick reference for common fixes:

### Fix 1: GitHub App private key format
The private key must be properly formatted in .env:
```bash
GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA...
...
-----END RSA PRIVATE KEY-----"
```

### Fix 2: Restart services after .env changes
```bash
docker compose down
docker compose up -d
```

### Fix 3: Check GitHub App installation
```bash
# Get installation info from database
docker compose exec db psql -U makapix -d makapix -c "SELECT github_username, github_app_installation_id FROM profiles;"
```

Please proceed with the diagnosis and let me know what you find.

