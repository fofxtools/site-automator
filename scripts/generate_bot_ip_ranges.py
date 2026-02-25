#!/usr/bin/env python3
"""
Generate Bot IP Range Arrays

Reads bot IP ranges from multiple JSON sources and generates Python files
with hardcoded arrays for fast IP checking.

Supported bots:
  - Google (Googlebot crawler)
  - Bing (Bingbot, Microsoft ARIN registry)

Input files (from resources/):
  Google:
    - googlebot.json (Googlebot crawler IPs)
  Bing:
    - bing.com-toolbox-bingbot.json
    - whois.arin.net-rest-nets-q-microsoft.json (ARIN registry)

To generate the whois.arin.net-rest-nets-q-{company}.json files, run:
    - scripts/fetch_and_convert_ip_ranges.py

Output files (to scripts/):
  - google_ip_ranges.py
  - bing_ip_ranges.py
"""

import ipaddress
import json
from pathlib import Path
from typing import Any, TypedDict


class BotConfig(TypedDict):
    """Configuration for a bot's IP range sources."""

    output: Path
    title: str
    sources: dict[str, Path]
    sources_description: list[str]


def process_bot_sources(sources: dict[str, Path]) -> dict[str, list[dict[str, Any]]]:
    """
    Process bot sources and return IPv4/IPv6 ranges

    Args:
        sources: Dictionary mapping source names to file paths

    Returns:
        Dictionary with 'ipv4' and 'ipv6' keys containing range lists
    """
    ipv4_ranges = []
    ipv6_ranges = []

    for source_name, file_path in sources.items():
        with open(file_path, "r") as f:
            data = json.load(f)

        if "prefixes" not in data or not isinstance(data["prefixes"], list):
            print(
                f"    ⚠ Warning: Invalid JSON structure in {file_path.name}, skipping"
            )
            continue

        for prefix in data["prefixes"]:
            if "ipv4Prefix" in prefix:
                cidr = prefix["ipv4Prefix"]

                try:
                    # Parse CIDR notation
                    ipv4_network = ipaddress.IPv4Network(cidr, strict=False)

                    # Calculate start and end IP addresses as integers
                    start_int = int(ipv4_network.network_address)
                    end_int = int(ipv4_network.broadcast_address)

                    # Store as zero-padded 10-digit strings (32-bit safe)
                    start = f"{start_int:010d}"
                    end = f"{end_int:010d}"

                    ipv4_ranges.append(
                        {
                            "start": start,
                            "end": end,
                            "cidr": cidr,
                            "source": source_name,
                        }
                    )
                except (ValueError, ipaddress.AddressValueError):
                    # Skip invalid IP addresses
                    continue

            elif "ipv6Prefix" in prefix:
                cidr = prefix["ipv6Prefix"]

                try:
                    # Parse to validate
                    ipv6_network = ipaddress.IPv6Network(cidr, strict=False)
                    prefix_len = ipv6_network.prefixlen

                    ipv6_ranges.append(
                        {
                            "cidr": cidr,
                            "prefix_length": prefix_len,
                            "source": source_name,
                        }
                    )
                except (ValueError, ipaddress.AddressValueError):
                    # Skip invalid IP addresses
                    continue

    # Sort IPv4 ranges by start address
    ipv4_ranges.sort(key=lambda x: x["start"])

    # Sort IPv6 ranges by CIDR
    ipv6_ranges.sort(key=lambda x: x["cidr"])

    # Remove duplicates while preserving sources
    ipv4_ranges = merge_duplicates(ipv4_ranges, "ipv4")
    ipv6_ranges = merge_duplicates(ipv6_ranges, "ipv6")

    return {
        "ipv4": ipv4_ranges,
        "ipv6": ipv6_ranges,
    }


def merge_duplicates(
    ranges: list[dict[str, Any]], range_type: str
) -> list[dict[str, Any]]:
    """
    Merge duplicate ranges, combining sources

    Args:
        ranges: List of range dictionaries
        range_type: 'ipv4' or 'ipv6'

    Returns:
        List of merged ranges
    """
    seen: dict[str, dict[str, Any]] = {}

    if range_type == "ipv4":
        for range_item in ranges:
            key = f"{range_item['start']}-{range_item['end']}"
            if key in seen:
                # Duplicate found - merge sources
                if range_item["source"] not in seen[key]["sources"]:
                    seen[key]["sources"].append(range_item["source"])
            else:
                seen[key] = {
                    "start": range_item["start"],
                    "end": range_item["end"],
                    "cidr": range_item["cidr"],
                    "sources": [range_item["source"]],
                }
    else:  # ipv6
        for range_item in ranges:
            key = range_item["cidr"]
            if key in seen:
                # Duplicate found - merge sources
                if range_item["source"] not in seen[key]["sources"]:
                    seen[key]["sources"].append(range_item["source"])
            else:
                seen[key] = {
                    "cidr": range_item["cidr"],
                    "prefix_length": range_item["prefix_length"],
                    "sources": [range_item["source"]],
                }

    return list(seen.values())


