# Pageview Tracking

Set up flat file-based pageview tracking for WordPress sites.

## What it does

`PageviewTrackingSetup` installs a custom tracking system that:
- Creates flat file storage directory structure
- Installs tracking plugin
- Configures exclusion rules (IPs, user agents)
- Uploads Python processing scripts
- Configures automated log processing via cron

## Setup

Add tracking configuration to `.env`:

```bash
# Data storage directory (optional - defaults to '/var/lib/pageview-tracking')
TRACKING_DATA_ROOT=/var/lib/pageview-tracking

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

wordops = WordOpsProvisioner(host="your-server-alias")
tracking = PageviewTrackingSetup(wordops.ssh)

# Set up complete tracking system
tracking.setup_tracking_wordpress("example.com")
```

## What Gets Created

The `setup_tracking_wordpress()` method:

- **Resource Files** - Uploads plugin to `/shared/` (if not already present)
- **Data Directory** - Creates `/var/lib/pageview-tracking/` with subdirectories:
  - `raw/` - Raw JSONL logs organized by domain/date
  - `agg/daily/` - Aggregated daily statistics
  - `logs/` - Server log bot statistics
  - `scripts/` - Python processing scripts
- **Environment File** - Creates `/var/www/example.com/.env` with tracking settings
- **Plugin** - Installs tracking plugin from `/shared/`
- **Configuration** - Writes `track_config.php` with storage path and exclusion rules
- **Processing Scripts** - Uploads Python scripts for log processing
- **Cron Jobs** - Sets up automated hourly log processing (pageview and server logs)

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

The tracking system requires these files in the local repository:

**Plugin** (in `/resources/`):
- `pageview-tracking.zip`

**Processing Scripts** (in `/pageview-tracking/python/`):
- `process_daily_logs.py` - Required for pageview statistics generation
- `generate_dummy_logs.py` - Optional, for testing
- `process_server_logs.py` - Required for server log bot verification

**IP Range Files** (in `/scripts/`):
- `google_ip_ranges.py` - Required for Googlebot IP verification
- `bing_ip_ranges.py` - Required for Bingbot IP verification

The plugin is automatically uploaded to `/shared/` on the server during setup. The Python scripts and IP range files are uploaded to `/var/lib/pageview-tracking/scripts/`.

## Complete Example

```python
from site_automator.wordops import WordOpsProvisioner
from site_automator.tracking import PageviewTrackingSetup

wordops = WordOpsProvisioner(host="your-server-alias")
tracking = PageviewTrackingSetup(wordops.ssh)

try:
    # Set up tracking with default flat file storage
    # and exclusion rules from .env
    tracking.setup_tracking_wordpress("example.com")

    print("Tracking setup completed successfully")

finally:
    wordops.close()
```

## Data Storage

After setup, tracking data is stored in flat files:

**Raw Logs** - `/var/lib/pageview-tracking/raw/`
- JSONL format (one JSON object per line)
- Organized by domain and date: `{domain}/{YYYY-MM-DD}.jsonl`

**Daily Aggregates** - `/var/lib/pageview-tracking/agg/daily/`
- Processed statistics by domain and date: `{domain}/{YYYY-MM-DD}.json`

**Server Log Stats** - `/var/lib/pageview-tracking/logs/`
- Bot verification statistics from Nginx/Caddy logs: `{YYYY-MM-DD}.json`

**Processing Scripts** - `/var/lib/pageview-tracking/scripts/`
- `process_daily_logs.py` - Runs hourly via cron to aggregate raw pageview logs
- `process_server_logs.py` - Runs hourly via cron to extract bot statistics from server logs
- `generate_dummy_logs.py` - Testing utility for generating sample data
- `google_ip_ranges.py` - Googlebot IP ranges for verification
- `bing_ip_ranges.py` - Bingbot IP ranges for verification