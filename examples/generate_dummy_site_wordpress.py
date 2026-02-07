#!/usr/bin/env python3
"""Generate a dummy WordPress site with fake data using Faker.

Usage:
    python examples/generate_dummy_site.py --site-id example_com
"""

import argparse
import logging
import os

from dotenv import load_dotenv
from time import perf_counter
from faker import Faker
import requests

from site_automator.sites import load_site_config
from site_automator.utils import configure_logging
from site_automator.wordops import WordOpsProvisioner
from site_automator.wordpress import WordPressDeployer


def install_with_fake_data(wordpress: WordPressDeployer, domain: str) -> dict[str, str]:
    """Install WordPress with fake metadata.

    Returns:
        Dictionary with credentials (title, username, password, email)
    """
    logging.info(f"Installing WordPress with dummy title for {domain}")
    import shlex

    fake = Faker()
    site_title = fake.catch_phrase()
    admin_user = "admin"
    admin_password = fake.password(length=16, special_chars=False)
    admin_email = fake.email()

    wordpress.wp(
        domain,
        f"core install "
        f"--url={shlex.quote(domain)} "
        f"--title={shlex.quote(site_title)} "
        f"--admin_user={shlex.quote(admin_user)} "
        f"--admin_password={shlex.quote(admin_password)} "
        f"--admin_email={shlex.quote(admin_email)}",
    )

    return {
        "title": site_title,
        "username": admin_user,
        "password": admin_password,
        "email": admin_email,
    }


def create_fake_taxonomy(
    wordpress: WordPressDeployer, domain: str
) -> dict[str, list[int]]:
    """Create fake categories and tags.

    Returns:
        Dictionary with 'categories' and 'tags' lists of IDs
    """
    logging.info(f"Creating fake taxonomy for {domain}")
    import shlex

    fake = Faker()

    # Create 5 categories
    category_ids = []
    for _ in range(5):
        name = fake.word().capitalize()
        output, _ = wordpress.wp(
            domain, f"term create category {shlex.quote(name)} --porcelain"
        )
        category_ids.append(int(output.strip()))

    # Create 10 tags
    tag_ids = []
    for _ in range(10):
        name = fake.word()
        output, _ = wordpress.wp(
            domain, f"term create post_tag {shlex.quote(name)} --porcelain"
        )
        tag_ids.append(int(output.strip()))

    return {"categories": category_ids, "tags": tag_ids}


def download_picsum_images(
    wordops: WordOpsProvisioner, shared_dir: str = "/shared", count: int = 9
) -> list[str]:
    """Download picsum images directly on remote server if they don't exist.

    Args:
        wordops: WordOpsProvisioner instance
        shared_dir: Directory to store images on remote server (default: /shared)
        count: Number of images to download (default: 9)

    Returns:
        List of remote image paths
    """
    logging.info(f"Checking for picsum images in {shared_dir}")

    # Create shared directory if it doesn't exist, set permissions, and set ownership to www-data
    wordops.ssh.run_command(
        f"mkdir -p {shared_dir} && chmod 755 {shared_dir} && chown -R www-data:www-data {shared_dir}",
        check=True,
    )

    image_paths = []
    for i in range(1, count + 1):
        image_path = os.path.join(shared_dir, f"picsum_800_600_{i}.jpg")
        image_paths.append(image_path)

        # Check if image already exists on remote server
        _, returncode = wordops.ssh.run_command(f"test -f {image_path}", check=False)
        if returncode == 0:
            logging.info(f"Image already exists on server: {image_path}")
            continue

        # Download random image from picsum.photos directly on remote server
        url = "https://picsum.photos/800/600"
        logging.info(f"Downloading random image to remote server: {image_path}")

        try:
            wordops.ssh.run_command(f"curl -L -o {image_path} {url}", check=True)
            logging.info(f"Successfully downloaded: {image_path}")
        except Exception as e:
            logging.error(f"Failed to download image from {url}: {e}")
            raise

    return image_paths


