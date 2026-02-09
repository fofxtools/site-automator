#!/usr/bin/env python3
"""Test setup script for a Hugo site.

This script sets up a complete Hugo test site with generated content.

Usage:
    python examples/setup_site_hugo.py --site-id example_com

With optional flags (caution: irreversible delete):
    python examples/setup_site_hugo.py --site-id example_com --wipe --delete-local-content

To reverse/cleanup:
    1. Set wipe=True and delete_local_content=True flags, then run this script again
    2. Or manually on server: rm -f /etc/caddy/sites-enabled/<domain>.caddy && caddy reload && rm -rf /var/www/<domain>
    3. And locally: rm -rf storage/content/<site_id>/
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
from site_automator.workflows import setup_site_hugo

# Configure logging
configure_logging()

logger = logging.getLogger(__name__)


def main() -> None:
    """Setup test site from --site-id CLI argument."""
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Setup a Hugo test site with generated content"
    )
    parser.add_argument("--site-id", required=True, help="Site ID from sites.csv")
    parser.add_argument(
        "--wipe", action="store_true", help="Wipe Hugo site files (preserving stats)"
    )
    parser.add_argument(
        "--delete-local-content",
        action="store_true",
        help="Delete local content folder",
    )

    args = parser.parse_args()

    site = load_site_config(args.site_id)

    logger.info(f"Setting up Hugo site: {args.site_id} ({site['domain']})")

    setup_site_hugo(
        args.site_id,
        wipe=args.wipe,
        delete_local_content=args.delete_local_content,
    )

    logger.info(
        f"\nTo automate daily content publishing, add the following to your crontab (replace paths):\n\n"
        f"PROJECT_PATH=/path/to/site-automator\n"
        f"VENV_PYTHON=/path/to/site-automator/.venv/bin/python\n\n"
        f"# {args.site_id}\n"
        f'0 0 * * * flock -n /tmp/{args.site_id}_hugo.lock -c "cd $PROJECT_PATH && $VENV_PYTHON scripts/publish_daily_hugo.py --site-id {args.site_id}"\n'
    )


if __name__ == "__main__":
    start_time = perf_counter()
    main()
    end_time = perf_counter()
    elapsed_time = end_time - start_time
    print(f"Total time elapsed: {elapsed_time:.2f} seconds")
