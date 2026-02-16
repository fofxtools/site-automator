"""Site setup workflows."""

import logging
import os
import shutil
from pathlib import Path

from site_automator.articles import generate_articles_llm
from site_automator.caddy import CaddyProvisioner
from site_automator.hugo import HugoDeployer
from site_automator.sites import load_site_config
from site_automator.topics import generate_topics_site_id
from site_automator.wordops import WordOpsProvisioner
from site_automator.wordpress import WordPressDeployer

logger = logging.getLogger(__name__)


def setup_site_wordpress(
    site_id: str,
    *,
    wipe: bool = False,
    delete_local_content: bool = False,
) -> None:
    """Setup a WordPress site with generated content.

    Args:
        site_id: Site identifier
        wipe: If True, wipe and reinstall WordPress
        delete_local_content: If True, delete local published content folder
    """
    site = load_site_config(site_id)
    domain = site["domain"]
    server = site["server"]

    logger.info(f"Setting up site: {site_id} ({domain})")

    wordops = WordOpsProvisioner(host=server)
    try:
        wordpress = WordPressDeployer(wordops)

        # Create site if it doesn't exist
        if not wordpress.site_exists(domain):
            wordops.create_site(domain, flags=["--wpfc"])
            try:
                _ = wordops.ensure_ssl(domain)
            except Exception as e:
                logger.warning(f"SSL setup failed: {e}. Continuing without SSL.")

        if wipe:
            logger.info("Wiping and installing WordPress")
            wordpress.wipe_and_install(
                domain,
                site["site_title"],
                exclude_dirs=["stats"],
                confirm=True,
            )

        if delete_local_content:
            content_root = Path(os.getenv("SITES_CONTENT_PATH", "storage/content"))
            site_dir = content_root / site_id
            if site_dir.exists():
                logger.info(f"Deleting site folder: {site_dir}")
                shutil.rmtree(site_dir)

        logger.info("Generating topics")
        generate_topics_site_id(site_id)

        logger.info("Generating articles")
        generate_articles_llm(site_id)

        logger.info("Deploying and configuring WordPress")
        wordpress.initial_setup(
            domain,
            site["site_title"],
            site["site_description"],
            site["theme"],
            site["seo_plugin"],
            site["internal_linking_mode"],
        )

        logger.info(f"Site setup complete: {site_id}")

    finally:
        wordops.close()


def setup_site_hugo(
    site_id: str,
    *,
    wipe: bool = False,
    delete_local_content: bool = False,
) -> None:
    """Setup a Hugo site with generated content.

    Args:
        site_id: Site identifier
        wipe: If True, wipe Hugo site files (preserving stats)
        delete_local_content: If True, delete local content folder
    """
    site = load_site_config(site_id)
    domain = site["domain"]
    server = site["server"]

    logger.info(f"Setting up Hugo site: {site_id} ({domain})")

    caddy = CaddyProvisioner(host=server)
    try:
        # Flush DNS cache to prevent stale records from blocking SSL
        caddy.ssh.run_command("resolvectl flush-caches", check=False)

        # Provision domain with Caddy
        caddy.enable_domain(domain)

        hugo = HugoDeployer(caddy.ssh)

        # Check Hugo is installed
        hugo.check_hugo_installed()

        if wipe:
            logger.info("Wiping Hugo site files")
            hugo.wipe_site(domain, confirm=True, exclude_dirs=["public/stats"])

        if delete_local_content:
            content_root = Path(os.getenv("SITES_CONTENT_PATH", "storage/content"))
            site_dir = content_root / site_id
            if site_dir.exists():
                logger.info(f"Deleting site folder: {site_dir}")
                shutil.rmtree(site_dir)

        logger.info("Generating topics")
        generate_topics_site_id(site_id)

        logger.info("Generating articles")
        generate_articles_llm(site_id, add_hugo_frontmatter=True)

        logger.info("Configuring Hugo site")
        hugo.initial_setup(domain)

        logger.info(f"Site setup complete: {site_id}")

    finally:
        caddy.close()
