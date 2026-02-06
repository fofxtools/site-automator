import csv
import os
from pathlib import Path
from typing import Any
import json

from dotenv import load_dotenv
from site_automator.utils import parse_bool

load_dotenv()

CSV_REQUIRED_HEADERS = {
    "site_id",
    "domain",
    "server",
    "prompts_file",
    "seed_topic",
    "cms",
    "pages_per_site",
    "posts_per_day",
    "llm_provider",
}
CSV_INTEGER_HEADERS = {"pages_per_site", "posts_per_day"}
CSV_BOOLEAN_HEADERS = {"llm_batch_mode"}


def load_all_sites() -> list[dict[str, str]]:
    csv_path = Path(os.getenv("SITES_CONFIG_PATH", "local/config/sites.csv"))

    if not csv_path.exists():
        raise FileNotFoundError(f"Sites config not found: {csv_path}")

    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        if not reader.fieldnames:
            raise ValueError("CSV has no headers")

        missing = CSV_REQUIRED_HEADERS - set(reader.fieldnames)
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        rows = list(reader)

    site_ids = [row["site_id"] for row in rows]
    if len(site_ids) != len(set(site_ids)):
        raise ValueError("Duplicate site_id values found")

    return rows


def load_site_config(site_id: str) -> dict[str, Any]:
    for site in load_all_sites():
        if site["site_id"] == site_id:
            return _normalize_site_row(site)

    raise ValueError(f"site_id not found: {site_id}")


def load_site_config_by_domain(domain: str) -> dict[str, Any]:
    """Load site config by domain.

    Args:
        domain: Domain name (e.g., "example.com")

    Returns:
        Normalized site configuration dictionary

    Raises:
        ValueError: If domain not found in sites.csv
    """
    for site in load_all_sites():
        if site["domain"] == domain:
            return _normalize_site_row(site)

    raise ValueError(f"domain not found: {domain}")


def _normalize_site_row(row: dict[str, str]) -> dict[str, Any]:
    normalized: dict[str, Any] = dict(row)

    for field in CSV_INTEGER_HEADERS:
        value = row.get(field)
        if value:
            normalized[field] = int(value)

    for field in CSV_BOOLEAN_HEADERS:
        normalized[field] = parse_bool(row.get(field))

    return normalized


def initialize_site(site_id: str) -> dict[str, Any]:
    """
    Initialize a site directory and write an informational site.init.json snapshot.

    - site.init.json is for human reference only
    - The system should NEVER read configuration from site.init.json
    - If the file already exists, it is left untouched
    - The returned config ALWAYS comes from sites.csv
    """
    content_root = Path(os.getenv("SITES_CONTENT_PATH", "storage/content"))

    site_config = load_site_config(site_id)

    site_dir = content_root / site_id
    site_dir.mkdir(parents=True, exist_ok=True)

    init_json_path = site_dir / "site.init.json"

    if not init_json_path.exists():
        with init_json_path.open("w", encoding="utf-8") as f:
            json.dump(site_config, f, indent=2, sort_keys=True)

    return site_config
