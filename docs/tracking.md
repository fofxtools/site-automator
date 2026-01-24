# Pageview Tracking

Set up database-backed pageview tracking for WordPress sites.

## What it does

`PageviewTrackingSetup` installs a custom tracking system that:
- Creates MySQL database and user
- Creates tracking tables
- Installs tracking plugins
- Configures exclusion rules (IPs, user agents)

## Setup

Add tracking configuration to `.env`:

```bash
# Database settings (optional - uses defaults if not set)
TRACKING_DB_NAME=site_automator
TRACKING_DB_USER=db_admin
TRACKING_DB_PASSWORD=

# Plugin configuration file path
TRACKING_DB_CONFIG_FILE=../../../../.env

# Exclusions (comma-separated)
TRACKING_EXCLUDE_IPS=127.0.0.1,192.168.1.1
TRACKING_EXCLUDE_IPS_CIDR=10.0.0.0/8
TRACKING_EXCLUDE_USER_AGENTS_EXACT=BadBot
TRACKING_EXCLUDE_USER_AGENTS_SUBSTRING=bot,scraper
```

## Basic Usage

```python
from site_automator.wordops import WordOpsProvisioner
from site_automator.tracking import PageviewTrackingSetup

wordops = WordOpsProvisioner.from_env()
tracking = PageviewTrackingSetup(wordops)

# Set up complete tracking system
tracking.setup_tracking("example.com")
```

## What Gets Created

The `setup_tracking()` method:

- **Resource Files** - Uploads plugins and SQL files to `/shared/` (if not already present)
- **MySQL User** - Creates database user (default: `db_admin`)
- **Database** - Creates database (default: `site_automator`)
- **Tables** - Creates `tracking_pageviews` and `tracking_pageviews_daily`
- **Environment File** - Creates `/var/www/example.com/.env` with credentials
- **Plugins** - Installs tracking plugins from `/shared/`
- **Configuration** - Writes `track_config.php` with exclusion rules

## Exclusion Rules

Configure what traffic to ignore in your local `.env`:

```bash
# Individual IPs to exclude (e.g. your home IP, to avoid statistics corruption)
TRACKING_EXCLUDE_IPS=127.0.0.1,192.168.1.100

# IP ranges to exclude (CIDR notation)
TRACKING_EXCLUDE_IPS_CIDR=192.168.1.0/24,10.0.0.0/8

# User agents to exclude (exact match, case-insensitive)
TRACKING_EXCLUDE_USER_AGENTS_EXACT=BadBot/1.0,Scraper/2.0

# User agent substrings to exclude (case-insensitive)
TRACKING_EXCLUDE_USER_AGENTS_SUBSTRING=bot,crawler,scraper
```

These rules are written to `track_config.php` on the server.

## Required Files

The tracking system requires these files in the local `/resources/` directory:

**SQL files:**
- `tracking_pageviews.sql`
- `tracking_pageviews_daily.sql`

**Plugin files:**
- `pageview-tracking-core.zip`
- `pageview-tracking.zip`
- `pageview-tracking-daily.zip`

These files are automatically uploaded to `/shared/` on the server during setup.

## Complete Example

```python
from site_automator.wordops import WordOpsProvisioner
from site_automator.tracking import PageviewTrackingSetup

wordops = WordOpsProvisioner.from_env()
tracking = PageviewTrackingSetup(wordops)

try:
    # Set up tracking with default database settings
    # and exclusion rules from .env
    tracking.setup_tracking("example.com")

    print("Tracking setup completed successfully")

finally:
    wordops.close()
```

## Database Access

After setup, the tracking database credentials are stored in:
- Server: `/var/www/example.com/.env`

```python
# Credentials are in the remote .env file
# Example structure:
# TRACKING_DB_HOST=localhost
# TRACKING_DB_NAME=site_automator
# TRACKING_DB_USER=db_admin
# TRACKING_DB_PASSWORD=<generated_password>
```