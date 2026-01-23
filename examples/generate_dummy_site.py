#!/usr/bin/env python3
"""Generate a dummy WordPress site with fake data using Faker."""

import logging
import os
import sys

from dotenv import load_dotenv
from time import perf_counter
from faker import Faker
import requests

from site_automator.tracking import PageviewTrackingSetup
from site_automator.wordops import WordOpsProvisioner
from site_automator.wordpress import WordPressDeployer

# Configure logging
console_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=console_level, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)

# File logging (if configured)
log_file = os.getenv("LOG_FILE")
if log_file:
    log_file_level = os.getenv("LOG_FILE_LEVEL", "ERROR").upper()
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(log_file_level)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
    )
    logging.getLogger().addHandler(file_handler)

# Silence paramiko's noisy INFO logs
logging.getLogger("paramiko").setLevel(logging.WARNING)


def reset_wordpress(
    wordpress: WordPressDeployer, wordops: WordOpsProvisioner, domain: str
) -> None:
    """Reset WordPress installation (wipe database and files)."""
    logging.info(f"Resetting WordPress installation for {domain}")
    wordpress.wp(domain, "db reset --yes")
    wordops.run_command(f"rm -rf /var/www/{domain}/htdocs/*", check=True)
    wordpress.wp(domain, "core download")


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


def deploy_and_configure(
    wordpress: WordPressDeployer,
    wordops: WordOpsProvisioner,
    domain: str,
    credentials: dict[str, str],
) -> None:
    """Deploy and configure WordPress site."""
    logging.info(f"Deploying and configuring WordPress for {domain}")
    fake = Faker()

    wordpress.delete_demo_content(domain)

    wordpress.configure_site(
        domain,
        title=credentials["title"],
        description=fake.catch_phrase(),
    )

    wordpress.sync_admin_password_to_db(domain)
    wordpress.disable_comments_with_plugin(domain)
    wordpress.delete_widgets(domain, ["block-4"])
    wordpress.install_theme(domain, "/shared/astra.zip", activate=False)
    wordpress.install_theme(domain, "/shared/kadence.zip", activate=False)
    wordpress.install_theme(domain, "/shared/generatepress.zip", activate=True)
    wordpress.delete_themes(domain, ["twentytwentythree", "twentytwentyfour"])

    tracking = PageviewTrackingSetup(wordops)
    tracking.setup_tracking(domain)


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
    plugin_paths = [
        "/shared/seo-by-rank-math.1.0.262.zip",
        "/shared/yet-another-related-posts-plugin.5.30.11.zip",
    ]
    wordpress.install_plugins(domain, plugin_paths, activate=True)

    # Visited /wp-admin to trigger Related Posts section from plugin (no need to login)
    requests.get(f"https://{domain}/wp-admin")


def main() -> None:
    """Generate dummy WordPress site."""
    load_dotenv()

    domain = os.getenv("SITE_DOMAIN")
    if not domain:
        print("ERROR: SITE_DOMAIN environment variable is required")
        sys.exit(1)

    wordops = WordOpsProvisioner.from_env()
    wordpress = WordPressDeployer(wordops)

    try:
        reset_wordpress(wordpress, wordops, domain)
        credentials = install_with_fake_data(wordpress, domain)
        deploy_and_configure(wordpress, wordops, domain, credentials)
        taxonomy = create_fake_taxonomy(wordpress, domain)
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
