# GeoIP Database Setup

This module uses MaxMind's GeoLite2 Country database for IP-to-country resolution.

## Getting the Database

1. **Create a MaxMind Account**
   - Go to https://www.maxmind.com/en/geolite2/signup
   - Create a free account

2. **Generate a License Key**
   - Log in to your MaxMind account
   - Go to "My License Key" under Services/My License Key
   - Generate a new license key

3. **Download the Database**
   - Go to https://www.maxmind.com/en/accounts/current/geoip/downloads
   - Download "GeoLite2 Country" in MMDB format
   - Extract the `.mmdb` file from the downloaded archive

4. **Install the Database**
   - Place the `GeoLite2-Country.mmdb` file in this directory (`api/app/geoip/`)
   - Or set the `GEOIP_DB_PATH` environment variable to the file location

## Automatic Updates

MaxMind updates the GeoLite2 database weekly. To keep your database current:

### Option 1: Manual Updates
Download the latest database monthly from the MaxMind website.

### Option 2: geoipupdate Tool
Install and configure `geoipupdate`:

```bash
# Install geoipupdate
# On Ubuntu/Debian:
sudo apt install geoipupdate

# On macOS:
brew install geoipupdate
```

Create `/etc/GeoIP.conf`:
```
AccountID YOUR_ACCOUNT_ID
LicenseKey YOUR_LICENSE_KEY
EditionIDs GeoLite2-Country
```

Run updates:
```bash
geoipupdate
```

## Docker Setup

For Docker deployments, add the database file to your container:

```dockerfile
COPY GeoLite2-Country.mmdb /workspace/api/app/geoip/
```

Or mount it as a volume in `docker-compose.yml`:

```yaml
volumes:
  - ./path/to/GeoLite2-Country.mmdb:/workspace/api/app/geoip/GeoLite2-Country.mmdb:ro
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GEOIP_DB_PATH` | Path to the GeoLite2-Country.mmdb file | `api/app/geoip/GeoLite2-Country.mmdb` |

## Verification

To verify the database is loaded correctly:

```python
from app.geoip import is_available, get_database_info, get_country_code

# Check if available
print(is_available())  # True if database is loaded

# Get database info
print(get_database_info())

# Test lookup
print(get_country_code("8.8.8.8"))  # Should return "US"
```

## License

GeoLite2 databases are subject to the MaxMind GeoLite2 End User License Agreement.
See: https://www.maxmind.com/en/geolite2/eula

**Important**: The GeoLite2 database file (`*.mmdb`) should NOT be committed to version control.
Add it to `.gitignore`:

```
api/app/geoip/*.mmdb
```

