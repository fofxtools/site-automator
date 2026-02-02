import json
import logging
import math
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from slugify import slugify

from site_automator.sites import load_site_config
from site_automator.prompts import load_prompt
from site_automator.llm import generate_list_items_bulk

logger = logging.getLogger(__name__)

load_dotenv()

MAX_TOPIC_GENERATION_BATCHES = 20


def _topics_path(site_id: str) -> Path:
    content_root = Path(os.getenv("SITES_CONTENT_PATH", "storage/content"))
    return content_root / site_id / "topics.json"


def load_topics(site_id: str) -> list[dict[str, Any]]:
    """Load existing topics.json for a site."""
    path = _topics_path(site_id)

    if not path.exists():
        raise FileNotFoundError(f"topics.json does not exist for site_id={site_id}")

    with path.open("r", encoding="utf-8") as f:
        data: list[dict[str, Any]] = json.load(f)
        return data


def generate_topics_site_id(
    site_id: str, batch_size: int = 100
) -> list[dict[str, Any]]:
    """
    Generate topics for a site using an LLM.

    Args:
        site_id: Site identifier
        batch_size: Assumed number of items returned per prompt (used to calculate
                    how many prompts to generate per iteration)

    Behavior:
    - Reads site config from sites.csv
    - If topics.json exists and is complete: returns existing topics
    - If topics.json exists and is incomplete: resumes generation
    - Generates topics in batches until pages_per_site or max batches is reached
    - Writes topics.json incrementally after each batch
    - Deduplicates topics by slug
    - Idempotent: safe to call multiple times
    """
    site = load_site_config(site_id)

    if site["topic_strategy"] != "llm":
        raise ValueError(f"topic_strategy is not 'llm' for site_id={site_id}")

    topics_path = _topics_path(site_id)
    topics_path.parent.mkdir(parents=True, exist_ok=True)

    target_count = site["pages_per_site"]

    # Load existing topics or start fresh
    if topics_path.exists():
        all_topics = load_topics(site_id)
        # If already complete, return immediately (idempotent)
        if len(all_topics) >= target_count:
            logger.info(
                f"Topics already complete for {site_id}: {len(all_topics)}/{target_count}"
            )
            return all_topics[:target_count]
        logger.info(
            f"Resuming topic generation for {site_id}: {len(all_topics)}/{target_count} existing"
        )
    else:
        logger.info(f"Starting topic generation for {site_id}: 0/{target_count}")
        all_topics = []

    # Build deduplication set from existing topics (by slug)
    seen_slugs = {topic["slug"] for topic in all_topics}

    prompt_template = load_prompt(
        site["prompts_file"],
        key="topic_generation",
    )

    iteration = 0

    while len(all_topics) < target_count and (
        MAX_TOPIC_GENERATION_BATCHES is None or iteration < MAX_TOPIC_GENERATION_BATCHES
    ):
        iteration += 1

        # Calculate how many prompts to generate based on remaining need
        remaining = target_count - len(all_topics)
        num_prompts = math.ceil(remaining / batch_size)

        # Generate multiple prompts
        prompts = [
            prompt_template.format(seed_topic=site["seed_topic"])
            for _ in range(num_prompts)
        ]

        # Call LLM in bulk and parse (already deduped within batch)
        titles = generate_list_items_bulk(prompts)

        if not titles:
            # LLM returned nothing parseable, continue to next iteration
            continue

        # Deduplicate and add new topics
        for title in titles:
            slug = slugify(title)
            if slug not in seen_slugs:
                seen_slugs.add(slug)
                all_topics.append(
                    {
                        "title": title,
                        "slug": slug,
                    }
                )

                # Stop if we've reached target
                if len(all_topics) >= target_count:
                    break

        # Write incrementally after each batch (truncate to target)
        topics_to_save = all_topics[:target_count]
        with topics_path.open("w", encoding="utf-8") as f:
            json.dump(topics_to_save, f, indent=2, ensure_ascii=False)

        logger.info(
            f"Batch {iteration} complete for {site_id}: {len(all_topics)}/{target_count} topics"
        )

    # Final check
    if not all_topics:
        logger.error(
            f"Failed to generate any topics for {site_id} after {iteration} batches"
        )
        raise RuntimeError(
            f"Failed to generate any topics for site_id={site_id} "
            f"after {iteration} iterations"
        )

    logger.info(
        f"Topic generation complete for {site_id}: {len(all_topics[:target_count])} topics"
    )

    # Return truncated list
    return all_topics[:target_count]
