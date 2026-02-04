#!/usr/bin/env python3
"""Set up DNS for a domain using registrar and DigitalOcean."""

import logging
import os
import sys
import time

from dotenv import load_dotenv

from site_automator.digitalocean import DigitalOceanDNSManager
from site_automator.registrars import RegistrarNameserverManager
from site_automator.sites import load_site_config_by_domain
from site_automator.ssh import resolve_ssh_host
from site_automator.utils import configure_logging

configure_logging()


def main() -> None:
    """Set up DNS nameservers and records."""
    load_dotenv()

    # Get domain from environment
    domain = os.getenv("SITE_DOMAIN")
    if not domain:
        print("ERROR: SITE_DOMAIN environment variable is required")
        sys.exit(1)

    # Load site config to get registrar and server
    site = load_site_config_by_domain(domain)

    registrar = site["registrar"]
    server = site["server"]

    # Resolve SSH host to get server IP
    server_ip, _, _ = resolve_ssh_host(server)

    logging.info(
        f"Setting up DNS for {domain} (registrar: {registrar}, server: {server}, IP: {server_ip})"
    )

    # Update nameservers at registrar
    registrars = RegistrarNameserverManager.from_env()

    if registrar == "namecheap":
        registrars.update_nameservers_namecheap(domain)
    elif registrar == "godaddy":
        registrars.update_nameservers_godaddy(domain)
    else:
        print(f"ERROR: Unknown registrar '{registrar}'")
        sys.exit(1)

    # Configure DNS records at DigitalOcean
    dns = DigitalOceanDNSManager.from_env()
    dns.ensure_basic_dns_digitalocean(domain, server_ip)

    print(f"\nSUCCESS: DNS configured for {domain}")
    print(f"Nameservers updated at {registrar}")
    print(f"DNS records created at DigitalOcean pointing to {server_ip}")


if __name__ == "__main__":
    start_time = time.perf_counter()
    main()
    end_time = time.perf_counter()
    elapsed_time = end_time - start_time
    print(f"Total time elapsed: {elapsed_time:.2f} seconds")
