#!/usr/bin/env python3
"""Caddy/Nginx JSON access log analyzer.

Reads JSON log files, applies exclusions from log_config.py, classifies requests
by Googlebot/Bingbot (UA match, IP match, UA+IP match), and writes daily
summary JSON files.

First download Caddy JSON logs:
    rsync -avz {server-alias}:/var/log/caddy/ ./storage/json-logs/

Usage:
    python scripts/log_analyzer.py --input-dir storage/json-logs --output-dir storage/json-logs/summaries
"""

import argparse
import glob
import gzip
import ipaddress
import json
import os
import struct
import sys
from collections import defaultdict
from collections.abc import Generator
from datetime import datetime, timezone
from typing import Any

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

import log_config

# ---------------------------------------------------------------------------
# Bot IP loading
# ---------------------------------------------------------------------------


def _load_ip_ranges(module_path: str) -> dict[str, Any]:
    """Import an IP ranges module by path and return its IP_RANGES dict."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("_ip_mod", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {module_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    ip_ranges: dict[str, Any] = mod.IP_RANGES
    return ip_ranges


def _build_ipv4_intervals(ranges_dict: dict[str, Any]) -> list[tuple[int, int]]:
    """Return sorted list of (start_int, end_int) from the IP_RANGES ipv4 list."""
    intervals = []
    for entry in ranges_dict.get("ipv4", []):
        intervals.append((int(entry["start"]), int(entry["end"])))
    intervals.sort()
    return intervals


def _build_ipv6_networks(ranges_dict: dict[str, Any]) -> list[ipaddress.IPv6Network]:
    """Return list of ipaddress.IPv6Network from the IP_RANGES ipv6 list."""
    networks = []
    for entry in ranges_dict.get("ipv6", []):
        networks.append(ipaddress.IPv6Network(entry["cidr"]))
    return networks


def _ip_to_int(ip_str: str) -> int:
    """Convert dotted-quad IPv4 string to integer."""
    result: int = struct.unpack("!I", ipaddress.IPv4Address(ip_str).packed)[0]
    return result


def _in_ipv4_intervals(ip_int: int, intervals: list[tuple[int, int]]) -> bool:
    """Binary search for ip_int in sorted (start, end) intervals."""
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


def _in_ipv6_networks(
    addr: ipaddress.IPv6Address, networks: list[ipaddress.IPv6Network]
) -> bool:
    """Check if an IPv6Address is in any of the networks."""
    for net in networks:
        if addr in net:
            return True
    return False


class BotIPChecker:
    """Checks whether an IP belongs to Google or Bing ranges."""

    def __init__(self, google_ranges_path: str, bing_ranges_path: str) -> None:
        google_ranges = _load_ip_ranges(google_ranges_path)
        bing_ranges = _load_ip_ranges(bing_ranges_path)

        self._google_v4 = _build_ipv4_intervals(google_ranges)
        self._google_v6 = _build_ipv6_networks(google_ranges)
        self._bing_v4 = _build_ipv4_intervals(bing_ranges)
        self._bing_v6 = _build_ipv6_networks(bing_ranges)

    def is_google_ip(self, ip_str: str) -> bool:
        try:
            addr = ipaddress.ip_address(ip_str)
        except ValueError:
            return False
        if isinstance(addr, ipaddress.IPv4Address):
            return _in_ipv4_intervals(_ip_to_int(ip_str), self._google_v4)
        return _in_ipv6_networks(addr, self._google_v6)

    def is_bing_ip(self, ip_str: str) -> bool:
        try:
            addr = ipaddress.ip_address(ip_str)
        except ValueError:
            return False
        if isinstance(addr, ipaddress.IPv4Address):
            return _in_ipv4_intervals(_ip_to_int(ip_str), self._bing_v4)
        return _in_ipv6_networks(addr, self._bing_v6)


# ---------------------------------------------------------------------------
# Exclusion helpers
# ---------------------------------------------------------------------------


def _build_exclude_networks(
    cidr_list: list[str],
) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    nets: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for cidr in cidr_list:
        nets.append(ipaddress.ip_network(cidr, strict=False))
    return nets


def _is_excluded(
    entry: dict[str, Any],
    ip_str: str,
    ua: str,
    path: str,
    exclude_nets: list[ipaddress.IPv4Network | ipaddress.IPv6Network],
) -> bool:
    """Return True if this log entry should be excluded based on config."""
    if ip_str in log_config.exclude_ips:
        return True

    if exclude_nets:
        try:
            addr = ipaddress.ip_address(ip_str)
            for net in exclude_nets:
                if addr in net:
                    return True
        except ValueError:
            pass

    if ua:
        if ua in log_config.exclude_user_agents_exact:
            return True
        ua_lower = ua.lower()
        for sub in log_config.exclude_user_agents_substring:
            if sub.lower() in ua_lower:
                return True

    status = entry.get("status")
    if status in log_config.exclude_status_codes:
        return True

    if path in log_config.exclude_paths:
        return True

    return False


# ---------------------------------------------------------------------------
# Noise detection
# ---------------------------------------------------------------------------

NOISE_EXTENSIONS = (
    ".css",
    ".js",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".ico",
    ".webp",
    ".woff",
    ".woff2",
    ".ttf",
    ".map",
    ".json",
    ".xml",
)

NOISE_PATH_PREFIXES = (
    "/wp-includes/",
    "/wp-content/",
    "/wp-admin/",
    "/wp-json/",
    "/static/",
    "/assets/",
    "/.well-known/",
    "/.git/",
    "/api/",
)

NOISE_PATHS_EXACT = (
    "/wp-cron.php",
    "/wp-login.php",
    "/wp-trackback.php",
)


def _is_noise(path: str) -> bool:
    """Return True if this path represents noise (not content)."""
    # Exact matches
    if path in NOISE_PATHS_EXACT:
        return True

    # Path prefixes
    for prefix in NOISE_PATH_PREFIXES:
        if path.startswith(prefix):
            return True

    # Extension check
    path_lower = path.lower()
    for ext in NOISE_EXTENSIONS:
        if path_lower.endswith(ext):
            return True

    # PHP files at root level (e.g., /admin.php, /shell.php)
    # But allow query params (e.g., /?p=123)
    if path.startswith("/") and not path.startswith("//"):
        parts = path.split("?", 1)
        base_path = parts[0]
        # Check if it's a .php file at root (no additional slashes)
        if base_path.endswith(".php") and base_path.count("/") == 1:
            return True

    # REST API via query parameter
    if "?rest_route=" in path:
        return True

    return False


# ---------------------------------------------------------------------------
# Domain normalization
# ---------------------------------------------------------------------------


def normalize_host(host: str) -> str:
    """Normalize domain by stripping www. prefix only."""
    host = host.lower().strip()
    if host.startswith("www."):
        return host[4:]
    return host


# ---------------------------------------------------------------------------
# Log parsing
# ---------------------------------------------------------------------------


def _open_log(path: str) -> gzip.GzipFile | Any:
    """Open a log file, handling .gz transparently."""
    if path.endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return open(path, "r", encoding="utf-8", errors="replace")


def _extract_fields(entry: dict[str, Any]) -> dict[str, Any] | None:
    """Extract common fields from a log entry. Returns None if unusable."""
    ts = entry.get("ts")
    if ts is None:
        return None

    req = entry.get("request")
    if not req:
        return None

    host = normalize_host(req.get("host") or "")
    if not host:
        return None

    ip = req.get("client_ip") or req.get("remote_ip") or ""
    uri = req.get("uri", "")
    path = uri.split("?", 1)[0]

    headers = req.get("headers") or {}
    ua_list = headers.get("User-Agent") or []
    ua = ua_list[0] if ua_list else ""

    status = entry.get("status")

    return {
        "ts": float(ts),
        "host": host,
        "ip": ip,
        "path": path,
        "ua": ua,
        "status": status,
    }


def stream_log_records(log_dir: str) -> Generator[dict[str, Any], None, None]:
    """Stream log records from all log files in log_dir. Yields extracted record dicts."""
    patterns = [
        os.path.join(log_dir, "*.log"),
        os.path.join(log_dir, "*.log.[0-9]*"),
        os.path.join(log_dir, "*.log.gz"),
        os.path.join(log_dir, "*.log.[0-9]*.gz"),
    ]

    files = set()
    for pat in patterns:
        files.update(glob.glob(pat))

    for fpath in sorted(files):
        with _open_log(fpath) as fh:
            for line_no, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    print(
                        f"WARNING: {fpath}:{line_no}: invalid JSON, skipping",
                        file=sys.stderr,
                    )
                    continue

                rec = _extract_fields(entry)
                if rec is None:
                    continue
                # Keep the raw entry reference for status/exclusion checks
                rec["_entry"] = entry
                yield rec


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------


def _empty_metrics() -> dict[str, Any]:
    return {
        "total_requests": 0,
        "unique_paths": set(),
        "status_counts": defaultdict(int),
        "classification": {
            "content": {
                "requests": 0,
                "unique_paths": set(),
            },
            "noise": {
                "requests": 0,
                "unique_paths": set(),
            },
            "excluded": {
                "requests": 0,
                "unique_paths": set(),
            },
        },
        "bots": {
            "googlebot": {
                "ua_matches": {
                    "requests": 0,
                    "unique_paths": set(),
                    "unique_content_paths": set(),
                },
                "ip_matches": {
                    "requests": 0,
                    "unique_paths": set(),
                    "unique_content_paths": set(),
                },
                "ua_and_ip": {
                    "requests": 0,
                    "unique_paths": set(),
                    "unique_content_paths": set(),
                },
            },
            "bingbot": {
                "ua_matches": {
                    "requests": 0,
                    "unique_paths": set(),
                    "unique_content_paths": set(),
                },
                "ip_matches": {
                    "requests": 0,
                    "unique_paths": set(),
                    "unique_content_paths": set(),
                },
                "ua_and_ip": {
                    "requests": 0,
                    "unique_paths": set(),
                    "unique_content_paths": set(),
                },
            },
            "unclassified": {
                "requests": 0,
                "unique_paths": set(),
            },
        },
    }


def _finalize_metrics(m: dict[str, Any]) -> dict[str, Any]:
    """Convert sets/defaultdicts to plain types for JSON serialization."""
    return {
        "total_requests": m["total_requests"],
        "unique_paths": len(m["unique_paths"]),
        "status_counts": dict(m["status_counts"]),
        "classification": {
            "content": {
                "requests": m["classification"]["content"]["requests"],
                "unique_paths": len(m["classification"]["content"]["unique_paths"]),
            },
            "noise": {
                "requests": m["classification"]["noise"]["requests"],
                "unique_paths": len(m["classification"]["noise"]["unique_paths"]),
            },
            "excluded": {
                "requests": m["classification"]["excluded"]["requests"],
                "unique_paths": len(m["classification"]["excluded"]["unique_paths"]),
            },
        },
        "bots": {
            "googlebot": {
                "ua_matches": {
                    "requests": m["bots"]["googlebot"]["ua_matches"]["requests"],
                    "unique_paths": len(
                        m["bots"]["googlebot"]["ua_matches"]["unique_paths"]
                    ),
                    "unique_content_paths": len(
                        m["bots"]["googlebot"]["ua_matches"]["unique_content_paths"]
                    ),
                },
                "ip_matches": {
                    "requests": m["bots"]["googlebot"]["ip_matches"]["requests"],
                    "unique_paths": len(
                        m["bots"]["googlebot"]["ip_matches"]["unique_paths"]
                    ),
                    "unique_content_paths": len(
                        m["bots"]["googlebot"]["ip_matches"]["unique_content_paths"]
                    ),
                },
                "ua_and_ip": {
                    "requests": m["bots"]["googlebot"]["ua_and_ip"]["requests"],
                    "unique_paths": len(
                        m["bots"]["googlebot"]["ua_and_ip"]["unique_paths"]
                    ),
                    "unique_content_paths": len(
                        m["bots"]["googlebot"]["ua_and_ip"]["unique_content_paths"]
                    ),
                },
            },
            "bingbot": {
                "ua_matches": {
                    "requests": m["bots"]["bingbot"]["ua_matches"]["requests"],
                    "unique_paths": len(
                        m["bots"]["bingbot"]["ua_matches"]["unique_paths"]
                    ),
                    "unique_content_paths": len(
                        m["bots"]["bingbot"]["ua_matches"]["unique_content_paths"]
                    ),
                },
                "ip_matches": {
                    "requests": m["bots"]["bingbot"]["ip_matches"]["requests"],
                    "unique_paths": len(
                        m["bots"]["bingbot"]["ip_matches"]["unique_paths"]
                    ),
                    "unique_content_paths": len(
                        m["bots"]["bingbot"]["ip_matches"]["unique_content_paths"]
                    ),
                },
                "ua_and_ip": {
                    "requests": m["bots"]["bingbot"]["ua_and_ip"]["requests"],
                    "unique_paths": len(
                        m["bots"]["bingbot"]["ua_and_ip"]["unique_paths"]
                    ),
                    "unique_content_paths": len(
                        m["bots"]["bingbot"]["ua_and_ip"]["unique_content_paths"]
                    ),
                },
            },
            "unclassified": {
                "requests": m["bots"]["unclassified"]["requests"],
                "unique_paths": len(m["bots"]["unclassified"]["unique_paths"]),
            },
        },
    }


def analyze(
    record_stream: Generator[dict[str, Any], None, None], bot_checker: BotIPChecker
) -> dict[str, Any]:
    """Analyze streaming records and return {date_str: {totals, per_domain}} summaries."""
    exclude_nets = _build_exclude_networks(log_config.exclude_ips_cidr)

    # Group by date
    by_date: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for rec in record_stream:
        dt = datetime.fromtimestamp(rec["ts"], tz=timezone.utc)
        date_str = dt.strftime("%Y-%m-%d")
        by_date[date_str].append(rec)

    summaries: dict[str, Any] = {}
    for date_str, day_records in sorted(by_date.items()):
        totals = _empty_metrics()
        per_domain: defaultdict[str, dict[str, Any]] = defaultdict(_empty_metrics)

        for rec in day_records:
            entry = rec["_entry"]
            ip = rec["ip"]
            ua = rec["ua"]
            path = rec["path"]
            host = rec["host"]
            status = rec["status"]

            dom = per_domain[host]

            # Check exclusion
            if _is_excluded(entry, ip, ua, path, exclude_nets):
                totals["classification"]["excluded"]["requests"] += 1
                totals["classification"]["excluded"]["unique_paths"].add(path)
                dom["classification"]["excluded"]["requests"] += 1
                dom["classification"]["excluded"]["unique_paths"].add(path)
                continue

            # Track totals
            totals["total_requests"] += 1
            dom["total_requests"] += 1

            totals["unique_paths"].add(path)
            dom["unique_paths"].add(path)

            status_key = str(status) if status is not None else "unknown"
            totals["status_counts"][status_key] += 1
            dom["status_counts"][status_key] += 1

            # Classify as content or noise
            is_noise_path = _is_noise(path)
            is_content = not is_noise_path

            if is_content:
                totals["classification"]["content"]["requests"] += 1
                totals["classification"]["content"]["unique_paths"].add(path)
                dom["classification"]["content"]["requests"] += 1
                dom["classification"]["content"]["unique_paths"].add(path)
            else:
                totals["classification"]["noise"]["requests"] += 1
                totals["classification"]["noise"]["unique_paths"].add(path)
                dom["classification"]["noise"]["requests"] += 1
                dom["classification"]["noise"]["unique_paths"].add(path)

            # Bot detection
            ua_lower = ua.lower() if ua else ""
            is_google_ua = "googlebot" in ua_lower
            is_bing_ua = "bingbot" in ua_lower
            is_google_ip = bot_checker.is_google_ip(ip) if ip else False
            is_bing_ip = bot_checker.is_bing_ip(ip) if ip else False

            # Track bot metrics
            def _update_bot_metrics(
                metrics: dict[str, Any],
                is_ua: bool,
                is_ip: bool,
                path: str,
                is_content: bool,
            ) -> None:
                """Update overlapping bot detection signals (NOT exclusive buckets)."""
                if not (is_ua or is_ip):
                    return

                # UA signal
                if is_ua:
                    metrics["ua_matches"]["requests"] += 1
                    metrics["ua_matches"]["unique_paths"].add(path)
                    if is_content:
                        metrics["ua_matches"]["unique_content_paths"].add(path)

                # IP signal
                if is_ip:
                    metrics["ip_matches"]["requests"] += 1
                    metrics["ip_matches"]["unique_paths"].add(path)
                    if is_content:
                        metrics["ip_matches"]["unique_content_paths"].add(path)

                # High-confidence (both signals)
                if is_ua and is_ip:
                    metrics["ua_and_ip"]["requests"] += 1
                    metrics["ua_and_ip"]["unique_paths"].add(path)
                    if is_content:
                        metrics["ua_and_ip"]["unique_content_paths"].add(path)

            _update_bot_metrics(
                totals["bots"]["googlebot"],
                is_google_ua,
                is_google_ip,
                path,
                is_content,
            )
            _update_bot_metrics(
                dom["bots"]["googlebot"], is_google_ua, is_google_ip, path, is_content
            )

            _update_bot_metrics(
                totals["bots"]["bingbot"], is_bing_ua, is_bing_ip, path, is_content
            )
            _update_bot_metrics(
                dom["bots"]["bingbot"], is_bing_ua, is_bing_ip, path, is_content
            )

            # Track unclassified requests (not detected as any bot)
            if not (is_google_ua or is_google_ip or is_bing_ua or is_bing_ip):
                totals["bots"]["unclassified"]["requests"] += 1
                totals["bots"]["unclassified"]["unique_paths"].add(path)
                dom["bots"]["unclassified"]["requests"] += 1
                dom["bots"]["unclassified"]["unique_paths"].add(path)

        summaries[date_str] = {
            "date": date_str,
            "totals": _finalize_metrics(totals),
            "per_domain": {
                d: _finalize_metrics(m) for d, m in sorted(per_domain.items())
            },
        }

    return summaries


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def write_summaries(summaries: dict[str, Any], output_dir: str) -> None:
    """Write individual daily summary files."""
    os.makedirs(output_dir, exist_ok=True)
    for date_str, summary in sorted(summaries.items()):
        fname = f"access_summary-{date_str}.json"
        path = os.path.join(output_dir, fname)
        with open(path, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"Wrote {path}")


def write_combined_summary(summaries: dict[str, Any], output_dir: str) -> None:
    """Write all dates into a single combined JSON file."""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, "access_summary-combined.json")
    with open(path, "w") as f:
        json.dump(summaries, f, indent=2)
    print(f"Wrote {path}")


def invert_summaries(summaries: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Transform from date→domain to domain→date structure."""
    by_domain: defaultdict[str, dict[str, Any]] = defaultdict(dict)

    for date_str, day_data in summaries.items():
        for domain, metrics in day_data["per_domain"].items():
            by_domain[domain][date_str] = metrics

    # Convert to regular dict with sorted domains and dates
    return {
        domain: dict(sorted(dates.items()))
        for domain, dates in sorted(by_domain.items())
    }


