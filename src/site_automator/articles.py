import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from site_automator.sites import load_site_config
from site_automator.topics import load_topics
from site_automator.prompts import load_prompt
from site_automator.llm import generate_completion_bulk_clean, get_llm_client

logger = logging.getLogger(__name__)

load_dotenv()

# None means unlimited
MAX_ARTICLES_PER_RUN = None


def _articles_markdown_path(site_id: str, slug: str) -> Path:
    """Get path to article markdown file."""
    content_root = Path(os.getenv("SITES_CONTENT_PATH", "storage/content"))
    return content_root / site_id / "articles" / "markdown" / f"{slug}.md"


def _articles_generation_path(site_id: str, slug: str) -> Path:
    """Get path to article generation metadata file."""
    content_root = Path(os.getenv("SITES_CONTENT_PATH", "storage/content"))
    return content_root / site_id / "articles" / "generation" / f"{slug}.json"


def _strip_leading_title_heading(content: str, expected_title: str) -> str:
    """Remove leading Markdown heading (any level) if it matches the expected title."""
    stripped = content.lstrip()
    lines = stripped.splitlines()

    if not lines:
        return content

    first_line = lines[0].strip()

    if first_line.startswith("#"):
        # Count leading #'s
        i = 0
        while i < len(first_line) and first_line[i] == "#":
            i += 1

        # Must have a space after hashes to be a valid heading
        if i > 0 and len(first_line) > i and first_line[i] == " ":
            heading_text = first_line[i + 1 :].strip()

            if heading_text.lower() == expected_title.lower():
                # Remove heading and any immediate blank line
                remaining = "\n".join(lines[1:]).lstrip("\n")
                return remaining

    return content


def generate_articles_llm(site_id: str, add_hugo_frontmatter: bool = False) -> None:
    """
    Generate articles for a site using an LLM.

    Args:
        site_id: Site identifier
        add_hugo_frontmatter: If True, prepend Hugo frontmatter with draft: true

    Behavior:
    - Reads site config from sites.csv
    - Checks if article_strategy is 'llm'
    - Loads topics from topics.json
    - For each topic, if markdown file doesn't exist:
      - Generates article content using LLM
      - Optionally prepends Hugo frontmatter (draft: true)
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
    failed = 0

    logger.info(f"Starting article generation for {site_id}: {total} topics")

    # First pass: determine which topics still need articles
    pending_topics: list[dict[str, Any]] = []
    pending_markdown_paths: list[Path] = []

    for topic in topics:
        slug = topic["slug"]
        markdown_path = _articles_markdown_path(site_id, slug)

        if markdown_path.exists():
            skipped += 1
            logger.debug(f"Skipping {slug}: markdown already exists")
            continue

        pending_topics.append(topic)
        pending_markdown_paths.append(markdown_path)

    # Apply MAX_ARTICLES_PER_RUN (None means unlimited)
    if MAX_ARTICLES_PER_RUN is None:
        batch_topics = pending_topics
        batch_markdown_paths = pending_markdown_paths
    else:
        batch_topics = pending_topics[:MAX_ARTICLES_PER_RUN]
        batch_markdown_paths = pending_markdown_paths[:MAX_ARTICLES_PER_RUN]

    if not batch_topics:
        logger.info(f"No new articles to generate for {site_id}")
    else:
        logger.info(
            f"Generating {len(batch_topics)} articles for {site_id} "
            f"(MAX_ARTICLES_PER_RUN={MAX_ARTICLES_PER_RUN})"
        )

        # Build prompts for bulk generation
        prompts = [
            prompt_template.format(title=topic["title"], seed_topic=site["seed_topic"])
            for topic in batch_topics
        ]

        # Bulk-generate article contents. Results are aligned with prompts.
        results = generate_completion_bulk_clean(prompts)

        for topic, markdown_path, article_content in zip(
            batch_topics, batch_markdown_paths, results
        ):
            title = topic["title"]
            slug = topic["slug"]

            if article_content is None:
                logger.warning(f"LLM generation failed for '{title}' ({slug})")
                failed += 1
                continue

            article_content = _strip_leading_title_heading(article_content, title)

            # Prepend Hugo frontmatter if requested
            if add_hugo_frontmatter:
                timestamp = datetime.now(timezone.utc).isoformat()
                # Use YAML serialization for safe escaping
                frontmatter_data = {
                    "title": title,
                    "date": timestamp,
                    "draft": True,
                }
                yaml_content = yaml.safe_dump(
                    frontmatter_data,
                    sort_keys=False,
                    allow_unicode=True,
                    default_flow_style=False,
                ).strip()
                frontmatter = f"---\n{yaml_content}\n---\n\n"
                article_content = frontmatter + article_content

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
        f"{generated} generated, {skipped} skipped, {failed} failed, {total} total"
    )
