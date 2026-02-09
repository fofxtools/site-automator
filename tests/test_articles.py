import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from site_automator.articles import (
    _articles_generation_path,
    _articles_markdown_path,
    generate_articles_llm,
)


class TestArticlesMarkdownPath:
    """Test _articles_markdown_path helper function."""

    def test_returns_correct_path(self, tmp_path):
        """Test constructs correct markdown file path."""
        content_path = tmp_path / "content"

        with patch.dict("os.environ", {"SITES_CONTENT_PATH": str(content_path)}):
            path = _articles_markdown_path("site1", "my-article")

        expected = content_path / "site1" / "articles" / "markdown" / "my-article.md"
        assert path == expected

    def test_uses_default_content_path(self):
        """Test uses default path when env var not set."""
        with patch.dict("os.environ", {}, clear=True):
            path = _articles_markdown_path("site1", "test")

        assert str(path).startswith("storage/content")
        assert path.name == "test.md"


class TestArticlesGenerationPath:
    """Test _articles_generation_path helper function."""

    def test_returns_correct_path(self, tmp_path):
        """Test constructs correct generation metadata path."""
        content_path = tmp_path / "content"

        with patch.dict("os.environ", {"SITES_CONTENT_PATH": str(content_path)}):
            path = _articles_generation_path("site1", "my-article")

        expected = (
            content_path / "site1" / "articles" / "generation" / "my-article.json"
        )
        assert path == expected

    def test_uses_default_content_path(self):
        """Test uses default path when env var not set."""
        with patch.dict("os.environ", {}, clear=True):
            path = _articles_generation_path("site1", "test")

        assert str(path).startswith("storage/content")
        assert path.name == "test.json"


