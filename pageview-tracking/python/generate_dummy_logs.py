#!/usr/bin/env python3
"""
Generate dummy pageview tracking logs for testing.

Generates random test data for the last few days.
Domains: *.test (example.com.test, shop.test, blog.test)
Output: /var/lib/pageview-tracking/raw/{domain}.test/{date}/

Usage:
    python3 generate_dummy_logs.py           # Generate test data
    python3 generate_dummy_logs.py --cleanup # Remove test data
"""

import json
import random
import uuid
import shutil
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Tuple, Any

# Configuration
DATA_ROOT = Path("/var/lib/pageview-tracking/raw")
AGG_ROOT = Path("/var/lib/pageview-tracking/agg/daily")

# Test domains with different traffic patterns
DOMAINS = [
    "example.com.test",
    "shop.test",
    "blog.test",
]

# Page templates by domain type
PAGES = {
    "example.com.test": [
        ("/", 0.30),
        ("/about", 0.15),
        ("/contact", 0.10),
        ("/services", 0.15),
        ("/pricing", 0.10),
        ("/blog/post-{}", 0.20),
    ],
    "shop.test": [
        ("/", 0.20),
        ("/products/item-{}", 0.40),
        ("/category/electronics", 0.10),
        ("/category/clothing", 0.10),
        ("/cart", 0.10),
        ("/checkout", 0.10),
    ],
    "blog.test": [
        ("/", 0.20),
        ("/post/{}/title-here", 0.50),
        ("/category/tech", 0.10),
        ("/category/lifestyle", 0.10),
        ("/about", 0.05),
        ("/archive", 0.05),
    ],
}

# Device distributions (viewport_width, viewport_height, type, weight)
DEVICES = [
    (1920, 1080, "desktop", 0.35),
    (1440, 900, "desktop", 0.15),
    (2560, 1440, "desktop", 0.10),
    (393, 852, "mobile", 0.15),
    (412, 915, "mobile", 0.10),
    (375, 667, "mobile", 0.05),
    (1024, 1366, "tablet", 0.10),
]

