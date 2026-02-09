"""Publish local articles to WordPress sites."""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import markdown

from dotenv import load_dotenv

from site_automator.hugo import HugoDeployer
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


def _count_posts_created_today(site_id: str) -> int:
    """Count posts created today for a site.

    Args:
        site_id: Site identifier

    Returns:
        Number of posts created today
    """
    content_root = Path(os.getenv("SITES_CONTENT_PATH", "storage/content"))
    published_dir = content_root / site_id / "articles" / "published"

    if not published_dir.exists():
        return 0

    today = datetime.now(timezone.utc).date()
    count = 0

    for pub_file in published_dir.glob("*.json"):
        try:
            with pub_file.open("r", encoding="utf-8") as f:
                data = json.load(f)

            # Check if created_at exists and is from today
            created_at = data.get("created_at")
            if created_at:
                created_dt = datetime.fromisoformat(created_at)
                # Ensure timezone-aware comparison
                if created_dt.tzinfo is None:
                    created_dt = created_dt.replace(tzinfo=timezone.utc)
                if created_dt.astimezone(timezone.utc).date() == today:
                    count += 1
        except (json.JSONDecodeError, ValueError, KeyError):
            # Skip malformed files
            continue

    return count


def _count_posts_published_today(site_id: str) -> int:
    """Count posts published today for a site.

    Args:
        site_id: Site identifier

    Returns:
        Number of posts published today
    """
    content_root = Path(os.getenv("SITES_CONTENT_PATH", "storage/content"))
    published_dir = content_root / site_id / "articles" / "published"

    if not published_dir.exists():
        return 0

    today = datetime.now(timezone.utc).date()
    count = 0

    for pub_file in published_dir.glob("*.json"):
        try:
            with pub_file.open("r", encoding="utf-8") as f:
                data = json.load(f)

            # Check if published_at exists and is from today
            published_at = data.get("published_at")
            if published_at:
                published_dt = datetime.fromisoformat(published_at)
                # Ensure timezone-aware comparison
                if published_dt.tzinfo is None:
                    published_dt = published_dt.replace(tzinfo=timezone.utc)
                if published_dt.astimezone(timezone.utc).date() == today:
                    count += 1
        except (json.JSONDecodeError, ValueError, KeyError):
            # Skip malformed files
            continue

    return count


def _set_hugo_draft_status(text: str, draft: bool) -> str:
    """Set Hugo draft flag in YAML front matter.

    Args:
        text: Markdown content with YAML frontmatter
        draft: True to set draft=true, False to set draft=false

    Returns:
        Updated content, or original if no frontmatter found
    """
    if not text.startswith("---"):
        return text

    try:
        _, fm, rest = text.split("---", 2)
    except ValueError:
        return text  # malformed frontmatter

    lines = fm.strip("\n").splitlines()

    for i, line in enumerate(lines):
        if line.strip().startswith("draft:"):
            lines[i] = f"draft: {'true' if draft else 'false'}"
            break
    else:
        # Add draft field if not found
        lines.append(f"draft: {'true' if draft else 'false'}")

    new_fm = "\n".join(lines)
    return f"---\n{new_fm}\n---{rest}"


def create_posts_wordpress(
    site_id: str, wordpress: WordPressDeployer, limit: int | None = None
) -> None:
    """
    Create posts on WordPress from generation files.

    Args:
        site_id: Site identifier
        wordpress: WordPressDeployer instance
        limit: Maximum number of posts to create (None for unlimited)

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

    logger.info(f"Starting post creation for {site_id}: {len(generation_files)} files")

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
        f"Post creation complete for {site_id}: "
        f"{created} created, {skipped} skipped, {len(generation_files)} total"
    )


def publish_posts_wordpress(
    site_id: str, wordpress: WordPressDeployer, limit: int | None = None
) -> None:
    """
    Publish draft posts on WordPress by changing status to 'publish'.

    Args:
        site_id: Site identifier
        wordpress: WordPressDeployer instance
        limit: Maximum number of posts to publish (None for unlimited)

    Behavior:
    - Reads all .json files in SITES_CONTENT_PATH/{site_id}/articles/published folder
    - For each file up to limit:
      - Gets post_id and status from published/{slug}.json
      - Changes post_id status to 'publish' using WordPressDeployer
      - Updates published/{slug}.json status field to 'publish'
      - Records published_at timestamp
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
    max_publish = limit if limit is not None else len(published_files)

    published = 0
    skipped = 0

    logger.info(
        f"Starting post publication for {site_id}: {len(published_files)} files"
    )

    for pub_file in published_files:
        if published >= max_publish:
            logger.info(f"Reached publication limit ({max_publish}), stopping")
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
            logger.debug(f"Skipping {slug}: already published")
            continue

        # Update post status to publish
        logger.info(f"Publishing post '{slug}' (ID: {post_id})")
        wordpress.wp(domain, f"post update {post_id} --post_status=publish", check=True)

        # Update published metadata
        pub_data["status"] = "publish"
        pub_data["published_at"] = datetime.now(timezone.utc).isoformat()

        with pub_file.open("w", encoding="utf-8") as f:
            json.dump(pub_data, f, indent=2, ensure_ascii=False)

        published += 1
        logger.info(
            f"Post published: {slug} (ID: {post_id}, {published}/{max_publish})"
        )

    logger.info(
        f"Post publication complete for {site_id}: "
        f"{published} published, {skipped} skipped, {len(published_files)} total"
    )


