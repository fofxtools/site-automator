import os
import random
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

load_dotenv()


def load_prompt(prompts_file: str, key: str) -> str:
    """
    Load a prompt string from a YAML prompts file.

    Supports both single prompts (strings) and multiple prompt variations (lists).
    When a list is provided, a random prompt is selected from the list.

    Args:
        prompts_file: Filename like "prompts.yaml"
        key: Prompt key, e.g. "topic_generation"

    Returns:
        Prompt template string

    Raises:
        ValueError if file or key is missing, or if prompt list is empty
    """
    prompts_root = Path(os.getenv("SITES_PROMPTS_PATH", "local/config"))
    path = prompts_root / prompts_file

    if not path.exists():
        raise ValueError(f"Prompts file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        data: dict[str, Any] = yaml.safe_load(f) or {}

    if key not in data:
        raise ValueError(f"Prompt '{key}' not found in {prompts_file}")

    value = data[key]

    # Handle list of prompts (randomization)
    if isinstance(value, list):
        if not value:
            raise ValueError(f"Prompt '{key}' is an empty list in {prompts_file}")
        # Type assertion: we know the list contains strings from YAML
        selected: str = random.choice(value)
        return selected

    # Handle single prompt (backward compatibility)
    return str(value)