USER_AGENTS = {
    "desktop": [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    ],
    "mobile": [
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    ],
    "tablet": [
        "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    ],
}

LANGUAGES = [
    ("en-US", 0.70),
    ("en-GB", 0.10),
    ("fr-FR", 0.05),
    ("de-DE", 0.05),
    ("es-ES", 0.05),
    ("ja-JP", 0.05),
]

TIMEZONES = [
    ("America/New_York", 0.50),
    ("Europe/London", 0.20),
    ("Europe/Paris", 0.10),
    ("Asia/Tokyo", 0.10),
    ("America/Los_Angeles", 0.10),
]

REFERRERS = [
    ("", 0.40),  # Direct
    ("https://google.com/search?q=test", 0.15),
    ("https://www.google.com/search?q=example", 0.15),
    ("https://www.facebook.com/", 0.10),
    ("https://twitter.com/", 0.10),
    ("https://www.bing.com/search?q=test", 0.05),
    ("https://news.ycombinator.com/", 0.05),
]

# Bot signal distributions
BOT_SIGNALS = [
    (["gb_ip", "g_ip", "gb_ua"], 0.05),  # Googlebot
    (["bb_ip", "ms_ip", "bb_ua"], 0.03),  # Bingbot
    (["g_ip"], 0.05),  # Google (not bot)
    (["ms_ip"], 0.02),  # Microsoft (not bot)
]


def weighted_choice(choices: List[Tuple[Any, ...]]) -> Any:
    """
    Choose from weighted list.
    Supports both (value, weight) and (val1, val2, ..., weight) tuples.
    Weight is always the last element.
    """
    total = sum(choice[-1] for choice in choices)
    r = random.uniform(0, total)
    cumulative = 0
    for choice in choices:
        weight = choice[-1]
        cumulative += weight
        if r <= cumulative:
            # Return all values except the weight
            return choice[:-1] if len(choice) > 2 else choice[0]  # type: ignore
    # Fallback to last choice
    return choices[-1][:-1] if len(choices[-1]) > 2 else choices[-1][0]  # type: ignore


def generate_pageview(domain: str, base_ts: int, offset_ms: int) -> Dict:
    """Generate a single pageview entry"""
    # Choose page based on domain
    page_template = weighted_choice(PAGES[domain])
    if "{}" in page_template:
        page = page_template.format(random.randint(1, 999))
    else:
        page = page_template

    url = f"http://{domain}{page}"
    is_internal = 1 if (page and page != '/') else 0

    # Choose device
    device = weighted_choice(DEVICES)
    vw, vh, device_type = device
    ua = random.choice(USER_AGENTS[device_type])

    # Choose language/timezone
    lang = weighted_choice(LANGUAGES)
    tz = weighted_choice(TIMEZONES)

    # Choose referrer
    ref = weighted_choice(REFERRERS)

    # Generate view ID
    vid = str(uuid.uuid4())

    # Timestamp
    ts_pv = base_ts + offset_ms

    # Generate realistic IP
    ip = f"192.168.{random.randint(1,254)}.{random.randint(1,254)}"

    return {
        "vid": vid,
        "url": url,
        "ref": ref,
        "lang": lang,
        "tz": tz,
        "ua": ua,
        "vw": vw,
        "vh": vh,
        "ts_pv": ts_pv,
        "ip": ip,
        "int": is_internal,
    }


def generate_metrics(vid: str, base_ts: int, offset_ms: int) -> Dict | None:
    """Generate metrics for a pageview (95% of the time)"""
    if random.random() < 0.05:  # 5% missing metrics
        return None

    # Realistic performance metrics (normal distribution)
    ttfb = max(10, int(random.gauss(100, 30)))
    dcl = max(50, int(random.gauss(400, 150)))
    load = max(100, int(random.gauss(800, 300)))

    ts_m = base_ts + offset_ms + random.randint(100, 500)

    return {
        "vid": vid,
        "ts_m": ts_m,
        "ttfb": ttfb,
        "dcl": dcl,
        "load": load,
    }


def generate_bot(is_internal: int, bot_ratio: float) -> Dict | None:
    """Generate bot entry (bot_ratio % of the time)"""
    if random.random() > bot_ratio:
        return None

    signals = weighted_choice(BOT_SIGNALS)

    return {
        "int": is_internal,
        "bot": signals,
    }


def generate_engagement(vid: str) -> Dict | None:
    """Generate engagement data for a pageview (90% of the time)"""
    if random.random() < 0.10:  # 10% bounce immediately (no engagement)
        return None

    # Realistic engagement metrics
    # time_on_page_ms: 0-300000ms (0-5 minutes), weighted toward 10-60s
    # Most users spend 10-60 seconds, some bounce quickly, some stay longer
    time_distribution = [
        (1000, 0.05),    # 1s (quick bounce)
        (3000, 0.10),    # 3s (very quick)
        (10000, 0.20),   # 10s (typical quick read)
        (30000, 0.30),   # 30s (engaged reading)
        (60000, 0.20),   # 1 min (good engagement)
        (120000, 0.10),  # 2 min (very engaged)
        (300000, 0.05),  # 5 min (deep engagement)
    ]
    base_time = weighted_choice(time_distribution)
    # Add some randomness around the base time
    time_on_page = max(0, int(base_time + random.gauss(0, base_time * 0.2)))

    # scroll_depth: 0-100, weighted toward 20-80%
    # Most users scroll partway through the page
    scroll_distribution = [
        (0, 0.05),    # No scroll (just landed)
        (20, 0.15),   # Scrolled a bit
        (40, 0.20),   # Scrolled to middle
        (60, 0.25),   # Good scroll
        (80, 0.20),   # Almost complete
        (100, 0.15),  # Full scroll
    ]
    base_scroll = weighted_choice(scroll_distribution)
    # Add some randomness
    scroll_depth = max(0, min(100, int(base_scroll + random.gauss(0, 10))))

    # scroll_events: 0-50, weighted toward 5-15
    # Number of scroll actions (not micro-scrolls, but distinct scroll movements)
    scroll_events_distribution = [
        (0, 0.05),   # No scrolling
        (3, 0.15),   # Few scrolls
        (8, 0.30),   # Typical scrolling
        (15, 0.30),  # Active scrolling
        (25, 0.15),  # Very active
        (50, 0.05),  # Excessive scrolling
    ]
    base_events = weighted_choice(scroll_events_distribution)
    # Add some randomness
    scroll_events = max(0, int(base_events + random.gauss(0, 3)))

    return {
        "vid": vid,
        "t_pg": time_on_page,
        "scr_d": scroll_depth,
        "scr_e": scroll_events,
    }


def generate_logs_for_domain(domain: str, date: str, count: int, bot_ratio: float = 0.15):
    """Generate dummy logs for a specific domain and date"""

    output_dir = DATA_ROOT / domain / date
    output_dir.mkdir(parents=True, exist_ok=True)

    pageview_file = output_dir / "pageview.jsonl"
    metrics_file = output_dir / "metrics.jsonl"
    bots_file = output_dir / "bots.jsonl"
    engagement_file = output_dir / "engagement.jsonl"

    # Base timestamp for the date (UTC)
    dt = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    base_ts = int(dt.timestamp() * 1000)

    print(f"  {domain}: generating {count:,} pageviews...")

    with open(pageview_file, 'w') as pv_f, \
         open(metrics_file, 'w') as m_f, \
         open(bots_file, 'w') as b_f, \
         open(engagement_file, 'w') as e_f:

        for i in range(count):
            # Spread pageviews throughout the day
            offset_ms = random.randint(0, 86400000)  # 0-24 hours in ms

            # Generate pageview
            pv = generate_pageview(domain, base_ts, offset_ms)
            pv_f.write(json.dumps(pv) + '\n')

            # Generate metrics (95% of the time)
            metrics = generate_metrics(pv['vid'], base_ts, offset_ms)
            if metrics:
                m_f.write(json.dumps(metrics) + '\n')

            # Generate engagement (90% of the time)
            engagement = generate_engagement(pv['vid'])
            if engagement:
                e_f.write(json.dumps(engagement) + '\n')

            # Generate bot entry (bot_ratio % of the time)
            bot = generate_bot(pv['int'], bot_ratio)
            if bot:
                b_f.write(json.dumps(bot) + '\n')

    pv_size = pageview_file.stat().st_size
    m_size = metrics_file.stat().st_size
    b_size = bots_file.stat().st_size
    e_size = engagement_file.stat().st_size

    print(f"    ✓ {pv_size:,} bytes (pageview.jsonl)")
    print(f"    ✓ {m_size:,} bytes (metrics.jsonl)")
    print(f"    ✓ {e_size:,} bytes (engagement.jsonl)")
    print(f"    ✓ {b_size:,} bytes (bots.jsonl)")


def generate_logs_for_date(date: str):
    """Generate dummy logs for all test domains for a single date"""

    print(f"Date: {date}")

    total_pageviews = 0
    for domain in DOMAINS:
        # Random count for each domain
        count = random.randint(800, 1200)
        bot_ratio = 0.15  # 15% bot traffic
        generate_logs_for_domain(domain, date, count, bot_ratio)
        total_pageviews += count

    print(f"  ✓ {total_pageviews:,} pageviews for {date}")
    return total_pageviews


def generate_logs():
    """Generate dummy logs for multiple dates"""

    print("Generating dummy logs")
    print(f"Domains: {', '.join(DOMAINS)}")
    print()

    # Generate from 4 days ago up to today (UTC) = 5 days total
    count = 5
    grand_total = 0
    for days_ago in range(count - 1, -1, -1):  # 4, 3, 2, 1, 0
        date = (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        total = generate_logs_for_date(date)
        grand_total += total
        print()

    print(f"✓ Generated {grand_total:,} total pageviews across {len(DOMAINS)} domains and {count} dates")


def cleanup():
    """Remove all dummy data (*.test domains)"""
    removed_raw_count = 0
    removed_agg_count = 0

    # Clean up raw logs
    if DATA_ROOT.exists():
        for domain_dir in DATA_ROOT.iterdir():
            if domain_dir.is_dir() and domain_dir.name.endswith('.test'):
                print(f"Removing raw logs: {domain_dir}...")
                shutil.rmtree(domain_dir)
                removed_raw_count += 1

    # Clean up aggregated data for test domains
    if AGG_ROOT.exists():
        for agg_file in AGG_ROOT.glob('*.json'):
            # Read the file to check if it contains only test domains
            try:
                with open(agg_file) as f:
                    data = json.load(f)

                domains = data.get('domains', {})
                if not domains:
                    continue

                # Check if all domains are test domains
                all_test = all(domain.endswith('.test') for domain in domains.keys())

                if all_test:
                    print(f"Removing aggregated data: {agg_file}...")
                    agg_file.unlink()
                    removed_agg_count += 1
            except (json.JSONDecodeError, OSError):
                continue

    # Summary
    if removed_raw_count > 0 or removed_agg_count > 0:
        print(f"✓ Removed {removed_raw_count} test domain(s) from raw logs")
        print(f"✓ Removed {removed_agg_count} aggregated file(s) with only test data")
    else:
        print("No test data found (*.test)")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate dummy pageview logs for testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate random test data for last few days
  python3 generate_dummy_logs.py

  # Clean up all test data
  python3 generate_dummy_logs.py --cleanup
        """
    )

    parser.add_argument("--cleanup", action="store_true",
                       help="Remove all test data (*.test domains)")

    args = parser.parse_args()

    if args.cleanup:
        cleanup()
    else:
        generate_logs()

