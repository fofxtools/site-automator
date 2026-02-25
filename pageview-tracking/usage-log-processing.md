# Pageview Tracking - Log Processing & Web Viewer

## Overview

Process raw pageview logs into daily statistics and view them in a web interface.

**Data Flow:**
1. Raw logs: `/var/lib/pageview-tracking/raw/{domain}/{date}/*.jsonl`
2. Python processor: Aggregates raw logs into daily stats
3. Aggregated data: `/var/lib/pageview-tracking/agg/daily/{date}.json`
4. PHP web viewer: Displays aggregated statistics

---

## Python Log Processor

### process_daily_logs.py

Aggregates raw JSONL logs into daily statistics by domain.

**Input:** `/var/lib/pageview-tracking/raw/{domain}/{date}/`
- `pageview.jsonl` - Pageview records
- `metrics.jsonl` - Performance metrics
- `engagement.jsonl` - Engagement metrics (time on page, scroll depth, scroll events)
- `bots.jsonl` - Bot detection signals

**Output:** `/var/lib/pageview-tracking/agg/daily/{date}.json`

**Usage:**
```bash
cd pageview-tracking/python

# Process all dates (skip already processed)
python3 process_daily_logs.py

# Reprocess all dates (force)
python3 process_daily_logs.py --force
```

**What it does:**
- Groups pageviews by domain and is_internal flag (0=homepage, 1=internal page)
- Joins pageviews with performance metrics by view_id
- Joins pageviews with engagement metrics by view_id
- Calculates qualified pageviews (time_on_page >= 5s AND (scroll_depth > 0 OR scroll_events >= 1))
- Calculates performance stats: avg, median, p95 for TTFB, DCL, Load
- Counts bot signals by type
- Writes atomic JSON output (temp file + rename)

**Automation:**
```bash
# Add to crontab to run daily at 1 AM
0 1 * * * cd /path/to/pageview-tracking/python && python3 process_daily_logs.py
```

---

### generate_dummy_logs.py

Generate test data for development.

**Usage:**
```bash
cd pageview-tracking/python

# Generate test data
python3 generate_dummy_logs.py

# Remove test data
python3 generate_dummy_logs.py --cleanup
```

**What it generates:**
- Test domains: `*.test` (example.com.test, shop.test, blog.test)
- Random pageviews with realistic patterns
- Performance metrics
- Engagement metrics
- Bot signals
- Last 5 days of data

---

### process_server_logs.py

Process Nginx/Caddy access logs to extract verified bot statistics (Googlebot and Bingbot).

**Input:** `/var/log/caddy/` or `/var/log/nginx/` (auto-detected)
- Nginx combined log format (handles dual-format: catch-all and domain vhosts)
- Caddy JSON log format
- Supports gzip-compressed rotated logs

**Output:** `/var/lib/pageview-tracking/logs/{date}.json`

**Verification:** Requires both User Agent AND IP match (no spoofed bots)

**Dependencies:**
- `google_ip_ranges.py` - Googlebot IP ranges (co-located in scripts/)
- `bing_ip_ranges.py` - Bingbot IP ranges (co-located in scripts/)

**Usage:**
```bash
cd /var/lib/pageview-tracking/scripts

# Process yesterday's logs (default)
python3 process_server_logs.py

# Process all dates (skip existing files)
python3 process_server_logs.py --all

# Process all dates (overwrite existing files)
python3 process_server_logs.py --all --force

# Process specific date
python3 process_server_logs.py --date 2026-02-23

# Reprocess specific date (force overwrite)
python3 process_server_logs.py --date 2026-02-23 --force

# Custom log directory
python3 process_server_logs.py --log-dir /custom/path/to/logs

# Custom output directory
python3 process_server_logs.py --output-dir /custom/output
```

**What it does:**
- Auto-detects Caddy (JSON) vs Nginx (text) log format
- Extracts real IP from proxy headers (Nginx dual-format handling)
- Verifies bot User Agent + IP match against authoritative ranges
- Groups by domain, page type (homepage vs internal), and health status
- Writes atomic JSON output (temp file + rename)

**Output Structure:**
```json
{
  "date": "2026-02-23",
  "processed_at": "2026-02-24T01:00:00Z",
  "bots": {
    "example.com": {
      "googlebot": {
        "homepage": {"healthy": 10, "not_healthy": 0},
        "internal": {"healthy": 25, "not_healthy": 1}
      },
      "bingbot": {
        "homepage": {"healthy": 5, "not_healthy": 0},
        "internal": {"healthy": 12, "not_healthy": 0}
      }
    }
  }
}
```

