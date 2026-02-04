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
# Environment file path (optional - defaults to '../../../../.env')
TRACKING_ENV_FILE=../../../../.env

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
tracking = PageviewTrackingSetup(wordops)

# Set up complete tracking system
tracking.setup_tracking("example.com")
```

## What Gets Created

The `setup_tracking()` method:

- **Resource Files** - Uploads plugin to `/shared/` (if not already present)
- **Data Directory** - Creates `/var/lib/pageview-tracking/` with subdirectories:
  - `raw/` - Raw JSONL logs organized by domain/date
  - `agg/daily/` - Aggregated daily statistics
  - `scripts/` - Python processing scripts
- **Environment File** - Creates `/var/www/example.com/.env` with tracking settings
- **Plugin** - Installs tracking plugin from `/shared/`
- **Configuration** - Writes `track_config.php` with storage path and exclusion rules
- **Processing Scripts** - Uploads Python scripts for log processing
- **Cron Job** - Sets up automated hourly log processing

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

**Plugin:**
- `pageview-tracking.zip`

**Processing Scripts** (in `/pageview-tracking/python/`):
- `process_daily_logs.py` - Required for statistics generation
- `generate_dummy_logs.py` - Optional, for testing

The plugin is automatically uploaded to `/shared/` on the server during setup. The Python scripts are uploaded to `/var/lib/pageview-tracking/scripts/`.

## Complete Example

```python
from site_automator.wordops import WordOpsProvisioner
from site_automator.tracking import PageviewTrackingSetup

wordops = WordOpsProvisioner(host="your-server-alias")
tracking = PageviewTrackingSetup(wordops)

try:
    # Set up tracking with default flat file storage
    # and exclusion rules from .env
    tracking.setup_tracking("example.com")

    print("Tracking setup completed successfully")

finally:
    wordops.close()
```

## Data Storage

After setup, pageview data is stored in flat files:

**Raw Logs** - `/var/lib/pageview-tracking/raw/`
- JSONL format (one JSON object per line)
- Organized by domain and date: `{domain}/{YYYY-MM-DD}.jsonl`

**Daily Aggregates** - `/var/lib/pageview-tracking/agg/daily/`
- Processed statistics by domain and date: `{domain}/{YYYY-MM-DD}.json`

**Processing Scripts** - `/var/lib/pageview-tracking/scripts/`
- `process_daily_logs.py` - Runs hourly via cron to aggregate raw logs
- `generate_dummy_logs.py` - Testing utility for generating sample data