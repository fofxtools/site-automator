import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from site_automator.sites import load_site_config
from site_automator.topics import load_topics
from site_automator.prompts import load_prompt
from site_automator.llm import generate_completion_clean, get_llm_client

logger = logging.getLogger(__name__)

load_dotenv()

MAX_ARTICLES_PER_RUN = 100


def _articles_markdown_path(site_id: str, slug: str) -> Path:
    """Get path to article markdown file."""
    content_root = Path(os.getenv("SITES_CONTENT_PATH", "storage/content"))
    return content_root / site_id / "articles" / "markdown" / f"{slug}.md"


def _articles_generation_path(site_id: str, slug: str) -> Path:
    """Get path to article generation metadata file."""
    content_root = Path(os.getenv("SITES_CONTENT_PATH", "storage/content"))
    return content_root / site_id / "articles" / "generation" / f"{slug}.json"


def generate_articles_llm(site_id: str) -> None:
    """
    Generate articles for a site using an LLM.

    Args:
        site_id: Site identifier

    Behavior:
    - Reads site config from sites.csv
    - Checks if article_strategy is 'llm'
    - Loads topics from topics.json
    - For each topic, if markdown file doesn't exist:
      - Generates article content using LLM
      - Writes markdown file
      - Writes generation metadata JSON
    - Resumable: skips topics that already have markdown files
    - Idempotent: safe to call multiple times
    """
    site = load_site_config(site_id)

    if site.get("article_strategy") != "llm":
        raise ValueError(f"article_strategy is not 'llm' for site_id={site_id}")

    # Load topics
    topics = load_topics(site_id)

    if not topics:
        logger.warning(f"No topics found for {site_id}")
        return

    # Create directories
    content_root = Path(os.getenv("SITES_CONTENT_PATH", "storage/content"))
    markdown_dir = content_root / site_id / "articles" / "markdown"
    generation_dir = content_root / site_id / "articles" / "generation"
    markdown_dir.mkdir(parents=True, exist_ok=True)
    generation_dir.mkdir(parents=True, exist_ok=True)

    # Load prompt template
    prompt_template = load_prompt(
        site["prompts_file"],
        key="article_generation",
    )

    # Get LLM client and model name
    llm = get_llm_client()
    model_name = llm.model

    # Track progress
    total = len(topics)
    generated = 0
    skipped = 0

    logger.info(f"Starting article generation for {site_id}: {total} topics")

    for topic in topics:
        # Stop if we've reached the max articles per run
        if generated >= MAX_ARTICLES_PER_RUN:
            logger.info(
                f"Reached MAX_ARTICLES_PER_RUN ({MAX_ARTICLES_PER_RUN}), stopping"
            )
            break
        title = topic["title"]
        slug = topic["slug"]

        markdown_path = _articles_markdown_path(site_id, slug)

        # Skip if markdown already exists (resumable)
        if markdown_path.exists():
            skipped += 1
            logger.debug(f"Skipping {slug}: markdown already exists")
            continue

        # Generate article
        logger.info(f"Generating article for '{title}' ({slug})")

        prompt = prompt_template.format(title=title)
        article_content = generate_completion_clean(prompt)

        # Write markdown file
        with markdown_path.open("w", encoding="utf-8") as f:
            f.write(article_content)

        # Write generation metadata
        generation_path = _articles_generation_path(site_id, slug)
        metadata = {
            "title": title,
            "slug": slug,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "model": model_name,
        }
        with generation_path.open("w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        generated += 1
        logger.info(f"Article generated: {slug} ({generated}/{total})")

    logger.info(
        f"Article generation complete for {site_id}: "
        f"{generated} generated, {skipped} skipped, {total} total"
    )
