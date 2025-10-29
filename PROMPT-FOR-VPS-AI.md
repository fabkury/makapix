# Prompt for VPS AI

Copy and paste this prompt to an AI model running on your VPS:

---

## Prompt:

I need to deploy the Makapix development environment on this VPS. The repository is at `/opt/makapix`. 

**Context:**
- This VPS already has `caddy-docker-proxy` running (container named `caddy`) which manages routing for multiple domains
- We want to deploy https://dev.makapix.club/ using the docker-compose setup in `/opt/makapix`
- The static CTA site at https://makapix.club/ (container `makapix-cta`) should continue running
- There's an old container `makapix-dev` that needs to be replaced

**What I need you to do:**

1. Navigate to `/opt/makapix` and pull the latest code from git
2. Stop and remove the old `makapix-dev` container if it exists
3. Run `make remote` to switch to the remote environment configuration
4. Verify the `.env` file has the correct GitHub credentials (it should already be configured)
5. Run `docker compose down -v` to clean up any old volumes
6. Run `docker compose up -d` to start the services
7. Verify all services are healthy with `docker compose ps`
8. Test that https://dev.makapix.club/ is accessible

The new setup uses caddy-docker-proxy labels for routing instead of a standalone proxy service, so the `makapix-proxy-1` container should NOT start on remote - that's expected.

**Important notes:**
- Do NOT stop the `caddy` or `makapix-cta` containers
- The configuration is already set up to use the existing caddy-docker-proxy
- If port 80 is already in use, that's because caddy-docker-proxy is already running - this is correct
- Services should connect to the `caddy_net` external network for routing

Please proceed with the deployment and let me know if any issues arise.

---

## Alternative: Quick Command Version

If you prefer to just run commands directly on the VPS, use this:

```bash
cd /opt/makapix
git pull origin main
docker stop makapix-dev 2>/dev/null || true
docker rm makapix-dev 2>/dev/null || true
make remote
docker compose down -v
docker compose up -d
docker compose ps
echo "✅ Deployment complete! Check https://dev.makapix.club/"
```


