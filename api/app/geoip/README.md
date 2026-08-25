# GeoIP Database Setup

This module uses MaxMind's GeoLite2 Country database for IP-to-country
resolution. Without the database file, `get_country_code` silently returns
`None` and `country_code` stays NULL in `site_events` / `view_events` — which
is exactly what happened until 2026-08-25, so treat "all-NULL country data" as
the symptom that this setup broke.

## How it works in this deployment (automated)

1. **Create a MaxMind account** at https://www.maxmind.com/en/geolite2/signup
   (free) and generate a license key under Services → My License Key.
2. **Set `MAXMIND_LICENSE_KEY`** in `deploy/stack/.env.dev` and
   `deploy/stack/.env.prod`. Compose passes it to the api and worker
   containers (optional — everything degrades gracefully without it).
3. The **`refresh_geoip_database` beat task** (daily 05:15 ET; see
   `beat_schedule` in `api/app/tasks.py`) downloads
   `GeoLite2-Country.mmdb` into this directory whenever the on-disk copy is
   missing or older than 6 days. The directory is bind-mounted into both
   containers, so the file lands on the host and survives rebuilds.
4. The reader in `__init__.py` is **mtime-aware**: running processes pick up
   a new or refreshed file on the next lookup — no restart needed.

To force an immediate download (e.g. right after setting the key):

```bash
docker exec makapix-dev-worker celery -A app.tasks call app.tasks.refresh_geoip_database --kwargs '{"force": true}'
```

(substitute `makapix-prod-worker` in production)

## Manual install (fallback)

Download "GeoLite2 Country" (MMDB format) from
https://www.maxmind.com/en/accounts/current/geoip/downloads, extract, and
place `GeoLite2-Country.mmdb` in this directory — or set the
`GEOIP_DB_PATH` environment variable to its location.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MAXMIND_LICENSE_KEY` | MaxMind license key for automated downloads | (unset — refresh task no-ops) |
| `GEOIP_DB_PATH` | Path to the GeoLite2-Country.mmdb file | `api/app/geoip/GeoLite2-Country.mmdb` |

## Verification

```python
from app.geoip import is_available, get_database_info, get_country_code

print(is_available())            # True if database is loaded
print(get_database_info())       # metadata incl. build_epoch
print(get_country_code("8.8.8.8"))  # Should return "US"
```

## License

GeoLite2 databases are subject to the MaxMind GeoLite2 End User License
Agreement (https://www.maxmind.com/en/geolite2/eula). The EULA requires
directly-downloaded copies to be kept current (no older than 30 days) — the
beat task's weekly refresh satisfies this.

**Important**: the database file must NOT be committed to version control
(`*.mmdb` and `*.mmdb.part` are gitignored). The license key is a secret:
it must live only in the env files, never in the repo, and the refresh task
deliberately never logs the download URL (the key is embedded in it).
