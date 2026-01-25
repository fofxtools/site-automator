import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

load_dotenv()


def load_prompt(prompts_file: str, key: str) -> str:
    """
    Load a prompt string from a YAML prompts file.

    Args:
        prompts_file: Filename like "prompts.yaml"
        key: Prompt key, e.g. "topic_generation"

    Returns:
        Prompt template string

    Raises:
        ValueError if file or key is missing
    """
    prompts_root = Path(os.getenv("SITES_PROMPTS_PATH", "local/config"))
    path = prompts_root / prompts_file

    if not path.exists():
        raise ValueError(f"Prompts file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        data: dict[str, Any] = yaml.safe_load(f) or {}

    if key not in data:
        raise ValueError(f"Prompt '{key}' not found in {prompts_file}")

    return str(data[key])