def create_posts_hugo(site_id: str, hugo: HugoDeployer) -> None:
    """
    Create posts on Hugo from markdown files.

    Args:
        site_id: Site identifier
        hugo: HugoDeployer instance

    Behavior:
    - Deploys entire markdown directory to Hugo content directory using rsync
    - Builds the Hugo site
    """
    site = load_site_config(site_id)
    domain = site["domain"]

    content_root = Path(os.getenv("SITES_CONTENT_PATH", "storage/content"))
    markdown_dir = content_root / site_id / "articles" / "markdown"

    if not markdown_dir.exists():
        logger.warning(f"Markdown directory not found: {markdown_dir}")
        return

    logger.info(f"Deploying content directory for {site_id}")
    hugo.deploy_content_directory(domain, markdown_dir)

    logger.info(f"Building Hugo site for {domain}")
    hugo.build_site(domain)

    logger.info(f"Post creation complete for {site_id}")


def publish_posts_hugo(
    site_id: str, hugo: HugoDeployer, limit: int | None = None
) -> None:
    """
    Publish draft posts on Hugo by changing draft status to false.

    Args:
        site_id: Site identifier
        hugo: HugoDeployer instance
        limit: Maximum number of posts to publish (None for unlimited)

    Behavior:
    - Reads all .json files in SITES_CONTENT_PATH/{site_id}/articles/generation folder
    - For each file up to limit:
      - Checks if already published in published/{slug}.json
      - Changes draft: true → draft: false in local markdown/{slug}.md file
      - Writes published/{slug}.json with status="published"
      - Records published_at timestamp
    - Syncs markdown directory to remote and builds the Hugo site once after all files are published
    """
    site = load_site_config(site_id)
    domain = site["domain"]

    content_root = Path(os.getenv("SITES_CONTENT_PATH", "storage/content"))
    generation_dir = content_root / site_id / "articles" / "generation"
    markdown_dir = content_root / site_id / "articles" / "markdown"
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
    max_publish = limit if limit is not None else len(generation_files)

    published = 0
    skipped = 0

    logger.info(
        f"Starting post publication for {site_id}: {len(generation_files)} files"
    )

    for gen_file in generation_files:
        if published >= max_publish:
            logger.info(f"Reached publication limit ({max_publish}), stopping")
            break

        slug = gen_file.stem

        # Check if already published
        published_path = _articles_published_path(site_id, slug)
        if published_path.exists():
            with published_path.open("r", encoding="utf-8") as f:
                pub_data = json.load(f)

            # Skip if already published
            if pub_data.get("status") == "published":
                skipped += 1
                logger.debug(f"Skipping {slug}: already published")
                continue

        # Load generation metadata for title
        with gen_file.open("r", encoding="utf-8") as f:
            gen_data = json.load(f)

        title = gen_data.get("title", slug)

        # Update draft status in local markdown file
        markdown_path = _articles_markdown_path(site_id, slug)
        if not markdown_path.exists():
            logger.warning(f"Markdown file not found for {slug}, skipping")
            skipped += 1
            continue

        logger.info(f"Publishing post '{title}' ({slug})")

        content = markdown_path.read_text(encoding="utf-8")
        updated_content = _set_hugo_draft_status(content, draft=False)

        if updated_content != content:
            markdown_path.write_text(updated_content, encoding="utf-8")
        else:
            logger.debug(f"Content unchanged for {slug}")

        # Write/update published metadata
        published_data = {
            "slug": slug,
            "published_at": datetime.now(timezone.utc).isoformat(),
            "cms": "hugo",
            "status": "published",
        }
        with published_path.open("w", encoding="utf-8") as f:
            json.dump(published_data, f, indent=2, ensure_ascii=False)

        published += 1
        logger.info(f"Post published: {slug} ({published}/{max_publish})")

    # Deploy updated content and build the Hugo site once after all files are published
    if published > 0:
        logger.info(f"Deploying content directory for {domain}")
        hugo.deploy_content_directory(domain, markdown_dir)

        logger.info(f"Building Hugo site for {domain}")
        hugo.build_site(domain)

    logger.info(
        f"Post publication complete for {site_id}: "
        f"{published} published, {skipped} skipped, {len(generation_files)} total"
    )
