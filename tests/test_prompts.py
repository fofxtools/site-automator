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

    def test_loads_list_prompt_returns_one_item(self, tmp_path):
        """Test that list-based prompts return one of the items."""
        yaml_content = (
            "topic_generation:\n"
            "  - Generate topics for {seed_topic}\n"
            "  - Create topics for {seed_topic}\n"
            "  - Write topics for {seed_topic}\n"
        )
        prompts_dir = _write_prompts_yaml(tmp_path, yaml_content)

        with patch.dict("os.environ", {"SITES_PROMPTS_PATH": prompts_dir}):
            result = load_prompt("prompts.yaml", "topic_generation")

        # Should return one of the three options
        assert result in [
            "Generate topics for {seed_topic}",
            "Create topics for {seed_topic}",
            "Write topics for {seed_topic}",
        ]

    def test_loads_list_prompt_with_multiline(self, tmp_path):
        """Test that list-based prompts work with multiline strings."""
        yaml_content = (
            "article:\n"
            "  - |\n"
            "    Line 1\n"
            "    Line 2\n"
            "  - |\n"
            "    Line A\n"
            "    Line B\n"
        )
        prompts_dir = _write_prompts_yaml(tmp_path, yaml_content)

        with patch.dict("os.environ", {"SITES_PROMPTS_PATH": prompts_dir}):
            result = load_prompt("prompts.yaml", "article")

        # Should return one of the two multiline options
        assert "Line 1" in result or "Line A" in result

    def test_empty_list_raises_error(self, tmp_path):
        """Test that empty list raises ValueError."""
        yaml_content = "topic_generation: []\n"
        prompts_dir = _write_prompts_yaml(tmp_path, yaml_content)

        with patch.dict("os.environ", {"SITES_PROMPTS_PATH": prompts_dir}):
            with pytest.raises(ValueError, match="is an empty list"):
                load_prompt("prompts.yaml", "topic_generation")

    def test_list_randomization_varies(self, tmp_path):
        """Test that random selection actually varies across calls."""
        yaml_content = (
            "topic_generation:\n" "  - Option A\n" "  - Option B\n" "  - Option C\n"
        )
        prompts_dir = _write_prompts_yaml(tmp_path, yaml_content)

        results = set()
        with patch.dict("os.environ", {"SITES_PROMPTS_PATH": prompts_dir}):
            # Call multiple times to check for variation
            for _ in range(50):
                result = load_prompt("prompts.yaml", "topic_generation")
                results.add(result)

        # With many calls and 3 options, we should get at least 2 different results
        assert len(results) >= 2

    def test_backward_compatibility_string_still_works(self, tmp_path):
        """Test that old string-based prompts still work (backward compatibility)."""
        yaml_content = "topic_generation: Generate topics for {seed_topic}\n"
        prompts_dir = _write_prompts_yaml(tmp_path, yaml_content)

        with patch.dict("os.environ", {"SITES_PROMPTS_PATH": prompts_dir}):
            result = load_prompt("prompts.yaml", "topic_generation")

        assert result == "Generate topics for {seed_topic}"
