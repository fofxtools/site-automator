"""Publisher - Publish articles to WordPress sites."""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import markdown

from dotenv import load_dotenv

from site_automator.sites import load_site_config
from site_automator.wordpress import WordPressDeployer

logger = logging.getLogger(__name__)

load_dotenv()

WP_PUBLISH_STATUS_DEFAULT = "draft"


def _articles_published_path(site_id: str, slug: str) -> Path:
    """Get path to article published metadata file."""
    content_root = Path(os.getenv("SITES_CONTENT_PATH", "storage/content"))
    return content_root / site_id / "articles" / "published" / f"{slug}.json"


def _articles_markdown_path(site_id: str, slug: str) -> Path:
    """Get path to article markdown file."""
    content_root = Path(os.getenv("SITES_CONTENT_PATH", "storage/content"))
    return content_root / site_id / "articles" / "markdown" / f"{slug}.md"


def create_articles_wordpress(
    site_id: str, wordpress: WordPressDeployer, limit: int | None = None
) -> None:
    """
    Create articles on WordPress from generation files.

    Args:
        site_id: Site identifier
        wordpress: WordPressDeployer instance
        limit: Maximum number of articles to create (None for unlimited)

    Behavior:
    - Reads all .json files in SITES_CONTENT_PATH/{site_id}/articles/generation folder
    - For each file up to limit:
      - Gets title from generation/{slug}.json
      - Checks if already published in published/{slug}.json
      - Gets content from markdown/{slug}.md
      - Creates post with WP_PUBLISH_STATUS_DEFAULT status
      - Writes published/{slug}.json with post_id and status
    """
    site = load_site_config(site_id)
    domain = site["domain"]

    content_root = Path(os.getenv("SITES_CONTENT_PATH", "storage/content"))
    generation_dir = content_root / site_id / "articles" / "generation"
    published_dir = content_root / site_id / "articles" / "published"

    if not generation_dir.exists():
        logger.warning(f"Generation directory not found: {generation_dir}")
        return

    # Create published directory if it doesn't exist
    published_dir.mkdir(parents=True, exist_ok=True)

    # Get all generation files
    generation_files = list(generation_dir.glob("*.json"))

    if not generation_files:
        logger.info(f"No generation files found for {site_id}")
        return

    # Sort by file modification time (oldest first)
    generation_files.sort(key=lambda f: f.stat().st_mtime)

    # Apply limit
    max_create = limit if limit is not None else len(generation_files)

    created = 0
    skipped = 0

    logger.info(
        f"Starting article creation for {site_id}: {len(generation_files)} files"
    )

    for gen_file in generation_files:
        if created >= max_create:
            logger.info(f"Reached creation limit ({max_create}), stopping")
            break

        slug = gen_file.stem

        # Check if already published
        published_path = _articles_published_path(site_id, slug)
        if published_path.exists():
            skipped += 1
            logger.debug(f"Skipping {slug}: already published")
            continue

        # Load generation metadata
        with gen_file.open("r", encoding="utf-8") as f:
            gen_data = json.load(f)

        title = gen_data.get("title")
        if not title:
            raise ValueError(f"Missing title in {gen_file}")

        # Load markdown content
        markdown_path = _articles_markdown_path(site_id, slug)
        if not markdown_path.exists():
            raise FileNotFoundError(f"Markdown file not found: {markdown_path}")

        with markdown_path.open("r", encoding="utf-8") as f:
            markdown_content = f.read()

        # Convert markdown to HTML
        html_content = markdown.markdown(markdown_content)

        # Create post
        logger.info(f"Creating post for '{title}' ({slug})")
        post_id = wordpress.create_post(
            domain,
            title=title,
            content=html_content,
            status=WP_PUBLISH_STATUS_DEFAULT,
            slug=slug,
        )

        # Write published metadata
        published_data = {
            "slug": slug,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "cms": "wordpress",
            "post_id": post_id,
            "status": WP_PUBLISH_STATUS_DEFAULT,
        }
        with published_path.open("w", encoding="utf-8") as f:
            json.dump(published_data, f, indent=2, ensure_ascii=False)

        created += 1
        logger.info(f"Post created: {slug} (ID: {post_id}, {created}/{max_create})")

    logger.info(
        f"Article creation complete for {site_id}: "
        f"{created} created, {skipped} skipped, {len(generation_files)} total"
    )


def activate_articles_wordpress(
    site_id: str, wordpress: WordPressDeployer, limit: int | None = None
) -> None:
    """
    Activate published articles on WordPress by changing status to 'publish'.

    Args:
        site_id: Site identifier
        wordpress: WordPressDeployer instance
        limit: Maximum number of articles to activate (None for unlimited)

    Behavior:
    - Reads all .json files in SITES_CONTENT_PATH/{site_id}/articles/published folder
    - For each file up to limit:
      - Gets post_id and status from published/{slug}.json
      - Changes post_id status to 'publish' using WordPressDeployer
      - Updates published/{slug}.json status field to 'publish'
      - Records activated_at timestamp
    """
    site = load_site_config(site_id)
    domain = site["domain"]

    content_root = Path(os.getenv("SITES_CONTENT_PATH", "storage/content"))
    published_dir = content_root / site_id / "articles" / "published"

    if not published_dir.exists():
        logger.warning(f"Published directory not found: {published_dir}")
        return

    # Get all published files
    published_files = list(published_dir.glob("*.json"))

    if not published_files:
        logger.info(f"No published files found for {site_id}")
        return

    # Sort by file modification time (oldest first)
    published_files.sort(key=lambda f: f.stat().st_mtime)

    # Apply limit
    max_activate = limit if limit is not None else len(published_files)

    activated = 0
    skipped = 0

    logger.info(
        f"Starting article activation for {site_id}: {len(published_files)} files"
    )

    for pub_file in published_files:
        if activated >= max_activate:
            logger.info(f"Reached activation limit ({max_activate}), stopping")
            break

        slug = pub_file.stem

        # Load published metadata
        with pub_file.open("r", encoding="utf-8") as f:
            pub_data = json.load(f)

        post_id = pub_data.get("post_id")
        status = pub_data.get("status")

        if post_id is None:
            raise ValueError(f"Missing post_id in {pub_file}")
        if status is None:
            raise ValueError(f"Missing status in {pub_file}")

        # Skip if already published
        if status == "publish":
            skipped += 1
            logger.debug(f"Skipping {slug}: already activated")
            continue

        # Update post status to publish
        logger.info(f"Activating post '{slug}' (ID: {post_id})")
        wordpress.wp(domain, f"post update {post_id} --post_status=publish", check=True)

        # Update published metadata
        pub_data["status"] = "publish"
        pub_data["activated_at"] = datetime.now(timezone.utc).isoformat()

        with pub_file.open("w", encoding="utf-8") as f:
            json.dump(pub_data, f, indent=2, ensure_ascii=False)

        activated += 1
        logger.info(
            f"Post activated: {slug} (ID: {post_id}, {activated}/{max_activate})"
        )

    logger.info(
        f"Article activation complete for {site_id}: "
        f"{activated} activated, {skipped} skipped, {len(published_files)} total"
    )
