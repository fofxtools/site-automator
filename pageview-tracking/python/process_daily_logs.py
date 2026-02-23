#!/usr/bin/env python3
"""
Process raw pageview logs into daily aggregated statistics.

Input:  /var/lib/pageview-tracking/raw/{domain}/{date}/*.jsonl
Output: /var/lib/pageview-tracking/agg/daily/{date}.json

Usage:
    python3 process_daily_logs.py           # Process all dates
    python3 process_daily_logs.py --force   # Reprocess all dates
"""

import json
import os
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict
from statistics import mean, median, quantiles
from typing import Dict, List, Any

# Configuration
RAW_ROOT = Path("/var/lib/pageview-tracking/raw")
AGG_ROOT = Path("/var/lib/pageview-tracking/agg/daily")


def process_domain_date(domain: str, date: str) -> Dict[str, Any]:
    """Process logs for one domain+date combination"""
    
    domain_dir = RAW_ROOT / domain / date
    
    # Initialize aggregation buckets by is_internal (0=homepage, 1=internal)
    groups = {
        0: {
            'pageviews': 0,
            'qualified_pageviews': 0,
            'pageviews_with_metrics': 0,
            'bot_signals': defaultdict(int),
            'ttfb': [], 'dcl': [], 'load': []
        },
        1: {
            'pageviews': 0,
            'qualified_pageviews': 0,
            'pageviews_with_metrics': 0,
            'bot_signals': defaultdict(int),
            'ttfb': [], 'dcl': [], 'load': []
        }
    }
    
    # Load metrics into memory (indexed by vid)
    metrics_by_vid = {}
    metrics_file = domain_dir / 'metrics.jsonl'
    if metrics_file.exists():
        with open(metrics_file) as f:
            for line in f:
                try:
                    m = json.loads(line)
                    metrics_by_vid[m['vid']] = m
                except (json.JSONDecodeError, KeyError):
                    continue

    # Load engagement into memory (indexed by vid)
    engagement_by_vid = {}
    engagement_file = domain_dir / 'engagement.jsonl'
    if engagement_file.exists():
        with open(engagement_file) as f:
            for line in f:
                try:
                    e = json.loads(line)
                    engagement_by_vid[e['vid']] = e
                except (json.JSONDecodeError, KeyError):
                    continue
    
    # Process pageviews
    pageview_file = domain_dir / 'pageview.jsonl'
    if pageview_file.exists():
        with open(pageview_file) as f:
            for line in f:
                try:
                    pv = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # Get vid (skip if missing)
                vid = pv.get('vid')
                if not vid:
                    continue

                # Get is_internal from log (trust the logged value, force to int)
                is_int = 1 if pv.get('int') else 0

                # Count pageview
                groups[is_int]['pageviews'] += 1

                # Check if qualified (has engagement data meeting criteria)
                if vid in engagement_by_vid:
                    e = engagement_by_vid[vid]
                    time_on_page = e.get('t_pg', 0)
                    scroll_depth = e.get('scr_d', 0)
                    scroll_events = e.get('scr_e', 0)

                    # qualified_pageview = time_on_page_ms >= 5000 AND (scroll_depth > 0 OR scroll_events >= 1)
                    if time_on_page >= 5000 and (scroll_depth > 0 or scroll_events >= 1):
                        groups[is_int]['qualified_pageviews'] += 1

                # If has metrics, collect performance data
                if vid in metrics_by_vid:
                    m = metrics_by_vid[vid]
                    groups[is_int]['pageviews_with_metrics'] += 1

                    if m.get('ttfb') is not None:
                        groups[is_int]['ttfb'].append(m['ttfb'])
                    if m.get('dcl') is not None:
                        groups[is_int]['dcl'].append(m['dcl'])
                    if m.get('load') is not None:
                        groups[is_int]['load'].append(m['load'])
    
    # Process bots (server-side tracking)
    bots_file = domain_dir / 'bots.jsonl'
    if bots_file.exists():
        with open(bots_file) as f:
            for line in f:
                try:
                    b = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # Force is_internal to int 0/1
                is_int = 1 if b.get('int') else 0
                for signal in b.get('bot', []):
                    groups[is_int]['bot_signals'][signal] += 1
    
    # Calculate stats for each group
    result = {'groups': []}
    
    for is_int in [0, 1]:
        g = groups[is_int]
        
        group_stats = {
            'is_internal': is_int,
            'pageviews': g['pageviews'],
            'qualified_pageviews': g['qualified_pageviews'],
            'pageviews_with_metrics': g['pageviews_with_metrics'],
            'bots': dict(g['bot_signals']),
            'performance': {
                'ttfb': calc_stats(g['ttfb']),
                'dcl': calc_stats(g['dcl']),
                'load': calc_stats(g['load']),
            }
        }
        
        result['groups'].append(group_stats)
    
    return result


