import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from site_automator.articles import generate_articles_llm


class TestGenerateArticlesLLM:
    """Test generate_articles_llm function."""

    def _setup_site_config(self, tmp_path: Path, site_id: str = "site1") -> str:
        """Helper to set up site config CSV."""
        csv_content = (
            "site_id,domain,seed_topic,prompts_file,cms,pages_per_site,posts_per_day,"
            "llm_provider,article_strategy,llm_batch_mode\n"
            f"{site_id},example.com,test topic,prompts.yaml,wordpress,10,2,openai,llm,false\n"
        )
        csv_file = tmp_path / "sites.csv"
        csv_file.write_text(csv_content)
        return str(csv_file)

    def _setup_prompts(self, tmp_path: Path) -> str:
        """Helper to set up prompts.yaml."""
        prompts_content = "article_generation: |\n  Write article for {title}\n"
        prompts_file = tmp_path / "prompts.yaml"
        prompts_file.write_text(prompts_content)
        return str(tmp_path)

    def _setup_topics(self, tmp_path: Path, site_id: str = "site1") -> None:
        """Helper to set up topics.json."""
        topics_data = [
            {"title": "Topic One", "slug": "topic-one"},
            {"title": "Topic Two", "slug": "topic-two"},
            {"title": "Topic Three", "slug": "topic-three"},
        ]
        topics_file = tmp_path / "content" / site_id / "topics.json"
        topics_file.parent.mkdir(parents=True, exist_ok=True)
        topics_file.write_text(json.dumps(topics_data))

    @patch("site_automator.articles.generate_completion_clean")
    @patch("site_automator.articles.get_llm_client")
    def test_generates_articles_from_scratch(
        self, mock_get_llm, mock_generate, tmp_path
    ):
        """Test generating articles from scratch."""
        # Setup
        csv_path = self._setup_site_config(tmp_path)
        prompts_path = self._setup_prompts(tmp_path)
        content_path = tmp_path / "content"
        self._setup_topics(tmp_path)

        # Mock LLM
        mock_llm = Mock()
        mock_llm.model = "gpt-4"
        mock_get_llm.return_value = mock_llm
        mock_generate.return_value = "# Article Content\n\nThis is the article."

        # Execute
        with patch.dict(
            "os.environ",
            {
                "SITES_CONFIG_PATH": csv_path,
                "SITES_PROMPTS_PATH": prompts_path,
                "SITES_CONTENT_PATH": str(content_path),
            },
        ):
            generate_articles_llm("site1")

        # Verify markdown files created
        markdown_dir = content_path / "site1" / "articles" / "markdown"
        assert (markdown_dir / "topic-one.md").exists()
        assert (markdown_dir / "topic-two.md").exists()
        assert (markdown_dir / "topic-three.md").exists()

        # Verify content
        content = (markdown_dir / "topic-one.md").read_text()
        assert "Article Content" in content

        # Verify metadata files created
        gen_dir = content_path / "site1" / "articles" / "generation"
        metadata_file = gen_dir / "topic-one.json"
        assert metadata_file.exists()

        metadata = json.loads(metadata_file.read_text())
        assert metadata["title"] == "Topic One"
        assert metadata["slug"] == "topic-one"
        assert metadata["model"] == "gpt-4"
        assert "generated_at" in metadata

    @patch("site_automator.articles.generate_completion_clean")
    @patch("site_automator.articles.get_llm_client")
    def test_skips_existing_articles(self, mock_get_llm, mock_generate, tmp_path):
        """Test resumable behavior - skips existing articles."""
        # Setup
        csv_path = self._setup_site_config(tmp_path)
        prompts_path = self._setup_prompts(tmp_path)
        content_path = tmp_path / "content"
        self._setup_topics(tmp_path)

        # Create existing markdown file
        markdown_dir = content_path / "site1" / "articles" / "markdown"
        markdown_dir.mkdir(parents=True, exist_ok=True)
        (markdown_dir / "topic-one.md").write_text("Existing article")

        # Mock LLM
        mock_llm = Mock()
        mock_llm.model = "gpt-4"
        mock_get_llm.return_value = mock_llm
        mock_generate.return_value = "# New Article"

        # Execute
        with patch.dict(
            "os.environ",
            {
                "SITES_CONFIG_PATH": csv_path,
                "SITES_PROMPTS_PATH": prompts_path,
                "SITES_CONTENT_PATH": str(content_path),
            },
        ):
            generate_articles_llm("site1")

        # Verify existing file unchanged
        content = (markdown_dir / "topic-one.md").read_text()
        assert content == "Existing article"

        # Verify other files created
        assert (markdown_dir / "topic-two.md").exists()
        assert (markdown_dir / "topic-three.md").exists()

        # Verify generate was called only 2 times (not 3)
        assert mock_generate.call_count == 2

    def test_raises_error_for_wrong_strategy(self, tmp_path):
        """Test raises error when article_strategy is not 'llm'."""
        # Setup with wrong strategy
        csv_content = (
            "site_id,domain,seed_topic,prompts_file,cms,pages_per_site,posts_per_day,"
            "llm_provider,article_strategy,llm_batch_mode\n"
            "site1,example.com,test topic,prompts.yaml,wordpress,10,2,openai,manual,false\n"
        )
        csv_file = tmp_path / "sites.csv"
        csv_file.write_text(csv_content)

        with patch.dict("os.environ", {"SITES_CONFIG_PATH": str(csv_file)}):
            with pytest.raises(ValueError, match="article_strategy is not 'llm'"):
                generate_articles_llm("site1")
