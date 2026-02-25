#!/usr/bin/env python3
"""Process Nginx/Caddy access logs and extract verified bot statistics.

Outputs {TRACKING_DATA_ROOT}/logs/{date}.json with per-domain bot counts.
Verified = both UA and IP match (no UA-only "claimed" bots).

Usage:
    python3 process_server_logs.py                    # Process yesterday
    python3 process_server_logs.py --all              # Process all dates (skip existing)
    python3 process_server_logs.py --all --force      # Process all dates (overwrite existing)
    python3 process_server_logs.py --date 2026-02-23  # Process specific date
    python3 process_server_logs.py --date 2026-02-23 --force  # Reprocess specific date
    python3 process_server_logs.py --date 2026-02-23 --log-dir ./tmp/var_log_caddy --output-dir ./tmp/logs
"""

import argparse
import gzip
import importlib.util
import ipaddress
import json
import os
import re
import struct
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


# Configuration
TRACKING_ROOT = "/var/lib/pageview-tracking"


# ---------------------------------------------------------------------------
# IP ranges loading + bot checker (adapted from log_analyzer.py)
# ---------------------------------------------------------------------------


def _load_ip_ranges(module_path: str) -> dict[str, Any]:
    spec = importlib.util.spec_from_file_location("_ip_mod", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {module_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod.IP_RANGES  # type: ignore[attr-defined]


def _build_ipv4_intervals(ranges_dict: dict) -> list[tuple[int, int]]:
    intervals = [(int(e["start"]), int(e["end"])) for e in ranges_dict.get("ipv4", [])]
    intervals.sort()
    return intervals


def _build_ipv6_networks(ranges_dict: dict) -> list[ipaddress.IPv6Network]:
    return [ipaddress.IPv6Network(e["cidr"]) for e in ranges_dict.get("ipv6", [])]


def _ip_to_int(ip_str: str) -> int:
    return struct.unpack("!I", ipaddress.IPv4Address(ip_str).packed)[0]


def _in_ipv4_intervals(ip_int: int, intervals: list[tuple[int, int]]) -> bool:
    lo, hi = 0, len(intervals) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        start, end = intervals[mid]
        if ip_int < start:
            hi = mid - 1
        elif ip_int > end:
            lo = mid + 1
        else:
            return True
    return False


def _in_ipv6_networks(addr: ipaddress.IPv6Address, nets: list[ipaddress.IPv6Network]) -> bool:
    return any(addr in net for net in nets)


class BotIPChecker:
    def __init__(self, google_path: str, bing_path: str) -> None:
        g = _load_ip_ranges(google_path)
        b = _load_ip_ranges(bing_path)
        self._google_v4 = _build_ipv4_intervals(g)
        self._google_v6 = _build_ipv6_networks(g)
        self._bing_v4 = _build_ipv4_intervals(b)
        self._bing_v6 = _build_ipv6_networks(b)

    def is_google_ip(self, ip: str) -> bool:
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return False
        if isinstance(addr, ipaddress.IPv4Address):
            return _in_ipv4_intervals(_ip_to_int(ip), self._google_v4)
        return _in_ipv6_networks(addr, self._google_v6)  # type: ignore[arg-type]

    def is_bing_ip(self, ip: str) -> bool:
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return False
        if isinstance(addr, ipaddress.IPv4Address):
            return _in_ipv4_intervals(_ip_to_int(ip), self._bing_v4)
        return _in_ipv6_networks(addr, self._bing_v6)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# UA detection
# ---------------------------------------------------------------------------


def _is_googlebot_ua(ua: str) -> bool:
    return "googlebot" in ua.lower()


def _is_bingbot_ua(ua: str) -> bool:
    ua_l = ua.lower()
    return "bingbot" in ua_l or "bingpreview" in ua_l


# ---------------------------------------------------------------------------
# Log parsing
# ---------------------------------------------------------------------------

# Nginx dual-format regex (validated against 770K production log lines):
#
# Format A (catch-all vhost):   ip - - [date] real_ip "METHOD path proto" ... (60,977 lines)
#   real_ip may be empty → double space before the quoted request
#
# Format B (domain vhosts):     ip time cache [date] domain "METHOD path proto" ... (709,297 lines)
#
# group 3 (field5) is the 5th space-separated token: empty string, IPv4, or domain name.
# If it looks like an IPv4 address → use as real_ip; otherwise use ip1 (group 1).
_NGINX_RE = re.compile(
    r'^(\S+)\s+\S+\s+\S+\s+\[([^\]]+)\]\s*(\S*)\s*"(\S+)\s+(\S+)\s+[^"]+"\s+(\d{3})\s+\S+\s+"[^"]*"\s+"([^"]*)"'
)
_IPV4_RE = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")


def _parse_nginx_line(line: str) -> dict | None:
    """Parse a Nginx log line (handles Format A catch-all and Format B domain vhosts).

    field5 (group 3) determines the real client IP:
      - IPv4 address → use as real_ip (Format A with forwarded header)
      - domain name or empty → use ip1 (Format B, or Format A with no forwarded IP)
    """
    m = _NGINX_RE.match(line)
    if not m:
        return None
    ip1, date_str, field5, method, path, status_str, ua = m.groups()
    real_ip = field5 if _IPV4_RE.match(field5) else ip1
    try:
        dt = datetime.strptime(date_str, "%d/%b/%Y:%H:%M:%S %z")
    except ValueError:
        return None
    return {
        "ip": real_ip,
        "date": dt.date(),
        "method": method,
        "path": path,
        "status": int(status_str),
        "ua": ua,
    }


def _parse_caddy_line(line: str) -> dict | None:
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        return None
    try:
        ts = float(obj["ts"])
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        req = obj["request"]
        ip = req.get("client_ip") or req.get("remote_ip", "")
        ua_list = req.get("headers", {}).get("User-Agent") or [""]
        return {
            "ip": ip,
            "date": dt.date(),
            "method": req.get("method", ""),
            "path": req.get("uri", ""),
            "status": int(obj.get("status", 0)),
            "ua": ua_list[0] if ua_list else "",
            "host": req.get("host", ""),
        }
    except (KeyError, TypeError, ValueError):
        return None


def _detect_caddy(line: str) -> bool:
    try:
        obj = json.loads(line)
        return "ts" in obj and "request" in obj
    except Exception:
        return False


def _open_log(path: str):
    if path.endswith(".gz"):
        return gzip.open(path, "rt", errors="replace")
    return open(path, "r", errors="replace")


def _domain_from_nginx_filename(filepath: str) -> str:
    """Extract domain from Nginx log filename.

    Examples:
        apache-monitor.com.access.log     → apache-monitor.com
        apache-monitor.com.access.log.1   → apache-monitor.com
        apache-monitor.com.access.log.2.gz → apache-monitor.com
        22222.access.log                   → 22222
    """
    name = Path(filepath).name
    if name.endswith(".gz"):
        name = name[:-3]
    idx = name.find(".access.log")
    if idx > 0:
        return name[:idx]
    return name


# ---------------------------------------------------------------------------
# Core processing
# ---------------------------------------------------------------------------

_DOMAIN_STATS_TEMPLATE = lambda: {  # noqa: E731
    "googlebot": {
        "homepage": {"healthy": 0, "not_healthy": 0},
        "internal": {"healthy": 0, "not_healthy": 0},
    },
    "bingbot": {
        "homepage": {"healthy": 0, "not_healthy": 0},
        "internal": {"healthy": 0, "not_healthy": 0},
    },
}


def process_log_files(
    log_files: list[str], checker: BotIPChecker, target_date: date | None = None
) -> dict[date, dict] | dict:
    """Process log files and return bot stats.

    Args:
        log_files: List of log file paths to process
        checker: BotIPChecker instance for IP verification
        target_date: If set, only process this date. If None, process all dates.

    Returns:
        If target_date is None: dict[date, dict] mapping dates to bot stats
        If target_date is set: dict with bot stats for that date only

        Bot stats format: {domain: {bot_type: {page_type: {health: count}}}}
    """
    if target_date is None:
        # All-dates mode: collect stats for every date
        all_stats: dict[date, dict] = defaultdict(lambda: defaultdict(_DOMAIN_STATS_TEMPLATE))
        entries_checked = 0
        bots_found = 0

        for log_path in log_files:
            is_caddy: bool | None = None
            nginx_domain = _domain_from_nginx_filename(log_path)

            try:
                with _open_log(log_path) as f:
                    for raw_line in f:
                        line = raw_line.rstrip("\n")
                        if not line:
                            continue

                        if is_caddy is None:
                            is_caddy = _detect_caddy(line)

                        if is_caddy:
                            entry = _parse_caddy_line(line)
                            if entry is None:
                                continue
                            domain = entry.get("host") or nginx_domain
                        else:
                            entry = _parse_nginx_line(line)
                            if entry is None:
                                continue
                            domain = nginx_domain

                        entries_checked += 1
                        entry_date = entry["date"]
                        ip = entry["ip"]
                        ua = entry["ua"]
                        status = entry["status"]
                        path = entry["path"]

                        # Verified bot: both UA and IP must match
                        if _is_googlebot_ua(ua) and checker.is_google_ip(ip):
                            bot_type = "googlebot"
                        elif _is_bingbot_ua(ua) and checker.is_bing_ip(ip):
                            bot_type = "bingbot"
                        else:
                            continue

                        bots_found += 1
                        page_type = "homepage" if path.split("?")[0] == "/" else "internal"
                        health = "healthy" if status < 400 else "not_healthy"
                        all_stats[entry_date][domain][bot_type][page_type][health] += 1

            except Exception as exc:
                print(f"  Warning: {log_path}: {exc}", file=sys.stderr)

        print(
            f"  Scanned {len(log_files)} file(s), {entries_checked} entries, "
            f"{bots_found} verified bot hits across {len(all_stats)} dates"
        )
        # Convert defaultdicts to regular dicts
        return {d: dict(stats) for d, stats in all_stats.items()}

    else:
        # Single-date mode: only collect stats for target_date
        stats: dict = defaultdict(_DOMAIN_STATS_TEMPLATE)
        entries_checked = 0
        bots_found = 0

        for log_path in log_files:
            is_caddy: bool | None = None
            nginx_domain = _domain_from_nginx_filename(log_path)

            try:
                with _open_log(log_path) as f:
                    for raw_line in f:
                        line = raw_line.rstrip("\n")
                        if not line:
                            continue

                        if is_caddy is None:
                            is_caddy = _detect_caddy(line)

                        if is_caddy:
                            entry = _parse_caddy_line(line)
                            if entry is None:
                                continue
                            domain = entry.get("host") or nginx_domain
                        else:
                            entry = _parse_nginx_line(line)
                            if entry is None:
                                continue
                            domain = nginx_domain

                        if entry["date"] != target_date:
                            continue

                        entries_checked += 1
                        ip = entry["ip"]
                        ua = entry["ua"]
                        status = entry["status"]
                        path = entry["path"]

                        # Verified bot: both UA and IP must match
                        if _is_googlebot_ua(ua) and checker.is_google_ip(ip):
                            bot_type = "googlebot"
                        elif _is_bingbot_ua(ua) and checker.is_bing_ip(ip):
                            bot_type = "bingbot"
                        else:
                            continue

                        bots_found += 1
                        page_type = "homepage" if path.split("?")[0] == "/" else "internal"
                        health = "healthy" if status < 400 else "not_healthy"
                        stats[domain][bot_type][page_type][health] += 1

            except Exception as exc:
                print(f"  Warning: {log_path}: {exc}", file=sys.stderr)

        print(
            f"  Scanned {len(log_files)} file(s), {entries_checked} entries on {target_date}, "
            f"{bots_found} verified bot hits"
        )
        return dict(stats)


def find_log_files(log_dirs: list[str]) -> list[str]:
    """Collect all access log files (including .gz) from given directories."""
    files = []
    for d in log_dirs:
        p = Path(d)
        if not p.is_dir():
            print(f"  Skipping missing directory: {d}", file=sys.stderr)
            continue
        for f in sorted(p.iterdir()):
            if f.is_file() and "access" in f.name:
                files.append(str(f))
    return files


def find_ranges(ranges_dir: str | None, script_dir: str) -> tuple[str, str]:
    """Locate google_ip_ranges.py and bing_ip_ranges.py."""
    candidates = []
    if ranges_dir:
        candidates.append(ranges_dir)
    candidates.append(script_dir)
    # Local dev: script in pageview-tracking/python/, ranges in project-root/scripts/
    candidates.append(os.path.normpath(os.path.join(script_dir, "..", "..", "scripts")))

    for d in candidates:
        g = os.path.join(d, "google_ip_ranges.py")
        b = os.path.join(d, "bing_ip_ranges.py")
        if os.path.exists(g) and os.path.exists(b):
            return g, b

    raise FileNotFoundError(
        f"Cannot find google_ip_ranges.py / bing_ip_ranges.py. Searched: {candidates}"
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Process Nginx/Caddy access logs for verified bot statistics."
    )
    parser.add_argument(
        "--date",
        default=None,
        metavar="YYYY-MM-DD",
        help="Date to process (default: yesterday).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all dates found in log files (last 30 days).",
    )
    parser.add_argument(
        "--log-dir",
        dest="log_dirs",
        action="append",
        default=[],
        metavar="DIR",
        help="Log directory to scan. Can be given multiple times.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        metavar="DIR",
        help="Output directory (default: $TRACKING_DATA_ROOT/logs).",
    )
    parser.add_argument(
        "--ranges-dir",
        default=None,
        metavar="DIR",
        help="Directory containing google_ip_ranges.py / bing_ip_ranges.py.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing output file.",
    )
    args = parser.parse_args()

    # --- output directory ---
    output_dir = args.output_dir or os.path.join(TRACKING_ROOT, "logs")
    os.makedirs(output_dir, exist_ok=True)

    # --- IP ranges ---
    script_dir = str(Path(__file__).parent)
    try:
        google_path, bing_path = find_ranges(args.ranges_dir, script_dir)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"IP ranges: {google_path}")
    print(f"           {bing_path}")

    checker = BotIPChecker(google_path, bing_path)

    # --- log files ---
    log_dirs = args.log_dirs or ["/var/log/caddy", "/var/log/nginx"]
    log_files = find_log_files(log_dirs)
    print(f"Log dirs:  {log_dirs}")
    print(f"Log files: {len(log_files)} found")

    if not log_files:
        print("No log files found — nothing to do.", file=sys.stderr)
        sys.exit(1)

    # --- process logs ---
    if args.all:
        # All-dates mode: single pass through all log files
        print("\nProcessing all dates (single-pass)...")
        all_date_stats = process_log_files(log_files, checker, target_date=None)

        if not all_date_stats:
            print("No bot data found in log files.")
            sys.exit(0)

        # Write one JSON file per date
        print(f"\nWriting {len(all_date_stats)} date files...")
        processed_count = 0
        skipped_count = 0
        processed_at = datetime.now(tz=timezone.utc).isoformat()

        for target_date in sorted(all_date_stats.keys()):
            bot_stats = all_date_stats[target_date]
            output_file = os.path.join(output_dir, f"{target_date}.json")

            # Skip if file exists and --force not set
            if os.path.exists(output_file) and not args.force:
                print(f"  Skipped {target_date} (already processed)")
                skipped_count += 1
                continue

            output = {
                "date": str(target_date),
                "processed_at": processed_at,
                "bots": bot_stats,
            }

            with open(output_file, "w") as f:
                json.dump(output, f, indent=2)

            # Summary for this date
            total_gb = sum(
                sum(v for pg in bots["googlebot"].values() for v in pg.values())
                for bots in bot_stats.values()
            )
            total_bb = sum(
                sum(v for pg in bots["bingbot"].values() for v in pg.values())
                for bots in bot_stats.values()
            )
            print(f"  {target_date}: {len(bot_stats)} domains, googlebot={total_gb}, bingbot={total_bb}")
            processed_count += 1

        print(f"\nProcessed: {processed_count} dates")
        if skipped_count > 0:
            print(f"Skipped:   {skipped_count} dates (use --force to reprocess)")

    else:
        # Single-date mode: process specific date only
        if args.date:
            target_date = date.fromisoformat(args.date)
        else:
            target_date = date.today() - timedelta(days=1)

        print(f"Target date: {target_date}")

        output_file = os.path.join(output_dir, f"{target_date}.json")

        if os.path.exists(output_file) and not args.force:
            print(f"Already processed: {output_file}  (use --force to reprocess)")
            sys.exit(0)

        # Process logs for single date
        bot_stats = process_log_files(log_files, checker, target_date=target_date)

        output = {
            "date": str(target_date),
            "processed_at": datetime.now(tz=timezone.utc).isoformat(),
            "bots": bot_stats,
        }

        with open(output_file, "w") as f:
            json.dump(output, f, indent=2)

        print(f"Output:    {output_file}")

        # Summary
        if bot_stats:
            print("\nSummary:")
            for domain, bots in sorted(bot_stats.items()):
                gb = sum(v for pg in bots["googlebot"].values() for v in pg.values())
                bb = sum(v for pg in bots["bingbot"].values() for v in pg.values())
                print(f"  {domain:40s}  googlebot={gb:4d}  bingbot={bb:4d}")
        else:
            print("\nNo verified bot hits found.")


if __name__ == "__main__":
    main()