class TestGenerateArticlesLLM:
    """Test generate_articles_llm function."""

    def _setup_site_config(self, tmp_path: Path, site_id: str = "site1") -> str:
        """Helper to set up site config CSV."""
        csv_content = (
            "site_id,domain,server,prompts_file,seed_topic,cms,pages_per_site,posts_per_day,"
            "llm_provider,article_strategy,llm_batch_mode\n"
            f"{site_id},example.com,test-server,prompts.yaml,test topic,wordpress,10,2,openai,llm,false\n"
        )
        csv_file = tmp_path / "sites.csv"
        csv_file.write_text(csv_content)
        return str(csv_file)

    def _setup_prompts(self, tmp_path: Path) -> str:
        """Helper to set up prompts.yaml."""
        prompts_content = (
            "article_generation: |\n  Write article titled {title} about {seed_topic}\n"
        )
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

    @patch("site_automator.articles.generate_completion_bulk_clean")
    @patch("site_automator.articles.get_llm_client")
    def test_generates_articles_from_scratch(
        self, mock_get_llm, mock_generate_bulk, tmp_path
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
        mock_generate_bulk.return_value = [
            "# Article Content\n\nThis is the article.",
            "# Article Content\n\nThis is the article.",
            "# Article Content\n\nThis is the article.",
        ]

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

        # Verify prompts were generated with correct substitutions
        mock_generate_bulk.assert_called_once()
        called_prompts = mock_generate_bulk.call_args.args[0]
        assert len(called_prompts) == 3

        # Verify substitution happened correctly in first prompt
        assert "Topic One" in called_prompts[0]
        assert "test topic" in called_prompts[0]
        assert "{title}" not in called_prompts[0]
        assert "{seed_topic}" not in called_prompts[0]

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

    @patch("site_automator.articles.generate_completion_bulk_clean")
    @patch("site_automator.articles.get_llm_client")
    def test_skips_existing_articles(self, mock_get_llm, mock_generate_bulk, tmp_path):
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
        mock_generate_bulk.return_value = ["# New Article", "# New Article"]

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

        # Verify bulk generate was called once with 2 prompts (for the 2 new topics)
        mock_generate_bulk.assert_called_once()
        called_prompts = mock_generate_bulk.call_args.args[0]
        assert len(called_prompts) == 2

        # Verify substitution happened correctly (Topic One was skipped, so we have Two and Three)
        assert "Topic Two" in called_prompts[0]
        assert "test topic" in called_prompts[0]
        assert "{title}" not in called_prompts[0]
        assert "{seed_topic}" not in called_prompts[0]

        assert "Topic Three" in called_prompts[1]
        assert "test topic" in called_prompts[1]
        assert "{title}" not in called_prompts[1]
        assert "{seed_topic}" not in called_prompts[1]

    def test_raises_error_for_wrong_strategy(self, tmp_path):
        """Test raises error when article_strategy is not 'llm'."""
        # Setup with wrong strategy
        csv_content = (
            "site_id,domain,server,prompts_file,seed_topic,cms,pages_per_site,posts_per_day,"
            "llm_provider,article_strategy,llm_batch_mode\n"
            "site1,example.com,test-server,prompts.yaml,test topic,wordpress,10,2,openai,manual,false\n"
        )
        csv_file = tmp_path / "sites.csv"
        csv_file.write_text(csv_content)

        with patch.dict("os.environ", {"SITES_CONFIG_PATH": str(csv_file)}):
            with pytest.raises(ValueError, match="article_strategy is not 'llm'"):
                generate_articles_llm("site1")

    @patch("site_automator.articles.generate_completion_bulk_clean")
    @patch("site_automator.articles.get_llm_client")
    def test_adds_hugo_frontmatter_when_requested(
        self, mock_get_llm, mock_generate_bulk, tmp_path
    ):
        """Test that Hugo frontmatter is added when flag is True."""
        # Setup
        csv_path = self._setup_site_config(tmp_path)
        prompts_path = self._setup_prompts(tmp_path)
        content_path = tmp_path / "content"
        self._setup_topics(tmp_path)

        # Mock LLM
        mock_llm = Mock()
        mock_llm.model = "gpt-4"
        mock_get_llm.return_value = mock_llm
        mock_generate_bulk.return_value = [
            "Article content here.",
            "Article content here.",
            "Article content here.",
        ]

        # Execute with Hugo frontmatter flag
        with patch.dict(
            "os.environ",
            {
                "SITES_CONFIG_PATH": csv_path,
                "SITES_PROMPTS_PATH": prompts_path,
                "SITES_CONTENT_PATH": str(content_path),
            },
        ):
            generate_articles_llm("site1", add_hugo_frontmatter=True)

        # Verify frontmatter was added
        markdown_dir = content_path / "site1" / "articles" / "markdown"
        content = (markdown_dir / "topic-one.md").read_text()

        # Check for frontmatter structure (YAML serialized)
        assert content.startswith("---\n")
        assert "title: Topic One" in content  # YAML doesn't quote simple strings
        assert "date:" in content
        assert "draft: true" in content
        assert "---\n\nArticle content here." in content

    @patch("site_automator.articles.generate_completion_bulk_clean")
    @patch("site_automator.articles.get_llm_client")
    def test_handles_quotes_in_hugo_frontmatter(
        self, mock_get_llm, mock_generate_bulk, tmp_path
    ):
        """Test that quotes in titles are properly handled by YAML serialization."""
        # Setup with a topic that has quotes in the title
        csv_path = self._setup_site_config(tmp_path)
        prompts_path = self._setup_prompts(tmp_path)
        content_path = tmp_path / "content"

        # Create topic with quotes in title
        topics_data = [
            {
                "title": '"A Journey to the Heart of Buddhism: Visiting the Sacred Sites of Cambodia"',
                "slug": "journey-to-buddhism",
            }
        ]
        topics_file = content_path / "site1" / "topics.json"
        topics_file.parent.mkdir(parents=True, exist_ok=True)
        topics_file.write_text(json.dumps(topics_data))

        # Mock LLM
        mock_llm = Mock()
        mock_llm.model = "gpt-4"
        mock_get_llm.return_value = mock_llm
        mock_generate_bulk.return_value = ["Article content here."]

        # Execute with Hugo frontmatter flag
        with patch.dict(
            "os.environ",
            {
                "SITES_CONFIG_PATH": csv_path,
                "SITES_PROMPTS_PATH": prompts_path,
                "SITES_CONTENT_PATH": str(content_path),
            },
        ):
            generate_articles_llm("site1", add_hugo_frontmatter=True)

        # Verify frontmatter has properly handled quotes via YAML serialization
        markdown_dir = content_path / "site1" / "articles" / "markdown"
        content = (markdown_dir / "journey-to-buddhism.md").read_text()

        # YAML serializer will quote strings containing quotes with single quotes
        assert content.startswith("---\n")
        assert (
            "title: '\"A Journey to the Heart of Buddhism: Visiting the Sacred Sites of Cambodia\"'"
            in content
        )
        assert "draft: true" in content
        assert "---\n\nArticle content here." in content
