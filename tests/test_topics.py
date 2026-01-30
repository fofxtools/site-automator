import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from site_automator.topics import load_topics, generate_topics_llm


class TestLoadTopics:
    """Test load_topics function."""

    def test_loads_existing_topics(self, tmp_path):
        """Test loading existing topics.json."""
        topics_data = [
            {"title": "Topic 1", "slug": "topic-1"},
            {"title": "Topic 2", "slug": "topic-2"},
        ]
        topics_file = tmp_path / "site1" / "topics.json"
        topics_file.parent.mkdir(parents=True)
        topics_file.write_text(json.dumps(topics_data))

        with patch.dict("os.environ", {"SITES_CONTENT_PATH": str(tmp_path)}):
            result = load_topics("site1")

        assert len(result) == 2
        assert result[0]["title"] == "Topic 1"
        assert result[1]["slug"] == "topic-2"

    def test_file_not_found(self, tmp_path):
        """Test FileNotFoundError when topics.json doesn't exist."""
        with patch.dict("os.environ", {"SITES_CONTENT_PATH": str(tmp_path)}):
            with pytest.raises(FileNotFoundError, match="topics.json does not exist"):
                load_topics("nonexistent")


class TestGenerateTopicsLLM:
    """Test generate_topics_llm function."""

    def _setup_site_config(
        self, tmp_path: Path, site_id: str = "site1", pages: int = 10
    ) -> str:
        """Helper to set up site config CSV."""
        csv_content = (
            "site_id,domain,seed_topic,prompts_file,cms,pages_per_site,posts_per_day,"
            "llm_provider,topic_strategy,llm_batch_mode\n"
            f"{site_id},example.com,test topic,prompts.yaml,wordpress,{pages},2,openai,llm,false\n"
        )
        csv_file = tmp_path / "sites.csv"
        csv_file.write_text(csv_content)
        return str(csv_file)

    def _setup_prompts(self, tmp_path: Path) -> str:
        """Helper to set up prompts.yaml."""
        prompts_content = "topic_generation: |\n  Generate topics for {seed_topic}\n"
        prompts_file = tmp_path / "prompts.yaml"
        prompts_file.write_text(prompts_content)
        return str(tmp_path)

    @patch("site_automator.topics.get_llm_client")
    def test_generates_topics_from_scratch(self, mock_get_llm, tmp_path):
        """Test generating topics from scratch."""
        # Setup
        csv_path = self._setup_site_config(tmp_path, pages=5)
        prompts_path = self._setup_prompts(tmp_path)
        content_path = tmp_path / "content"

        # Mock LLM to return numbered list
        mock_llm = Mock()
        mock_llm.generate_completion.return_value = (
            "1. Topic One\n2. Topic Two\n3. Topic Three\n4. Topic Four\n5. Topic Five"
        )
        mock_get_llm.return_value = mock_llm

        # Execute
        with patch.dict(
            "os.environ",
            {
                "SITES_CONFIG_PATH": csv_path,
                "SITES_PROMPTS_PATH": prompts_path,
                "SITES_CONTENT_PATH": str(content_path),
            },
        ):
            result = generate_topics_llm("site1")

        # Verify
        assert len(result) == 5
        assert result[0]["title"] == "Topic One"
        assert result[0]["slug"] == "topic-one"
        assert result[4]["title"] == "Topic Five"

        # Verify file was written
        topics_file = content_path / "site1" / "topics.json"
        assert topics_file.exists()
        saved_data = json.loads(topics_file.read_text())
        assert len(saved_data) == 5

    @patch("site_automator.topics.get_llm_client")
    def test_returns_existing_complete_topics(self, mock_get_llm, tmp_path):
        """Test idempotent behavior - returns existing complete topics."""
        # Setup
        csv_path = self._setup_site_config(tmp_path, pages=3)
        prompts_path = self._setup_prompts(tmp_path)
        content_path = tmp_path / "content"

        # Create existing complete topics
        existing_topics = [
            {"title": "Existing 1", "slug": "existing-1"},
            {"title": "Existing 2", "slug": "existing-2"},
            {"title": "Existing 3", "slug": "existing-3"},
        ]
        topics_file = content_path / "site1" / "topics.json"
        topics_file.parent.mkdir(parents=True)
        topics_file.write_text(json.dumps(existing_topics))

        # Execute
        with patch.dict(
            "os.environ",
            {
                "SITES_CONFIG_PATH": csv_path,
                "SITES_PROMPTS_PATH": prompts_path,
                "SITES_CONTENT_PATH": str(content_path),
            },
        ):
            result = generate_topics_llm("site1")

        # Verify - should return existing without calling LLM
        assert len(result) == 3
        assert result[0]["title"] == "Existing 1"
        mock_get_llm.assert_not_called()

    @patch("site_automator.topics.get_llm_client")
    def test_resumes_incomplete_topics(self, mock_get_llm, tmp_path):
        """Test resuming generation from incomplete topics."""
        # Setup
        csv_path = self._setup_site_config(tmp_path, pages=5)
        prompts_path = self._setup_prompts(tmp_path)
        content_path = tmp_path / "content"

        # Create incomplete topics (2 out of 5)
        existing_topics = [
            {"title": "Existing 1", "slug": "existing-1"},
            {"title": "Existing 2", "slug": "existing-2"},
        ]
        topics_file = content_path / "site1" / "topics.json"
        topics_file.parent.mkdir(parents=True)
        topics_file.write_text(json.dumps(existing_topics))

        # Mock LLM to return more topics
        mock_llm = Mock()
        mock_llm.generate_completion.return_value = (
            "1. New Topic 3\n2. New Topic 4\n3. New Topic 5"
        )
        mock_get_llm.return_value = mock_llm

        # Execute
        with patch.dict(
            "os.environ",
            {
                "SITES_CONFIG_PATH": csv_path,
                "SITES_PROMPTS_PATH": prompts_path,
                "SITES_CONTENT_PATH": str(content_path),
            },
        ):
            result = generate_topics_llm("site1")

        # Verify - should have 5 total (2 existing + 3 new)
        assert len(result) == 5
        assert result[0]["title"] == "Existing 1"
        assert result[2]["title"] == "New Topic 3"
