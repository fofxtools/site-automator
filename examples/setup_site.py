#!/usr/bin/env python3
"""Test setup script for a site.

This script sets up a complete test site with generated content.

Usage:
    python3 examples/setup_site.py --site-id example_com

With optional flags (caution: irreversible delete):
    python3 examples/setup_site.py --site-id example_com --wipe --delete-local-content

To reverse/cleanup:
    1. Set wipe=True and delete_local_content=True flags, then run this script again
    2. Or manually: wo site delete <domain> && rm -rf storage/content/<site_id>/
"""

import argparse
import logging
import sys
from pathlib import Path
from time import perf_counter
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from site_automator.utils import configure_logging
from site_automator.sites import load_site_config
from site_automator.workflows import setup_site

# Configure logging
configure_logging()

logger = logging.getLogger(__name__)


def main() -> None:
    """Setup test site from --site-id CLI argument."""
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Setup a test site with generated content"
    )
    parser.add_argument("--site-id", required=True, help="Site ID from sites.csv")
    parser.add_argument(
        "--wipe", action="store_true", help="Wipe and reinstall WordPress"
    )
    parser.add_argument(
        "--delete-local-content",
        action="store_true",
        help="Delete local content folder",
    )

    args = parser.parse_args()

    site = load_site_config(args.site_id)

    logger.info(f"Setting up site: {args.site_id} ({site['domain']})")

    setup_site(
        args.site_id,
        wipe=args.wipe,
        delete_local_content=args.delete_local_content,
    )


if __name__ == "__main__":
    start_time = perf_counter()
    main()
    end_time = perf_counter()
    elapsed_time = end_time - start_time
    print(f"Total time elapsed: {elapsed_time:.2f} seconds")