def calc_stats(values: List[float]) -> Dict[str, Any]:
    """Calculate avg, median, p95 for a list of values"""
    if not values:
        return {'avg': None, 'median': None, 'p95': None, 'count': 0}
    
    return {
        'avg': mean(values),
        'median': median(values),
        'p95': quantiles(values, n=100)[94] if len(values) >= 2 else values[0],
        'count': len(values)
    }


def write_atomic(path: Path, data: Dict[str, Any]):
    """Write JSON file atomically (temp + rename)"""
    temp_path = path.with_suffix('.tmp')
    with open(temp_path, 'w') as f:
        json.dump(data, f, indent=2)
    os.rename(temp_path, path)


def discover_domain_date_pairs() -> List[tuple]:
    """Discover all (domain, date) pairs in raw data"""
    pairs = []

    if not RAW_ROOT.exists():
        return pairs

    for domain_dir in RAW_ROOT.iterdir():
        if not domain_dir.is_dir():
            continue
        domain = domain_dir.name

        for date_dir in domain_dir.iterdir():
            if not date_dir.is_dir():
                continue
            date = date_dir.name
            pairs.append((domain, date))

    return pairs


def process_all(force: bool = False):
    """Process all dates"""

    # Ensure output directory exists
    AGG_ROOT.mkdir(parents=True, exist_ok=True)

    # Discover all domain+date pairs
    pairs = discover_domain_date_pairs()

    if not pairs:
        print("No data found in", RAW_ROOT)
        return

    # Group by date
    dates_to_domains = defaultdict(list)
    for domain, date in pairs:
        dates_to_domains[date].append(domain)

    # Get today's date (UTC) for comparison
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Process each date
    processed_count = 0
    skipped_count = 0

    for date in sorted(dates_to_domains.keys()):
        output_file = AGG_ROOT / f'{date}.json'

        # Skip if already processed (unless today or --force)
        if output_file.exists() and date != today and not force:
            skipped_count += 1
            continue

        # Process all domains for this date
        date_stats = {
            'date': date,
            'processed_at': datetime.now(timezone.utc).isoformat(),
            'domains': {}
        }

        for domain in sorted(dates_to_domains[date]):
            domain_stats = process_domain_date(domain, date)
            date_stats['domains'][domain] = domain_stats

        # Write output atomically
        write_atomic(output_file, date_stats)

        domain_count = len(dates_to_domains[date])
        print(f"✓ {date}: {domain_count} domains → {output_file}")
        processed_count += 1

    # Summary
    print()
    print(f"Processed: {processed_count} dates")
    if skipped_count > 0:
        print(f"Skipped: {skipped_count} dates (already processed, use --force to reprocess)")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Process raw pageview logs into daily aggregated statistics"
    )
    parser.add_argument("--force", action="store_true",
                       help="Reprocess all dates (even if already processed)")

    args = parser.parse_args()

    process_all(force=args.force)

