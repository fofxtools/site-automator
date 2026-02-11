#!/usr/bin/env python3
"""Submit homepage URL to IndexNow for indexing.

This script creates an IndexNow key file and submits the homepage URL
to IndexNow via Zyte API for better deliverability.

Usage:
    python examples/indexnow.py --site-id example_com
"""

import argparse
import logging
from time import perf_counter

from dotenv import load_dotenv

from site_automator.seo import create_indexnow_key, submit_indexnow
from site_automator.sites import load_site_config
from site_automator.utils import configure_logging
from site_automator.wordops import WordOpsProvisioner

configure_logging()

logger = logging.getLogger(__name__)


def main() -> None:
    """Submit homepage to IndexNow."""
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Submit homepage URL to IndexNow for indexing"
    )
    parser.add_argument("--site-id", required=True, help="Site ID from sites.csv")
    args = parser.parse_args()

    site = load_site_config(args.site_id)
    domain = site["domain"]
    server = site["server"]
    cms = site["cms"]

    # Determine webroot based on CMS
    webroot = "public" if cms == "hugo" else "htdocs"

    wordops = WordOpsProvisioner(host=server)
    try:
        # Create IndexNow key file
        key = create_indexnow_key(domain, wordops.ssh, webroot=webroot)

        # Submit homepage URL
        homepage_url = f"https://{domain}/"
        submit_indexnow(homepage_url, key, use_zyte=True)
    finally:
        wordops.close()


if __name__ == "__main__":
    start_time = perf_counter()
    main()
    elapsed = perf_counter() - start_time
    print(f"Completed in {elapsed:.2f} seconds")
