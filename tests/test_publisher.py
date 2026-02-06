import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from site_automator.publisher import (
    create_posts_wordpress,
    publish_posts_wordpress,
)


def _setup_site_config(tmp_path: Path, site_id: str = "site1") -> str:
    """Helper to set up site config CSV."""
    csv_content = (
        "site_id,domain,server,prompts_file,seed_topic,cms,pages_per_site,posts_per_day,"
        "llm_provider,llm_batch_mode\n"
        f"{site_id},example.com,test-server,prompts.yaml,test topic,wordpress,10,2,openai,false\n"
    )
    csv_file = tmp_path / "sites.csv"
    csv_file.write_text(csv_content)
    return str(csv_file)


class TestCreateArticlesWordpress:
    """Test create_posts_wordpress function."""

    def _setup_generation_files(self, tmp_path: Path, site_id: str = "site1") -> None:
        """Helper to set up generation files."""
        gen_dir = tmp_path / "content" / site_id / "articles" / "generation"
        markdown_dir = tmp_path / "content" / site_id / "articles" / "markdown"
        gen_dir.mkdir(parents=True, exist_ok=True)
        markdown_dir.mkdir(parents=True, exist_ok=True)

        # Create generation metadata and markdown files
        for i, slug in enumerate(["article-one", "article-two", "article-three"]):
            gen_data = {"title": f"Article {i+1}", "slug": slug}
            (gen_dir / f"{slug}.json").write_text(json.dumps(gen_data))
            (markdown_dir / f"{slug}.md").write_text(
                f"# Article {i+1}\n\nContent here."
            )

    def test_creates_posts_from_generation_files(self, tmp_path, wordpress):
        """Test creating WordPress posts from generation files."""
        # Setup
        csv_path = _setup_site_config(tmp_path)
        content_path = tmp_path / "content"
        self._setup_generation_files(tmp_path)

        # Mock WordPress create_post to return post IDs
        wordpress.create_post = Mock(side_effect=[101, 102, 103])

        # Execute
        with patch.dict(
            "os.environ",
            {
                "SITES_CONFIG_PATH": csv_path,
                "SITES_CONTENT_PATH": str(content_path),
            },
        ):
            create_posts_wordpress("site1", wordpress)

        # Verify create_post was called 3 times
        assert wordpress.create_post.call_count == 3

        # Verify published metadata files created
        published_dir = content_path / "site1" / "articles" / "published"
        assert (published_dir / "article-one.json").exists()
        assert (published_dir / "article-two.json").exists()
        assert (published_dir / "article-three.json").exists()

        # Verify published metadata content
        pub_data = json.loads((published_dir / "article-one.json").read_text())
        assert pub_data["slug"] == "article-one"
        assert pub_data["post_id"] == 101
        assert pub_data["status"] == "draft"
        assert pub_data["cms"] == "wordpress"
        assert "created_at" in pub_data

    def test_skips_already_published_articles(self, tmp_path, wordpress):
        """Test resumable behavior - skips already published articles."""
        # Setup
        csv_path = _setup_site_config(tmp_path)
        content_path = tmp_path / "content"
        self._setup_generation_files(tmp_path)

        # Create existing published file
        published_dir = content_path / "site1" / "articles" / "published"
        published_dir.mkdir(parents=True, exist_ok=True)
        pub_data = {"slug": "article-one", "post_id": 999, "status": "draft"}
        (published_dir / "article-one.json").write_text(json.dumps(pub_data))

        # Mock WordPress
        wordpress.create_post = Mock(side_effect=[102, 103])

        # Execute
        with patch.dict(
            "os.environ",
            {
                "SITES_CONFIG_PATH": csv_path,
                "SITES_CONTENT_PATH": str(content_path),
            },
        ):
            create_posts_wordpress("site1", wordpress)

        # Verify create_post was called only 2 times (not 3)
        assert wordpress.create_post.call_count == 2

    def test_respects_limit_parameter(self, tmp_path, wordpress):
        """Test limit parameter restricts number of posts created."""
        # Setup
        csv_path = _setup_site_config(tmp_path)
        content_path = tmp_path / "content"
        self._setup_generation_files(tmp_path)

        # Mock WordPress
        wordpress.create_post = Mock(side_effect=[101, 102])

        # Execute with limit=2
        with patch.dict(
            "os.environ",
            {
                "SITES_CONFIG_PATH": csv_path,
                "SITES_CONTENT_PATH": str(content_path),
            },
        ):
            create_posts_wordpress("site1", wordpress, limit=2)

        # Verify only 2 posts created (not all 3)
        assert wordpress.create_post.call_count == 2

    def test_converts_markdown_to_html(self, tmp_path, wordpress):
        """Test markdown is converted to HTML before posting."""
        # Setup
        csv_path = _setup_site_config(tmp_path)
        content_path = tmp_path / "content"
        self._setup_generation_files(tmp_path)

        # Mock WordPress
        wordpress.create_post = Mock(return_value=101)

        # Execute
        with patch.dict(
            "os.environ",
            {
                "SITES_CONFIG_PATH": csv_path,
                "SITES_CONTENT_PATH": str(content_path),
            },
        ):
            create_posts_wordpress("site1", wordpress)

        # Verify HTML content was passed (not markdown)
        call_args = wordpress.create_post.call_args_list[0]
        content = call_args[1]["content"]
        assert "<h1" in content  # HTML heading
        assert "Article 1" in content

    def test_raises_error_if_title_missing(self, tmp_path, wordpress):
        """Test raises error if title is missing from generation file."""
        # Setup
        csv_path = _setup_site_config(tmp_path)
        content_path = tmp_path / "content"
        gen_dir = content_path / "site1" / "articles" / "generation"
        markdown_dir = content_path / "site1" / "articles" / "markdown"
        gen_dir.mkdir(parents=True, exist_ok=True)
        markdown_dir.mkdir(parents=True, exist_ok=True)

        # Create generation file without title
        (gen_dir / "bad.json").write_text(json.dumps({"slug": "bad"}))
        (markdown_dir / "bad.md").write_text("Content")

        # Execute and verify error
        with patch.dict(
            "os.environ",
            {
                "SITES_CONFIG_PATH": csv_path,
                "SITES_CONTENT_PATH": str(content_path),
            },
        ):
            with pytest.raises(ValueError, match="Missing title"):
                create_posts_wordpress("site1", wordpress)


