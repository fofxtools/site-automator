#!/usr/bin/env python3
"""Convert Nginx access logs to Caddy-style JSON format.

Reads Nginx access log files (including .gz compressed) from an input directory
and writes one-JSON-object-per-line output files to an output directory.

Nginx-specific fields (upstream_response_time, cache_status) are preserved as
extra top-level keys. Caddy fields not present in Nginx logs are omitted.

First download Nginx logs:
    rsync -avz {server-alias}:/var/log/nginx/ ./storage/nginx/

Usage:
    python scripts/log_nginx_to_json.py --input-dir storage/nginx --output-dir storage/json-logs
"""

import argparse
import gzip
import json
import re
import sys
from collections.abc import Generator
from datetime import datetime
from pathlib import Path
from typing import Any, TextIO

# Custom log format (with host, upstream fields, trailing proto/extra):
#   $remote_addr $upstream_response_time $upstream_cache_status
#   [$time_local] $host
#   "$request" $status $body_bytes_sent
#   "$http_referer" "$http_user_agent" "$server_protocol" "$extra"
NGINX_CUSTOM_RE = re.compile(
    r"^"
    r"(\S+)\s+"  # 1: remote_addr
    r"(\S+)\s+"  # 2: upstream_response_time (number or -)
    r"(\S+)\s+"  # 3: upstream_cache_status  (HIT/MISS/STALE/- etc)
    r"\[([^\]]+)\]\s+"  # 4: time_local
    r"(\S+)\s+"  # 5: host
    r'"(.*?)"\s+'  # 6: request line (METHOD URI PROTO)
    r"(\d+)\s+"  # 7: status
    r"(\d+)\s+"  # 8: body_bytes_sent
    r'"(.*?)"\s+'  # 9: http_referer
    r'"(.*?)"\s+'  # 10: http_user_agent
    r'"([^"]*)"\s+'  # 11: server_protocol
    r'"([^"]*)"'  # 12: extra
    r"$"
)

# Same custom format but with an empty host (double space before request):
#   $remote_addr $upstream_time $cache_status [$time_local]  "$request" ...
NGINX_CUSTOM_NOHOST_RE = re.compile(
    r"^"
    r"(\S+)\s+"  # 1: remote_addr
    r"(\S+)\s+"  # 2: upstream_response_time
    r"(\S+)\s+"  # 3: upstream_cache_status
    r"\[([^\]]+)\]\s+"  # 4: time_local
    r'"(.*?)"\s+'  # 5: request line (no host before it)
    r"(\d+)\s+"  # 6: status
    r"(\d+)\s+"  # 7: body_bytes_sent
    r'"(.*?)"\s+'  # 8: http_referer
    r'"(.*?)"\s+'  # 9: http_user_agent
    r'"([^"]*)"\s+'  # 10: server_protocol
    r'"([^"]*)"'  # 11: extra
    r"$"
)

# Standard Nginx combined format (no host, no upstream, no trailing fields):
#   $remote_addr - $remote_user [$time_local]
#   "$request" $status $body_bytes_sent
#   "$http_referer" "$http_user_agent"
NGINX_COMBINED_RE = re.compile(
    r"^"
    r"(\S+)\s+"  # 1: remote_addr
    r"(\S+)\s+"  # 2: remote_user (usually -)
    r"(\S+)\s+"  # 3: auth user  (usually -)
    r"\[([^\]]+)\]\s+"  # 4: time_local
    r'"(.*?)"\s+'  # 5: request line
    r"(\d+)\s+"  # 6: status
    r"(\d+)\s+"  # 7: body_bytes_sent
    r'"(.*?)"\s+'  # 8: http_referer
    r'"(.*?)"'  # 9: http_user_agent
    r"$"
)


def parse_timestamp(time_str: str) -> float:
    """Convert '15/Feb/2026:00:03:39 +0000' to Unix epoch float."""
    dt = datetime.strptime(time_str, "%d/%b/%Y:%H:%M:%S %z")
    return dt.timestamp()


def parse_request_line(request_line: str) -> tuple[str, str, str]:
    """Split 'GET /path HTTP/1.1' into (method, uri, proto)."""
    parts = request_line.split(" ", 2)
    if len(parts) == 3:
        return parts[0], parts[1], parts[2]
    if len(parts) == 2:
        return parts[0], parts[1], ""
    return request_line, "", ""


def _try_custom(line: str) -> dict[str, str] | None:
    """Try the custom format with host field."""
    m = NGINX_CUSTOM_RE.match(line)
    if not m:
        return None
    (
        remote_addr,
        upstream_time,
        cache_status,
        time_local,
        host,
        request_line,
        status,
        body_bytes,
        referer,
        user_agent,
        _server_protocol,
        _extra,
    ) = m.groups()
    return dict(
        remote_addr=remote_addr,
        upstream_time=upstream_time,
        cache_status=cache_status,
        time_local=time_local,
        host=host,
        request_line=request_line,
        status=status,
        body_bytes=body_bytes,
        referer=referer,
        user_agent=user_agent,
    )