def generate_python_file(
    ipv4_ranges: list[dict[str, Any]],
    ipv6_ranges: list[dict[str, Any]],
    title: str,
    sources_description: list[str],
) -> str:
    """
    Generate Python file content

    Args:
        ipv4_ranges: List of IPv4 range dictionaries
        ipv6_ranges: List of IPv6 range dictionaries
        title: Title for the Python file
        sources_description: List of source descriptions

    Returns:
        Python file content as string
    """
    lines = []

    # Header comment
    lines.append(f"# {title}")
    lines.append("#")
    lines.append("# Generated by: generate_bot_ip_ranges.py")
    lines.append("#")
    lines.append("# Sources:")
    for desc in sources_description:
        lines.append(f"# - {desc}")
    lines.append("#")
    lines.append(f"# Total IPv4 ranges: {len(ipv4_ranges)}")
    lines.append(f"# Total IPv6 ranges: {len(ipv6_ranges)}")
    lines.append("")

    # Start IP_RANGES dictionary
    lines.append("IP_RANGES = {")
    lines.append('    "ipv4": [')

    # IPv4 ranges
    for range_item in ipv4_ranges:
        sources_str = '", "'.join(range_item["sources"])
        lines.append(
            f'        {{"start": "{range_item["start"]}", '
            f'"end": "{range_item["end"]}", '
            f'"cidr": "{range_item["cidr"]}", '
            f'"sources": ["{sources_str}"]}},'
        )

    lines.append("    ],")
    lines.append("")
    lines.append('    "ipv6": [')

    # IPv6 ranges
    for range_item in ipv6_ranges:
        sources_str = '", "'.join(range_item["sources"])
        lines.append(
            f'        {{"cidr": "{range_item["cidr"]}", '
            f'"prefix_length": {range_item["prefix_length"]}, '
            f'"sources": ["{sources_str}"]}},'
        )

    lines.append("    ],")
    lines.append("}")
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    print("Bot IP Range Generator")
    print("=" * 50)
    print()

    # Get directories
    script_dir = Path(__file__).parent
    resources_dir = script_dir.parent / "resources"
    output_dir = script_dir

    # Configuration: bot sources
    bots: dict[str, BotConfig] = {
        "google": {
            "output": output_dir / "google_ip_ranges.py",
            "title": "Google IP Ranges",
            "sources": {
                "googlebot": resources_dir / "googlebot.json",
            },
            "sources_description": [
                "developers.google.com/static/search/apis/ipranges/googlebot.json (Googlebot crawler)",
            ],
        },
        "bing": {
            "output": output_dir / "bing_ip_ranges.py",
            "title": "Bing IP Ranges",
            "sources": {
                "arin": resources_dir / "whois.arin.net-rest-nets-q-microsoft.json",
                "bingbot": resources_dir / "bing.com-toolbox-bingbot.json",
            },
            "sources_description": [
                "ARIN whois registry (Microsoft)",
                "bing.com/toolbox/bingbot.json (Bingbot crawler)",
            ],
        },
    }

    # Process each bot
    for bot_name, config in bots.items():
        print(f"Processing {bot_name.capitalize()}...")

        # Verify all input files exist
        valid_sources = {}
        for source_name, file_path in config["sources"].items():
            if not file_path.exists():
                print(f"  ⚠ Warning: Input file not found: {file_path} (skipping)")
            else:
                valid_sources[source_name] = file_path

        if not valid_sources:
            print(f"  ✗ No valid sources found for {bot_name}, skipping\n")
            continue

        # Process this bot's sources
        result = process_bot_sources(valid_sources)

        # Generate Python file
        output_content = generate_python_file(
            result["ipv4"],
            result["ipv6"],
            config["title"],
            config["sources_description"],
        )

        config["output"].write_text(output_content)

        print(f"  ✓ IPv4: {len(result['ipv4'])} ranges")
        print(f"  ✓ IPv6: {len(result['ipv6'])} ranges")
        print(f"  ✓ Output: {config['output'].name}")
        print()

    print("=" * 50)
    print("✓ Complete!")