class TestPublishPostsWordpress:
    """Test publish_posts_wordpress function."""

    def _setup_published_files(self, tmp_path: Path, site_id: str = "site1") -> None:
        """Helper to set up published files."""
        published_dir = tmp_path / "content" / site_id / "articles" / "published"
        published_dir.mkdir(parents=True, exist_ok=True)

        # Create published metadata files
        for i, slug in enumerate(["article-one", "article-two", "article-three"]):
            pub_data = {
                "slug": slug,
                "post_id": 100 + i + 1,
                "status": "draft",
                "cms": "wordpress",
                "created_at": "2024-01-01T00:00:00Z",
            }
            (published_dir / f"{slug}.json").write_text(json.dumps(pub_data))

    def test_publishes_draft_posts(self, tmp_path, wordpress):
        """Test publishing draft posts to publish status."""
        # Setup
        csv_path = _setup_site_config(tmp_path)
        content_path = tmp_path / "content"
        self._setup_published_files(tmp_path)

        # Mock WordPress wp method
        wordpress.wp = Mock()

        # Execute
        with patch.dict(
            "os.environ",
            {
                "SITES_CONFIG_PATH": csv_path,
                "SITES_CONTENT_PATH": str(content_path),
            },
        ):
            publish_posts_wordpress("site1", wordpress)

        # Verify wp was called 3 times
        assert wordpress.wp.call_count == 3

        # Verify correct commands
        calls = [call[0] for call in wordpress.wp.call_args_list]
        assert calls[0] == ("example.com", "post update 101 --post_status=publish")
        assert calls[1] == ("example.com", "post update 102 --post_status=publish")
        assert calls[2] == ("example.com", "post update 103 --post_status=publish")

        # Verify metadata updated
        published_dir = content_path / "site1" / "articles" / "published"
        pub_data = json.loads((published_dir / "article-one.json").read_text())
        assert pub_data["status"] == "publish"
        assert "published_at" in pub_data

    def test_skips_already_published(self, tmp_path, wordpress):
        """Test resumable behavior - skips already published posts."""
        # Setup
        csv_path = _setup_site_config(tmp_path)
        content_path = tmp_path / "content"
        published_dir = content_path / "site1" / "articles" / "published"
        published_dir.mkdir(parents=True, exist_ok=True)

        # Create one already published, two drafts
        pub_data_published = {
            "slug": "article-one",
            "post_id": 101,
            "status": "publish",
            "published_at": "2024-01-01T00:00:00Z",
        }
        (published_dir / "article-one.json").write_text(json.dumps(pub_data_published))

        for i, slug in enumerate(["article-two", "article-three"]):
            pub_data = {"slug": slug, "post_id": 102 + i, "status": "draft"}
            (published_dir / f"{slug}.json").write_text(json.dumps(pub_data))

        # Mock WordPress
        wordpress.wp = Mock()

        # Execute
        with patch.dict(
            "os.environ",
            {
                "SITES_CONFIG_PATH": csv_path,
                "SITES_CONTENT_PATH": str(content_path),
            },
        ):
            publish_posts_wordpress("site1", wordpress)

        # Verify wp was called only 2 times (not 3)
        assert wordpress.wp.call_count == 2

    def test_respects_limit_parameter(self, tmp_path, wordpress):
        """Test limit parameter restricts number of posts published."""
        # Setup
        csv_path = _setup_site_config(tmp_path)
        content_path = tmp_path / "content"
        self._setup_published_files(tmp_path)

        # Mock WordPress
        wordpress.wp = Mock()

        # Execute with limit=2
        with patch.dict(
            "os.environ",
            {
                "SITES_CONFIG_PATH": csv_path,
                "SITES_CONTENT_PATH": str(content_path),
            },
        ):
            publish_posts_wordpress("site1", wordpress, limit=2)

        # Verify only 2 posts published (not all 3)
        assert wordpress.wp.call_count == 2

    def test_raises_error_if_post_id_missing(self, tmp_path, wordpress):
        """Test raises error if post_id is missing."""
        # Setup
        csv_path = _setup_site_config(tmp_path)
        content_path = tmp_path / "content"
        published_dir = content_path / "site1" / "articles" / "published"
        published_dir.mkdir(parents=True, exist_ok=True)

        # Create published file without post_id
        pub_data = {"slug": "bad", "status": "draft"}
        (published_dir / "bad.json").write_text(json.dumps(pub_data))

        # Execute and verify error
        with patch.dict(
            "os.environ",
            {
                "SITES_CONFIG_PATH": csv_path,
                "SITES_CONTENT_PATH": str(content_path),
            },
        ):
            with pytest.raises(ValueError, match="Missing post_id"):
                publish_posts_wordpress("site1", wordpress)

    def test_raises_error_if_status_missing(self, tmp_path, wordpress):
        """Test raises error if status is missing."""
        # Setup
        csv_path = _setup_site_config(tmp_path)
        content_path = tmp_path / "content"
        published_dir = content_path / "site1" / "articles" / "published"
        published_dir.mkdir(parents=True, exist_ok=True)

        # Create published file without status
        pub_data = {"slug": "bad", "post_id": 999}
        (published_dir / "bad.json").write_text(json.dumps(pub_data))

        # Execute and verify error
        with patch.dict(
            "os.environ",
            {
                "SITES_CONFIG_PATH": csv_path,
                "SITES_CONTENT_PATH": str(content_path),
            },
        ):
            with pytest.raises(ValueError, match="Missing status"):
                publish_posts_wordpress("site1", wordpress)
