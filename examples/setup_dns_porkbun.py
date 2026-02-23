#!/usr/bin/env python3
"""Set up DNS using Porkbun DNS (no external DNS provider needed).

This script configures DNS records directly at Porkbun, pointing to a DigitalOcean droplet.
No need for DigitalOcean DNS zones or nameserver changes.

Usage:
    python examples/setup_dns_porkbun.py --site-id example_com
"""

import argparse
import logging
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from site_automator.utils import configure_logging
from site_automator.sites import load_site_config
from site_automator.registrars import RegistrarNameserverManager
from site_automator.ssh import resolve_ssh_host

configure_logging()
logger = logging.getLogger(__name__)


def main() -> None:
    """Set up DNS using Porkbun DNS."""
    load_dotenv()

    parser = argparse.ArgumentParser(description="Set up DNS using Porkbun DNS")
    parser.add_argument("--site-id", required=True, help="Site ID from sites.csv")
    args = parser.parse_args()

    site = load_site_config(args.site_id)
    domain = site["domain"]
    registrar = site["registrar"]
    server = site["server"]

    if registrar != "porkbun":
        logger.error(
            f"This script only works with Porkbun domains. {domain} is registered at {registrar}"
        )
        sys.exit(1)

    # Resolve SSH host to get server IP
    server_ip, _, _ = resolve_ssh_host(server)

    logger.info(f"Setting up Porkbun DNS for {domain}")
    logger.info(f"  Server: {server} ({server_ip})")

    # Configure DNS records at Porkbun
    registrars = RegistrarNameserverManager.from_env()

    # Set apex A record (example.com → server IP)
    registrars.set_porkbun_dns_a_record(domain, server_ip)

    # Set www CNAME (www.example.com → example.com)
    registrars.set_porkbun_dns_cname(domain, domain, subdomain="www")

    logger.info(f"\nSUCCESS: DNS configured for {domain}")
    logger.info(f"  {domain} → {server_ip}")
    logger.info(f"  www.{domain} → {domain}")
    logger.info("\nNo nameserver changes needed - using Porkbun DNS directly")


if __name__ == "__main__":
    start_time = time.perf_counter()
    main()
    end_time = time.perf_counter()
    elapsed_time = end_time - start_time
    print(f"Total time elapsed: {elapsed_time:.2f} seconds")