def write_by_domain_summary(summaries: dict[str, Any], output_dir: str) -> None:
    """Write inverted format: domain→date→metrics."""
    os.makedirs(output_dir, exist_ok=True)
    inverted = invert_summaries(summaries)
    path = os.path.join(output_dir, "access_summary-by-domain.json")
    with open(path, "w") as f:
        json.dump(inverted, f, indent=2)
    print(f"Wrote {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze Caddy/Nginx JSON access logs")
    parser.add_argument(
        "--input-dir", required=True, help="Directory containing JSON log files"
    )
    parser.add_argument(
        "--output-dir", required=True, help="Directory for summary output files"
    )
    parser.add_argument(
        "--bot-ip-dir",
        default=None,
        help="Directory containing google_ip_ranges.py and bing_ip_ranges.py "
        "(default: same directory as this script)",
    )
    args = parser.parse_args()

    bot_ip_dir = args.bot_ip_dir or os.path.dirname(os.path.abspath(__file__))
    google_path = os.path.join(bot_ip_dir, "google_ip_ranges.py")
    bing_path = os.path.join(bot_ip_dir, "bing_ip_ranges.py")

    for p in (google_path, bing_path):
        if not os.path.isfile(p):
            print(f"ERROR: Bot IP range file not found: {p}", file=sys.stderr)
            sys.exit(1)

    print("Loading bot IP ranges...")
    bot_checker = BotIPChecker(google_path, bing_path)

    print(f"Processing logs from {args.input_dir}...")
    record_stream = stream_log_records(args.input_dir)
    summaries = analyze(record_stream, bot_checker)
    print(f"Found {len(summaries)} distinct dates")

    print("\nWriting output files...")
    write_summaries(summaries, args.output_dir)
    write_combined_summary(summaries, args.output_dir)
    write_by_domain_summary(summaries, args.output_dir)
    print("Done.")


if __name__ == "__main__":
    main()