**Automation:**
```bash
# Add to crontab to run hourly (already configured by setup_tracking_wordpress/hugo)
0 * * * * /usr/bin/python3 /var/lib/pageview-tracking/scripts/process_server_logs.py
```

---

## PHP Web Viewer

### index.php

Overview of all dates with aggregated statistics.

**URL:** `http://your-domain.com/pageview-tracking/php/index.php`

**Displays:**
- Date (clickable to view details)
- Total pageviews
- Qualified pageviews (engaged users)
- Pageviews with metrics
- Domains tracked
- Performance stats (TTFB, DCL, Load) - avg/median/p95
- Bot signals count

**Setup:**
```bash
# Option 1: PHP built-in server (development)
cd pageview-tracking/php
php -S localhost:8080

# Option 2: Apache/Nginx (production)
# Point document root to pageview-tracking/php/
# Or create a symlink in your web root
```

---

### day.php

Detailed statistics for a specific date.

**URL:** `http://your-domain.com/pageview-tracking/php/day.php?date=2026-01-29`

**Displays:**
- Per-domain breakdown
- Homepage vs internal page stats
- Qualified pageviews per domain/group
- Performance metrics by group
- Bot signals by type
- Domain filter dropdown

**Features:**
- Filter by domain
- Expandable domain groups
- Totals row
- Color-coded sections

---

## Data Structure

### Raw Logs (JSONL)

**pageview.jsonl:**
```json
{"vid":"uuid","url":"...","ref":"...","lang":"en-US","tz":"America/New_York","ua":"...","vw":1920,"vh":1080,"ts_pv":1234567890,"ip":"1.2.3.4","int":0}
```

**metrics.jsonl:**
```json
{"vid":"uuid","ts_m":1234567890,"ttfb":50,"dcl":200,"load":500}
```

**engagement.jsonl:**
```json
{"vid":"uuid","t_pg":30000,"scr_d":75,"scr_e":12}
```
- `t_pg` = time_on_page_ms (milliseconds user spent on page)
- `scr_d` = scroll_depth (0-100, percentage of page scrolled)
- `scr_e` = scroll_events (number of scroll actions)

**bots.jsonl:**
```json
{"vid":"uuid","url":"...","ip":"1.2.3.4","ua":"...","bot":["gb_ip","gb_ua"],"int":0}
```

### Aggregated Data (JSON)

**{date}.json:**
```json
{
  "date": "2026-01-29",
  "processed_at": "2026-01-30T01:00:00",
  "domains": {
    "example.com": {
      "groups": [
        {
          "is_internal": 0,
          "pageviews": 100,
          "qualified_pageviews": 85,
          "pageviews_with_metrics": 95,
          "bots": {"gb_ip": 5, "gb_ua": 3},
          "performance": {
            "ttfb": {"avg": 50, "median": 45, "p95": 80, "count": 95},
            "dcl": {"avg": 200, "median": 180, "p95": 350, "count": 95},
            "load": {"avg": 500, "median": 450, "p95": 800, "count": 95}
          }
        },
        {
          "is_internal": 1,
          "pageviews": 200,
          ...
        }
      ]
    }
  }
}
```

---

## Qualified Pageviews

**Definition:** A pageview is considered "qualified" if the user showed meaningful engagement with the page.

**Criteria:**
```
qualified_pageview = (time_on_page_ms >= 5000) AND (scroll_depth > 0 OR scroll_events >= 1)
```

**Explanation:**
- User must spend at least 5 seconds on the page (not a bounce)
- User must show some scroll activity (either scrolled to any depth > 0% OR performed at least 1 scroll action)

**Use Cases:**
- Filter out bounces and accidental clicks
- Measure genuine user engagement
- Calculate more accurate conversion metrics
- Identify quality traffic sources

---

## Troubleshooting

**No data in web viewer:**
- Check `/var/lib/pageview-tracking/agg/daily/` exists
- Run `python3 process_daily_logs.py` to generate aggregated data
- Verify raw logs exist in `/var/lib/pageview-tracking/raw/`

**Processor finds no data:**
- Check raw logs directory: `ls -lhR /var/lib/pageview-tracking/raw/`
- Verify tracking is enabled: `TRACKING_ENABLED=true` in `.env`
- Check file permissions

**Web viewer shows errors:**
- Verify PHP has read access to `/var/lib/pageview-tracking/agg/`
- Check PHP error logs
- Ensure JSON files are valid: `cat /var/lib/pageview-tracking/agg/daily/2026-01-29.json | jq`

