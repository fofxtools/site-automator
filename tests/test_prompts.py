from pathlib import Path
from unittest.mock import patch

import pytest

from site_automator.prompts import load_prompt


def _write_prompts_yaml(tmp_path: Path, content: str) -> str:
    prompts_file = tmp_path / "prompts.yaml"
    prompts_file.write_text(content)
    return str(tmp_path)


class TestLoadPrompt:
    def test_loads_valid_prompt(self, tmp_path):
        yaml_content = "topic_generation: |\n  Generate topics for {seed_topic}\n"
        prompts_dir = _write_prompts_yaml(tmp_path, yaml_content)

        with patch.dict("os.environ", {"SITES_PROMPTS_PATH": prompts_dir}):
            result = load_prompt("prompts.yaml", "topic_generation")

        assert "Generate topics for {seed_topic}" in result

    def test_loads_multiline_prompt(self, tmp_path):
        yaml_content = "article: |\n  Line 1\n  Line 2\n  Line 3\n"
        prompts_dir = _write_prompts_yaml(tmp_path, yaml_content)

        with patch.dict("os.environ", {"SITES_PROMPTS_PATH": prompts_dir}):
            result = load_prompt("prompts.yaml", "article")

        assert "Line 1" in result
        assert "Line 2" in result
        assert "Line 3" in result

    def test_file_not_found(self, tmp_path):
        with patch.dict("os.environ", {"SITES_PROMPTS_PATH": str(tmp_path)}):
            with pytest.raises(ValueError, match="Prompts file not found"):
                load_prompt("nonexistent.yaml", "topic_generation")

    def test_key_not_found(self, tmp_path):
        yaml_content = "topic_generation: Generate topics\n"
        prompts_dir = _write_prompts_yaml(tmp_path, yaml_content)

        with patch.dict("os.environ", {"SITES_PROMPTS_PATH": prompts_dir}):
            with pytest.raises(ValueError, match="Prompt 'nonexistent' not found"):
                load_prompt("prompts.yaml", "nonexistent")

    def test_uses_default_path(self, tmp_path):
        # Create prompts.yaml in local/config structure
        config_dir = tmp_path / "local" / "config"
        config_dir.mkdir(parents=True)
        prompts_file = config_dir / "prompts.yaml"
        prompts_file.write_text("test_prompt: Test content\n")

        # Change to tmp_path as working directory and use default path
        with patch.dict("os.environ", {}, clear=True):
            import os

            original_cwd = os.getcwd()
            try:
                os.chdir(tmp_path)
                result = load_prompt("prompts.yaml", "test_prompt")
                assert result == "Test content"
            finally:
                os.chdir(original_cwd)
