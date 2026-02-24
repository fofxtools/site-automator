#!/usr/bin/env python3
"""Setup pageview tracking for sites.

This script deploys the pageview tracking system to WordPress or Hugo sites.

Usage:
    # Setup tracking for a single site
    python examples/setup_tracking.py --site-id <site_id>

    # Setup tracking for all sites on a server
    python examples/setup_tracking.py --server <server>

    # Setup tracking for all sites
    python examples/setup_tracking.py --all

What it does:
    - Uploads tracking plugin files
    - Creates .env file with TRACKING_ENABLED=true
    - Installs and activates plugin (WordPress) or deploys to static/ (Hugo)
    - Creates /var/lib/pageview-tracking directory structure
    - Uploads Python processing scripts
    - Sets up cron job to process logs hourly
"""

import argparse
import logging
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from site_automator.utils import configure_logging
from site_automator.sites import load_site_config, load_all_sites
from site_automator.wordops import WordOpsProvisioner
from site_automator.caddy import CaddyProvisioner
from site_automator.tracking import PageviewTrackingSetup

# Configure logging
configure_logging()
logger = logging.getLogger(__name__)


def setup_tracking_for_site(site_id: str) -> None:
    """Setup tracking for a single site.

    Args:
        site_id: Site ID from sites.csv
    """
    site = load_site_config(site_id)
    domain = site["domain"]
    server = site["server"]
    cms = site.get("cms", "wordpress")

    logger.info(f"Setting up tracking for {site_id} ({domain}) on {server}")

    if cms == "wordpress":
        wordops = WordOpsProvisioner(host=server)
        try:
            tracking = PageviewTrackingSetup(wordops.ssh)
            tracking.setup_tracking_wordpress(domain)
            logger.info(f"Tracking setup complete for {domain}")
        finally:
            wordops.close()

    elif cms == "hugo":
        caddy = CaddyProvisioner(host=server)
        try:
            tracking = PageviewTrackingSetup(caddy.ssh)
            tracking.setup_tracking_hugo(domain)
            logger.info(f"Tracking setup complete for {domain}")
            logger.info("Next steps:")
            logger.info(
                "  - Ensure Caddy is configured to handle PHP files via php-fpm"
            )
            logger.info("  - Tracking script should already be in baseof.html")
        finally:
            caddy.ssh.close()

    else:
        logger.error(f"Unsupported CMS: {cms}")
        sys.exit(1)


def setup_tracking_for_server(server: str) -> None:
    """Setup tracking for all sites on a server.

    Args:
        server: Server name from sites.csv
    """
    sites = load_all_sites()
    server_sites = [s for s in sites if s["server"] == server]

    if not server_sites:
        logger.error(f"No sites found for server: {server}")
        sys.exit(1)

    logger.info(f"Found {len(server_sites)} sites on {server}")

    for site in server_sites:
        setup_tracking_for_site(site["site_id"])


def setup_tracking_for_all() -> None:
    """Setup tracking for all sites in sites.csv."""
    sites = load_all_sites()

    logger.info(f"Setting up tracking for {len(sites)} sites")

    for site in sites:
        setup_tracking_for_site(site["site_id"])


def main() -> None:
    """Main entry point."""
    load_dotenv()

    parser = argparse.ArgumentParser(description="Setup pageview tracking for sites")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--site-id", help="Site ID from sites.csv")
    group.add_argument("--server", help="Server name (setup all sites on this server)")
    group.add_argument(
        "--all", action="store_true", help="Setup tracking for all sites"
    )

    args = parser.parse_args()

    if args.site_id:
        setup_tracking_for_site(args.site_id)
    elif args.server:
        setup_tracking_for_server(args.server)
    elif args.all:
        setup_tracking_for_all()

    # Print web viewer deployment instructions
    logger.info("\n" + "=" * 80)
    logger.info("Tracking backend deployed successfully")
    logger.info("To view stats in the web interface, deploy the web viewer files.")
    logger.info("For WordPress sites:")
    logger.info(
        "\n\n  rsync -avz pageview-tracking/php/{index.php,day.php,views.php} {server-alias}:/var/www/{domain}/htdocs/stats/\n"
    )
    logger.info("For Hugo sites:")
    logger.info(
        "\n\n  rsync -avz pageview-tracking/php/{index.php,day.php,views.php} {server-alias}:/var/www/{domain}/public/stats/\n"
    )
    logger.info("Replace {server-alias} and {domain} with actual values.")
    logger.info("Then visit: https://{domain}/stats/")
    logger.info(
        "Note: You only need to do this once per server (web viewer reads all domains)."
    )
    logger.info("=" * 80 + "\n")
    logger.info(
        "Then to regenerate statistics, run process_daily_logs.py with --force flag on each server:"
    )
    logger.info(
        "\n\n  ssh {server-alias} 'cd /var/lib/pageview-tracking/scripts && python3 process_daily_logs.py --force'\n"
    )


if __name__ == "__main__":
    main()
