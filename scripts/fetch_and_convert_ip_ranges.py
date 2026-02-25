#!/usr/bin/env python3
"""
Fetch IP range data and convert ARIN XML to JSON format

Downloads IP range data from various sources and converts ARIN whois XML files
to JSON format matching the structure of gstatic.com JSON files.

Processes:
  - Google (Googlebot JSON file)
  - Microsoft (ARIN XML)
  - Bing (JSON file)

Output files (saved to resources/):
  - googlebot.json
  - whois.arin.net-rest-nets-q-microsoft.xml
  - whois.arin.net-rest-nets-q-microsoft.json (converted from XML)
  - bing.com-toolbox-bingbot.json
"""

import ipaddress
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import requests


def download_file(url: str, output_path: Path) -> bool:
    """Download a file using requests"""
    try:
        print(f"  Downloading {output_path.name}...")
        response = requests.get(url)
        response.raise_for_status()

        output_path.write_bytes(response.content)
        print(f"  ✓ Downloaded {output_path.name}")
        return True
    except requests.RequestException as e:
        print(f"  ✗ Failed to download {output_path.name}: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Error downloading {output_path.name}: {e}")
        return False


def download_arin_xml(company: str, output_path: Path) -> bool:
    """Download ARIN XML data"""
    try:
        print(f"  Downloading ARIN data for {company}...")
        url = f"https://whois.arin.net/rest/nets;q={company}?showDetails=true&showARIN=true&showNonArinTopLevelNet=false&ext=netref2"

        response = requests.get(url)
        response.raise_for_status()

        output_path.write_bytes(response.content)
        print(f"  ✓ Downloaded ARIN XML for {company}")
        return True
    except requests.RequestException as e:
        print(f"  ✗ Failed to download ARIN XML for {company}: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Error downloading ARIN XML for {company}: {e}")
        return False


def convert_arin_xml_to_json(xml_path: Path, json_path: Path) -> bool:
    """Convert ARIN XML to JSON format matching gstatic.com structure"""
    try:
        print(f"  Converting {xml_path.name} to JSON...")

        # Parse XML
        tree = ET.parse(xml_path)
        root = tree.getroot()

        # Define namespace
        ns = {"ns": "https://www.arin.net/whoisrws/core/v1"}

        # Find all netBlock elements
        net_blocks = root.findall(".//ns:netBlock", ns)

        if not net_blocks:
            print(f"  ✗ No netBlock elements found in {xml_path.name}")
            return False

        ipv4_cidrs = []
        ipv6_cidrs = []

        # Extract CIDR ranges
        for net_block in net_blocks:
            start_address = net_block.find("ns:startAddress", ns)
            cidr_length = net_block.find("ns:cidrLength", ns)

            if start_address is not None and cidr_length is not None:
                start_addr = start_address.text
                cidr_len = cidr_length.text

                if start_addr and cidr_len:
                    cidr = f"{start_addr}/{cidr_len}"

                    # Separate IPv4 and IPv6 (with validation)
                    try:
                        addr = ipaddress.ip_address(start_addr)
                        if addr.version == 6:
                            ipv6_cidrs.append(cidr)
                        else:
                            ipv4_cidrs.append(cidr)
                    except ValueError:
                        # Invalid IP address, skip
                        continue

        # Sort and deduplicate
        ipv4_cidrs = sorted(set(ipv4_cidrs))
        ipv6_cidrs = sorted(set(ipv6_cidrs))

        # Build prefixes array in gstatic.com format
        prefixes = []

        for cidr in ipv4_cidrs:
            prefixes.append({"ipv4Prefix": cidr})

        for cidr in ipv6_cidrs:
            prefixes.append({"ipv6Prefix": cidr})

        # Create JSON structure
        output = {"prefixes": prefixes}

        # Write JSON with pretty formatting
        with open(json_path, "w") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
            f.write("\n")

        print(f"  ✓ IPv4: {len(ipv4_cidrs)} ranges")
        print(f"  ✓ IPv6: {len(ipv6_cidrs)} ranges")
        print(f"  ✓ Total: {len(prefixes)} prefixes")
        print(f"  ✓ Output: {json_path.name}")

        return True
    except Exception as e:
        print(f"  ✗ Error converting {xml_path.name}: {e}")
        return False


if __name__ == "__main__":
    print("IP Range Fetcher and Converter")
    print("=" * 50)
    print()

    # Get resources directory
    script_dir = Path(__file__).parent
    resources_dir = script_dir.parent / "resources"
    resources_dir.mkdir(exist_ok=True)

    # Download Google data
    print("Processing Google...")
    download_file(
        "https://developers.google.com/static/search/apis/ipranges/googlebot.json",
        resources_dir / "googlebot.json",
    )
    print()

    # Download Microsoft data
    print("Processing Microsoft...")
    download_arin_xml(
        "microsoft", resources_dir / "whois.arin.net-rest-nets-q-microsoft.xml"
    )
    print()

    # Download Bing data
    print("Processing Bing...")
    download_file(
        "https://www.bing.com/toolbox/bingbot.json",
        resources_dir / "bing.com-toolbox-bingbot.json",
    )
    print()

    # Convert ARIN XML files to JSON
    print("=" * 50)
    print("Converting ARIN XML to JSON")
    print("=" * 50)
    print()

    for company in ["microsoft"]:
        print(f"Processing {company}...")
        xml_file = resources_dir / f"whois.arin.net-rest-nets-q-{company}.xml"
        json_file = resources_dir / f"whois.arin.net-rest-nets-q-{company}.json"

        if xml_file.exists():
            convert_arin_xml_to_json(xml_file, json_file)
        else:
            print("  ⚠ Skipping: XML file not found")
        print()

    print("=" * 50)
    print("✓ Complete!")
