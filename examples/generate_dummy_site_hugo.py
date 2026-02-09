#!/usr/bin/env python3
"""Generate a dummy Hugo site with fake data using Faker.

Usage:
    python examples/generate_dummy_site_hugo.py --site-id example_com
"""

import argparse
import logging
from pathlib import Path
from time import perf_counter

from dotenv import load_dotenv
from faker import Faker

from site_automator.sites import load_site_config
from site_automator.ssh import SSHConnection
from site_automator.hugo import HugoDeployer
from site_automator.utils import configure_logging


def generate_markdown_file(fake: Faker, output_dir: Path, slug: str) -> Path:
    """Generate a single markdown file with frontmatter.

    Args:
        fake: Faker instance
        output_dir: Local directory to save markdown files
        slug: URL slug for the article

    Returns:
        Path to the generated markdown file
    """
    title = fake.sentence(nb_words=6).rstrip(".")
    date = fake.date_time_between(start_date="-1y", end_date="now")
    content = "\n\n".join(fake.paragraphs(nb=5))

    # Hugo frontmatter
    frontmatter = f"""---
title: "{title}"
date: {date.strftime("%Y-%m-%dT%H:%M:%S%z")}
draft: false
---

{content}
"""

    file_path = output_dir / f"{slug}.md"
    file_path.write_text(frontmatter)
    logging.info(f"Generated markdown file: {slug}.md")

    return file_path


def populate_fake_content(hugo: HugoDeployer, domain: str, count: int = 20) -> None:
    """Generate and deploy fake articles.

    Args:
        hugo: HugoDeployer instance
        domain: Domain name for the Hugo site
        count: Number of articles to generate (default: 20)
    """
    logging.info(f"Generating {count} fake articles for {domain}")
    fake = Faker()

    # Create local temp directory for markdown files
    temp_dir = Path("/tmp/hugo_content")
    temp_dir.mkdir(exist_ok=True)

    # Generate all markdown files first
    for i in range(count):
        slug = fake.slug()
        generate_markdown_file(fake, temp_dir, slug)

    # Deploy entire directory with one rsync
    hugo.deploy_content_directory(domain, temp_dir)

    logging.info(f"Deployed {count} articles to {domain}")


def main() -> None:
    """Generate dummy Hugo site."""
    load_dotenv()
    configure_logging()

    parser = argparse.ArgumentParser(
        description="Generate a dummy Hugo site with fake data"
    )
    parser.add_argument("--site-id", required=True, help="Site ID from sites.csv")
    args = parser.parse_args()

    site = load_site_config(args.site_id)
    domain = site["domain"]
    server = site["server"]

    ssh = SSHConnection(host=server)
    hugo = HugoDeployer(ssh)

    try:
        # Initialize Hugo site
        hugo.check_hugo_installed()
        hugo.ensure_site_initialized(domain)
        hugo.ensure_base_url(domain)
        hugo.ensure_theme_installed(domain, theme="ananke")

        # Setup internal linking
        hugo.ensure_internal_links_partial(domain)
        hugo.ensure_single_layout_override(domain)

        # Generate and deploy content
        count = 20
        populate_fake_content(hugo, domain, count)

        # Build site (robots.txt must exist in /static/ before build)
        hugo.ensure_robots_txt(domain)
        hugo.build_site(domain)
        hugo.ensure_permissions(domain)

        # Success message
        print("\n" + "=" * 60)
        print("SUCCESS: Dummy Hugo site created.")
        print("=" * 60)
        print(f"URL: https://{domain}")
        print(f"Articles: {count}")
        print("=" * 60 + "\n")

    finally:
        ssh.close()


if __name__ == "__main__":
    start_time = perf_counter()
    main()
    end_time = perf_counter()
    elapsed_time = end_time - start_time
    print(f"Total time elapsed: {elapsed_time:.2f} seconds")