def populate_fake_posts_and_pages(
    wordpress: WordPressDeployer, domain: str, taxonomy: dict[str, list[int]]
) -> None:
    """Create fake posts and pages with featured images."""
    import random
    import shlex

    fake = Faker()

    # Featured images available
    images = [
        "/shared/picsum_800_600_1.jpg",
        "/shared/picsum_800_600_2.jpg",
        "/shared/picsum_800_600_3.jpg",
        "/shared/picsum_800_600_4.jpg",
        "/shared/picsum_800_600_5.jpg",
        "/shared/picsum_800_600_6.jpg",
        "/shared/picsum_800_600_7.jpg",
        "/shared/picsum_800_600_8.jpg",
        "/shared/picsum_800_600_9.jpg",
    ]

    # Create posts
    logging.info(f"Creating fake posts for {domain}")
    for i in range(20):
        title = fake.sentence(nb_words=6).rstrip(".")
        content = "\n\n".join(fake.paragraphs(nb=3))

        # Random date in the past year
        date = fake.date_time_between(start_date="-1y", end_date="now")
        date_str = date.strftime("%Y-%m-%d %H:%M:%S")

        # Random categories and tags
        post_categories = random.sample(taxonomy["categories"], k=random.randint(1, 3))
        post_tags = random.sample(taxonomy["tags"], k=random.randint(2, 5))

        categories_str = ",".join(map(str, post_categories))
        tags_str = ",".join(map(str, post_tags))

        # Create post
        post_id = wordpress.create_post(
            domain,
            title=title,
            content=content,
            status="publish",
            date=date_str,
            additional_flags=[
                f"--post_category={categories_str}",
                f"--tags_input={tags_str}",
            ],
        )

        # Add featured image
        image_path = random.choice(images)
        attachment_id = wordpress.ensure_attachment(domain, image_path)
        wordpress.set_featured_image(domain, post_id, attachment_id)

    # Create pages
    logging.info(f"Creating fake pages for {domain}")
    for i in range(5):
        title = fake.sentence(nb_words=4).rstrip(".")
        content = "\n\n".join(fake.paragraphs(nb=2))

        # Create page
        output, _ = wordpress.wp(
            domain,
            f"post create "
            f"--post_type=page "
            f"--post_title={shlex.quote(title)} "
            f"--post_content={shlex.quote(content)} "
            f"--post_status=publish "
            f"--porcelain",
        )
        page_id = int(output.strip())

        # Add featured image
        image_path = random.choice(images)
        attachment_id = wordpress.ensure_attachment(domain, image_path)
        wordpress.set_featured_image(domain, page_id, attachment_id)


def setup_plugins(wordpress: WordPressDeployer, domain: str) -> None:
    """Install and activate plugins."""
    logging.info(f"Installing and activating plugins for {domain}")
    plugin_slugs = [
        "nginx-helper",
        "seo-by-rank-math",
        "yet-another-related-posts-plugin",
    ]
    wordpress.install_plugins(domain, plugin_slugs, activate=True)

    # Visit /wp-admin to trigger Related Posts section from plugin (no need to login)
    requests.get(f"https://{domain}/wp-admin")


def main() -> None:
    """Generate dummy WordPress site."""
    load_dotenv()
    configure_logging()

    parser = argparse.ArgumentParser(
        description="Generate a dummy WordPress site with fake data"
    )
    parser.add_argument("--site-id", required=True, help="Site ID from sites.csv")
    args = parser.parse_args()

    site = load_site_config(args.site_id)
    domain = site["domain"]
    server = site["server"]

    wordops = WordOpsProvisioner(host=server)
    wordpress = WordPressDeployer(wordops)

    try:
        # Create site if it doesn't exist
        if not wordpress.site_exists(domain):
            wordops.create_site(domain, flags=["--wpfc"])
            wordops.ensure_ssl(domain)
            wordops.restart_nginx()

        wordpress.wipe_site(domain, confirm=True)
        wordpress.wp(domain, "core download")
        credentials = install_with_fake_data(wordpress, domain)

        # Deploy and configure WordPress
        fake = Faker()
        wordpress.initial_setup(
            domain,
            site_title=credentials["title"],
            site_description=fake.catch_phrase(),
            theme="generatepress",
            seo_plugin="seo-by-rank-math",
            internal_linking_plugin="yet-another-related-posts-plugin",
        )

        taxonomy = create_fake_taxonomy(wordpress, domain)
        download_picsum_images(wordops)
        populate_fake_posts_and_pages(wordpress, domain, taxonomy)
        # Must activate related posts plugins only after populating posts to avoid empty wp_yarpp_related_cache table error
        setup_plugins(wordpress, domain)

        # Print credentials
        print("\n" + "=" * 60)
        print("SUCCESS: Dummy site created.")
        print("=" * 60)
        print(f"URL:      https://{domain}")
        print(f"Title:    {credentials['title']}")
        print(f"Username: {credentials['username']}")
        print(f"Password: {credentials['password']}")
        print(f"Email:    {credentials['email']}")
        print("=" * 60 + "\n")

    finally:
        wordops.close()


if __name__ == "__main__":
    start_time = perf_counter()
    main()
    end_time = perf_counter()
    elapsed_time = end_time - start_time
    print(f"Total time elapsed: {elapsed_time:.2f} seconds")