def _try_custom_nohost(line: str) -> dict[str, str] | None:
    """Try the custom format with empty/missing host."""
    m = NGINX_CUSTOM_NOHOST_RE.match(line)
    if not m:
        return None
    (
        remote_addr,
        upstream_time,
        cache_status,
        time_local,
        request_line,
        status,
        body_bytes,
        referer,
        user_agent,
        _server_protocol,
        _extra,
    ) = m.groups()
    return dict(
        remote_addr=remote_addr,
        upstream_time=upstream_time,
        cache_status=cache_status,
        time_local=time_local,
        host="",
        request_line=request_line,
        status=status,
        body_bytes=body_bytes,
        referer=referer,
        user_agent=user_agent,
    )


def _try_combined(line: str) -> dict[str, str] | None:
    """Try standard Nginx combined format (no host, no upstream fields)."""
    m = NGINX_COMBINED_RE.match(line)
    if not m:
        return None
    (
        remote_addr,
        _remote_user,
        _auth_user,
        time_local,
        request_line,
        status,
        body_bytes,
        referer,
        user_agent,
    ) = m.groups()
    return dict(
        remote_addr=remote_addr,
        upstream_time="-",
        cache_status="-",
        time_local=time_local,
        host="",
        request_line=request_line,
        status=status,
        body_bytes=body_bytes,
        referer=referer,
        user_agent=user_agent,
    )


def convert_line(line: str) -> dict[str, Any] | None:
    """Convert one Nginx access log line to a Caddy-style dict. Returns None on failure."""
    line = line.strip()
    if not line:
        return None

    fields = _try_custom(line) or _try_custom_nohost(line) or _try_combined(line)
    if not fields:
        return None

    method, uri, proto = parse_request_line(fields["request_line"])

    # Build request.headers (only include what Nginx logs)
    headers: dict[str, list[str]] = {}
    if fields["user_agent"] and fields["user_agent"] != "-":
        headers["User-Agent"] = [fields["user_agent"]]
    if fields["referer"] and fields["referer"] != "-":
        headers["Referer"] = [fields["referer"]]

    # Build request object
    request: dict[str, Any] = {
        "remote_ip": fields["remote_addr"],
        "client_ip": fields["remote_addr"],
        "proto": proto,
        "method": method,
        "host": fields["host"],
        "uri": uri,
    }
    if headers:
        request["headers"] = headers

    # Build the entry
    entry = {
        "level": "info",
        "ts": parse_timestamp(fields["time_local"]),
        "logger": "http.log.access",
        "msg": "handled request",
        "request": request,
        "size": int(fields["body_bytes"]),
        "status": int(fields["status"]),
    }

    # Nginx-specific fields (kept when present)
    upstream_time = fields["upstream_time"]
    if upstream_time != "-":
        try:
            entry["upstream_response_time"] = float(upstream_time)
        except ValueError:
            entry["upstream_response_time"] = upstream_time

    cache_status = fields["cache_status"]
    if cache_status != "-":
        entry["cache_status"] = cache_status

    return entry


def open_log(path: Path) -> TextIO:
    """Open a plain or gzip-compressed log file for reading."""
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return open(path, "r", encoding="utf-8", errors="replace")


def convert_file(input_path: Path, output_path: Path) -> tuple[int, int]:
    """Convert one log file. Returns (converted, failed) counts."""
    converted = 0
    failed = 0

    with open_log(input_path) as infile, open(output_path, "w") as outfile:
        for lineno, line in enumerate(infile, 1):
            entry = convert_line(line)
            if entry is not None:
                json.dump(entry, outfile, separators=(",", ":"))
                outfile.write("\n")
                converted += 1
            elif line.strip():
                failed += 1
                preview = line.strip()[:120]
                print(f"  WARN line {lineno}: {preview}", file=sys.stderr)

    return converted, failed


def find_access_logs(input_dir: Path) -> Generator[Path, None, None]:
    """Yield Path objects for all Nginx access log files in input_dir."""
    for p in sorted(input_dir.iterdir()):
        if not p.is_file():
            continue
        if "error" in p.name:
            continue
        # Match: *.access.log, *.access.log.1, *.access.log.2.gz, etc.
        if "access" in p.name:
            yield p


def output_name(filename: str) -> str:
    """Derive the JSON output filename from the input log filename.

    Examples:
        camcon.org.access.log       -> camcon.org.access.log
        camcon.org.access.log.1     -> camcon.org.access.log.1
        camcon.org.access.log.2.gz  -> camcon.org.access.log.2
    """
    name = filename
    if name.endswith(".gz"):
        name = name[:-3]
    return name


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert Nginx access logs to Caddy-style JSON format"
    )
    parser.add_argument(
        "--input-dir", required=True, help="Directory containing Nginx log files"
    )
    parser.add_argument(
        "--output-dir", required=True, help="Directory for converted JSON output"
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    if not input_dir.is_dir():
        print(f"Error: {input_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    log_files = list(find_access_logs(input_dir))
    if not log_files:
        print("No access log files found.", file=sys.stderr)
        sys.exit(1)

    total_converted = 0
    total_failed = 0

    for log_file in log_files:
        out_name = output_name(log_file.name)
        out_path = output_dir / out_name

        print(f"{log_file.name}  ->  {out_name}")
        converted, failed = convert_file(log_file, out_path)
        total_converted += converted
        total_failed += failed
        print(f"  {converted} converted, {failed} failed")

    print(f"\nTotal: {total_converted} converted, {total_failed} failed")


if __name__ == "__main__":
    main()
