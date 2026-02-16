#!/usr/bin/env python3
"""Generate a dummy Hugo site with fake data using Faker.

Usage:
    python examples/generate_dummy_site_hugo.py --site-id example_com
"""

import argparse
import logging
import os
import random
import shutil
from pathlib import Path
from time import perf_counter

from dotenv import load_dotenv
from faker import Faker

from site_automator.sites import load_site_config
from site_automator.ssh import SSHConnection
from site_automator.caddy import CaddyProvisioner
from site_automator.hugo import HugoDeployer
from site_automator.utils import configure_logging


def download_picsum_images(
    ssh: SSHConnection, shared_dir: str | None = None, count: int = 9
) -> list[str]:
    """Download picsum images directly on remote server if they don't exist.

    Args:
        ssh: SSHConnection instance
        shared_dir: Directory to store images on remote server (default: from SHARED_IMAGES_PATH env var)
        count: Number of images to download (default: 9)

    Returns:
        List of remote image paths
    """
    if shared_dir is None:
        shared_dir = os.getenv("SHARED_IMAGES_PATH", "/var/www/shared/images")

    logging.info(f"Checking for picsum images in {shared_dir}")

    # Create shared directory if it doesn't exist and set permissions
    ssh.run_command(
        f"mkdir -p {shared_dir} && chmod 755 {shared_dir}",
        check=True,
    )

    image_paths = []
    for i in range(1, count + 1):
        image_filename = f"picsum_800_600_{i}.jpg"
        image_path = os.path.join(shared_dir, image_filename)
        image_paths.append(image_filename)

        # Check if image already exists on remote server
        _, returncode = ssh.run_command(f"test -f {image_path}", check=False)
        if returncode == 0:
            logging.info(f"Image already exists on server: {image_path}")
            continue

        # Download random image from picsum.photos directly on remote server
        url = "https://picsum.photos/800/600"
        logging.info(f"Downloading random image to remote server: {image_path}")

        try:
            ssh.run_command(f"curl -L -o {image_path} {url}", check=True)
            logging.info(f"Successfully downloaded: {image_path}")
        except Exception as e:
            logging.error(f"Failed to download image from {url}: {e}")
            raise

    return image_paths


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


def populate_fake_content(
    hugo: HugoDeployer,
    domain: str,
    site_id: str,
    theme: str,
    available_images: list[str],
    count: int = 20,
) -> None:
    """Generate and deploy fake articles with featured images.

    Args:
        hugo: HugoDeployer instance
        domain: Domain name for the Hugo site
        site_id: Site identifier (from sites.csv)
        theme: Theme name for the Hugo site
        available_images: List of available image filenames
        count: Number of articles to generate (default: 20)
    """
    logging.info(f"Generating {count} fake articles for {domain}")
    fake = Faker()

    # Set up temp directory structure to match expected SITES_CONTENT_PATH layout
    # Expected: {SITES_CONTENT_PATH}/{site_id}/articles/markdown/{slug}.md
    temp_content_root = Path("/tmp/hugo_site_content")
    if temp_content_root.exists():
        shutil.rmtree(temp_content_root)

    markdown_dir = temp_content_root / site_id / "articles" / "markdown"
    markdown_dir.mkdir(parents=True)

    # Override SITES_CONTENT_PATH for set_featured_image_local
    os.environ["SITES_CONTENT_PATH"] = str(temp_content_root)

    # Generate all markdown files and set featured images
    for _ in range(count):
        slug = fake.slug()
        generate_markdown_file(fake, markdown_dir, slug)

        # Pick random image and symlink it
        image_filename = random.choice(available_images)
        hugo.symlink_shared_image(domain, image_filename)

        # Set featured image in local markdown frontmatter
        image_url = f"/images/{image_filename}"
        hugo.set_featured_image_local(site_id, slug, theme, image_url)

    # Deploy entire directory with one rsync
    hugo.deploy_content_directory(domain, markdown_dir)

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
    theme = site.get("theme", "ananke")

    caddy = CaddyProvisioner(host=server)
    hugo = HugoDeployer(caddy.ssh)

    try:
        caddy.enable_domain(domain)

        # Wipe and initialize Hugo site
        hugo.check_hugo_installed()
        hugo.wipe_site(domain, confirm=True, exclude_dirs=["public/stats"])
        hugo.initial_setup(domain)

        # Download picsum images to shared directory
        available_images = download_picsum_images(caddy.ssh)

        # Generate and deploy content with featured images
        count = 20
        populate_fake_content(
            hugo, domain, args.site_id, theme, available_images, count
        )

        # Build site (robots.txt must exist in /static/ before build)
        hugo.write_robots_txt(domain)
        hugo.build_site(domain)
        hugo.set_permissions(domain)

        # Success message
        print("\n" + "=" * 60)
        print("SUCCESS: Dummy Hugo site created.")
        print("=" * 60)
        print(f"URL: https://{domain}")
        print(f"Articles: {count}")
        print("=" * 60 + "\n")

    finally:
        caddy.close()


if __name__ == "__main__":
    start_time = perf_counter()
    main()
    end_time = perf_counter()
    elapsed_time = end_time - start_time
    print(f"Total time elapsed: {elapsed_time:.2f} seconds")
