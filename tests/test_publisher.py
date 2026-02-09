import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from site_automator.publisher import (
    _articles_markdown_path,
    _articles_published_path,
    _count_posts_created_today,
    _count_posts_published_today,
    _set_hugo_draft_status,
    create_posts_hugo,
    create_posts_wordpress,
    publish_posts_hugo,
    publish_posts_wordpress,
)


class TestArticlesPublishedPath:
    """Test _articles_published_path helper function."""

    def test_returns_correct_path(self, tmp_path):
        """Test constructs correct published metadata path."""
        content_path = tmp_path / "content"

        with patch.dict("os.environ", {"SITES_CONTENT_PATH": str(content_path)}):
            path = _articles_published_path("site1", "my-article")

        expected = content_path / "site1" / "articles" / "published" / "my-article.json"
        assert path == expected

    def test_uses_default_content_path(self):
        """Test uses default path when env var not set."""
        with patch.dict("os.environ", {}, clear=True):
            path = _articles_published_path("site1", "test")

        assert str(path).startswith("storage/content")
        assert path.name == "test.json"


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


class TestCountPostsCreatedToday:
    """Test _count_posts_created_today function."""

    def test_returns_zero_if_no_published_directory(self, tmp_path):
        """Test returns 0 when published directory doesn't exist."""
        content_path = tmp_path / "content"

        with patch.dict("os.environ", {"SITES_CONTENT_PATH": str(content_path)}):
            count = _count_posts_created_today("site1")

        assert count == 0

    def test_returns_zero_if_no_posts_today(self, tmp_path):
        """Test returns 0 when no posts were created today."""
        content_path = tmp_path / "content"
        published_dir = content_path / "site1" / "articles" / "published"
        published_dir.mkdir(parents=True, exist_ok=True)

        # Create post from old date
        old_date = "2024-01-01T00:00:00Z"
        pub_data = {"slug": "old", "created_at": old_date}
        (published_dir / "old.json").write_text(json.dumps(pub_data))

        with patch.dict("os.environ", {"SITES_CONTENT_PATH": str(content_path)}):
            count = _count_posts_created_today("site1")

        assert count == 0

    def test_counts_posts_created_today(self, tmp_path):
        """Test correctly counts posts created today."""
        from datetime import datetime, timezone

        content_path = tmp_path / "content"
        published_dir = content_path / "site1" / "articles" / "published"
        published_dir.mkdir(parents=True, exist_ok=True)

        # Create posts with today's date
        today = datetime.now(timezone.utc).isoformat()
        for i in range(3):
            pub_data = {"slug": f"post-{i}", "created_at": today}
            (published_dir / f"post-{i}.json").write_text(json.dumps(pub_data))

        with patch.dict("os.environ", {"SITES_CONTENT_PATH": str(content_path)}):
            count = _count_posts_created_today("site1")

        assert count == 3

    def test_counts_only_today_posts(self, tmp_path):
        """Test counts only today's posts, not old dates."""
        from datetime import datetime, timezone

        content_path = tmp_path / "content"
        published_dir = content_path / "site1" / "articles" / "published"
        published_dir.mkdir(parents=True, exist_ok=True)

        # Create posts from today
        today = datetime.now(timezone.utc).isoformat()
        for i in range(2):
            pub_data = {"slug": f"today-{i}", "created_at": today}
            (published_dir / f"today-{i}.json").write_text(json.dumps(pub_data))

        # Create posts from old date
        old_date = "2024-01-01T00:00:00Z"
        for i in range(3):
            pub_data = {"slug": f"old-{i}", "created_at": old_date}
            (published_dir / f"old-{i}.json").write_text(json.dumps(pub_data))

        with patch.dict("os.environ", {"SITES_CONTENT_PATH": str(content_path)}):
            count = _count_posts_created_today("site1")

        assert count == 2

    def test_handles_malformed_json(self, tmp_path):
        """Test skips malformed JSON files gracefully."""
        content_path = tmp_path / "content"
        published_dir = content_path / "site1" / "articles" / "published"
        published_dir.mkdir(parents=True, exist_ok=True)

        # Create malformed JSON
        (published_dir / "bad.json").write_text("{invalid json")

        with patch.dict("os.environ", {"SITES_CONTENT_PATH": str(content_path)}):
            count = _count_posts_created_today("site1")

        assert count == 0

    def test_handles_missing_created_at_field(self, tmp_path):
        """Test skips posts without created_at field."""
        content_path = tmp_path / "content"
        published_dir = content_path / "site1" / "articles" / "published"
        published_dir.mkdir(parents=True, exist_ok=True)

        # Create post without created_at
        pub_data = {"slug": "no-timestamp"}
        (published_dir / "no-timestamp.json").write_text(json.dumps(pub_data))

        with patch.dict("os.environ", {"SITES_CONTENT_PATH": str(content_path)}):
            count = _count_posts_created_today("site1")

        assert count == 0


class TestCountPostsPublishedToday:
    """Test _count_posts_published_today function."""

    def test_returns_zero_if_no_published_directory(self, tmp_path):
        """Test returns 0 when published directory doesn't exist."""
        content_path = tmp_path / "content"

        with patch.dict("os.environ", {"SITES_CONTENT_PATH": str(content_path)}):
            count = _count_posts_published_today("site1")

        assert count == 0

    def test_returns_zero_if_no_posts_today(self, tmp_path):
        """Test returns 0 when no posts were published today."""
        content_path = tmp_path / "content"
        published_dir = content_path / "site1" / "articles" / "published"
        published_dir.mkdir(parents=True, exist_ok=True)

        # Create post from old date
        old_date = "2024-01-01T00:00:00Z"
        pub_data = {"slug": "old", "published_at": old_date}
        (published_dir / "old.json").write_text(json.dumps(pub_data))

        with patch.dict("os.environ", {"SITES_CONTENT_PATH": str(content_path)}):
            count = _count_posts_published_today("site1")

        assert count == 0

    def test_counts_posts_published_today(self, tmp_path):
        """Test correctly counts posts published today."""
        from datetime import datetime, timezone

        content_path = tmp_path / "content"
        published_dir = content_path / "site1" / "articles" / "published"
        published_dir.mkdir(parents=True, exist_ok=True)

        # Create posts with today's date
        today = datetime.now(timezone.utc).isoformat()
        for i in range(3):
            pub_data = {"slug": f"post-{i}", "published_at": today}
            (published_dir / f"post-{i}.json").write_text(json.dumps(pub_data))

        with patch.dict("os.environ", {"SITES_CONTENT_PATH": str(content_path)}):
            count = _count_posts_published_today("site1")

        assert count == 3

    def test_counts_only_today_posts(self, tmp_path):
        """Test counts only today's posts, not old dates."""
        from datetime import datetime, timezone

        content_path = tmp_path / "content"
        published_dir = content_path / "site1" / "articles" / "published"
        published_dir.mkdir(parents=True, exist_ok=True)

        # Create posts from today
        today = datetime.now(timezone.utc).isoformat()
        for i in range(2):
            pub_data = {"slug": f"today-{i}", "published_at": today}
            (published_dir / f"today-{i}.json").write_text(json.dumps(pub_data))

        # Create posts from old date
        old_date = "2024-01-01T00:00:00Z"
        for i in range(3):
            pub_data = {"slug": f"old-{i}", "published_at": old_date}
            (published_dir / f"old-{i}.json").write_text(json.dumps(pub_data))

        with patch.dict("os.environ", {"SITES_CONTENT_PATH": str(content_path)}):
            count = _count_posts_published_today("site1")

        assert count == 2

    def test_handles_malformed_json(self, tmp_path):
        """Test skips malformed JSON files gracefully."""
        content_path = tmp_path / "content"
        published_dir = content_path / "site1" / "articles" / "published"
        published_dir.mkdir(parents=True, exist_ok=True)

        # Create malformed JSON
        (published_dir / "bad.json").write_text("{invalid json")

        with patch.dict("os.environ", {"SITES_CONTENT_PATH": str(content_path)}):
            count = _count_posts_published_today("site1")

        assert count == 0

    def test_handles_missing_published_at_field(self, tmp_path):
        """Test skips posts without published_at field."""
        content_path = tmp_path / "content"
        published_dir = content_path / "site1" / "articles" / "published"
        published_dir.mkdir(parents=True, exist_ok=True)

        # Create post without published_at
        pub_data = {"slug": "no-timestamp"}
        (published_dir / "no-timestamp.json").write_text(json.dumps(pub_data))

        with patch.dict("os.environ", {"SITES_CONTENT_PATH": str(content_path)}):
            count = _count_posts_published_today("site1")

        assert count == 0


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


class TestSetHugoDraftStatus:
    """Test _set_hugo_draft_status helper function."""

    def test_sets_draft_to_false(self):
        """Test publishing: draft true → false."""
        content = """---
title: "Test Article"
date: 2024-01-01T00:00:00Z
draft: true
---

# Content
"""
        result = _set_hugo_draft_status(content, draft=False)
        assert "draft: false" in result
        assert "draft: true" not in result
        assert result != content

    def test_sets_draft_to_true(self):
        """Test unpublishing: draft false → true."""
        content = """---
title: "Test Article"
date: 2024-01-01T00:00:00Z
draft: false
---

# Content
"""
        result = _set_hugo_draft_status(content, draft=True)
        assert "draft: true" in result
        assert "draft: false" not in result
        assert result != content

    def test_adds_draft_field_if_missing(self):
        """Test adds draft field if not present."""
        content = """---
title: "Test Article"
date: 2024-01-01T00:00:00Z
---

# Content
"""
        result = _set_hugo_draft_status(content, draft=False)
        assert "draft: false" in result
        assert result != content

    def test_returns_unchanged_if_no_frontmatter(self):
        """Test returns original content if no frontmatter."""
        content = """# Plain Markdown

No frontmatter here.
"""
        result = _set_hugo_draft_status(content, draft=False)
        assert result == content

    def test_returns_unchanged_if_already_correct(self):
        """Test optimization: no change if already correct value."""
        content = """---
title: "Test Article"
date: 2024-01-01T00:00:00Z
draft: false
---

# Content
"""
        result = _set_hugo_draft_status(content, draft=False)
        assert result == content


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


class TestCreatePostsHugo:
    """Test create_posts_hugo function."""

    def _setup_markdown_files(self, tmp_path: Path, site_id: str = "site1") -> None:
        """Helper to set up markdown files."""
        markdown_dir = tmp_path / "content" / site_id / "articles" / "markdown"
        markdown_dir.mkdir(parents=True, exist_ok=True)

        # Create markdown files
        for i, slug in enumerate(["article-one", "article-two", "article-three"]):
            (markdown_dir / f"{slug}.md").write_text(
                f"# Article {i+1}\n\nContent here."
            )

    def test_deploys_content_directory_and_builds_site(self, tmp_path):
        """Test deploys markdown directory and builds Hugo site."""
        # Setup
        csv_path = _setup_site_config(tmp_path)
        content_path = tmp_path / "content"
        self._setup_markdown_files(tmp_path)

        # Mock HugoDeployer
        hugo = Mock()

        # Execute
        with patch.dict(
            "os.environ",
            {
                "SITES_CONFIG_PATH": csv_path,
                "SITES_CONTENT_PATH": str(content_path),
            },
        ):
            create_posts_hugo("site1", hugo)

        # Verify deploy_content_directory was called
        assert hugo.deploy_content_directory.call_count == 1
        call_args = hugo.deploy_content_directory.call_args
        assert call_args[0][0] == "example.com"  # domain
        assert "markdown" in str(call_args[0][1])  # markdown directory path

        # Verify build_site was called
        assert hugo.build_site.call_count == 1
        assert hugo.build_site.call_args[0][0] == "example.com"

    def test_handles_missing_markdown_directory(self, tmp_path):
        """Test handles missing markdown directory gracefully."""
        # Setup
        csv_path = _setup_site_config(tmp_path)
        content_path = tmp_path / "content"
        # Don't create markdown directory

        # Mock HugoDeployer
        hugo = Mock()

        # Execute
        with patch.dict(
            "os.environ",
            {
                "SITES_CONFIG_PATH": csv_path,
                "SITES_CONTENT_PATH": str(content_path),
            },
        ):
            create_posts_hugo("site1", hugo)

        # Verify nothing was called
        assert hugo.deploy_content_directory.call_count == 0
        assert hugo.build_site.call_count == 0


class TestPublishPostsHugo:
    """Test publish_posts_hugo function."""

    def _setup_hugo_files(
        self, tmp_path: Path, site_id: str = "site1", with_frontmatter: bool = True
    ) -> None:
        """Helper to set up Hugo generation and markdown files."""
        content_path = tmp_path / "content" / site_id / "articles"
        generation_dir = content_path / "generation"
        markdown_dir = content_path / "markdown"
        generation_dir.mkdir(parents=True, exist_ok=True)
        markdown_dir.mkdir(parents=True, exist_ok=True)

        # Create generation metadata and markdown files
        for i, slug in enumerate(["article-one", "article-two", "article-three"]):
            # Generation metadata
            gen_data = {
                "title": f"Article {i+1}",
                "slug": slug,
            }
            (generation_dir / f"{slug}.json").write_text(json.dumps(gen_data))

            # Markdown file with draft: true frontmatter
            if with_frontmatter:
                content = f"""---
title: "Article {i+1}"
date: 2024-01-01T00:00:00Z
draft: true
slug: "{slug}"
---

# Article {i+1}

Content for article {i+1}.
"""
            else:
                content = f"# Article {i+1}\n\nContent for article {i+1}.\n"

            (markdown_dir / f"{slug}.md").write_text(content)

    def test_publishes_draft_posts(self, tmp_path):
        """Test publishing draft posts by changing draft: true to draft: false."""
        # Setup
        csv_path = _setup_site_config(tmp_path)
        content_path = tmp_path / "content"
        self._setup_hugo_files(tmp_path)

        # Mock Hugo deployer
        hugo = Mock()

        # Execute
        with patch.dict(
            "os.environ",
            {
                "SITES_CONFIG_PATH": csv_path,
                "SITES_CONTENT_PATH": str(content_path),
            },
        ):
            publish_posts_hugo("site1", hugo)

        # Verify all 3 posts were published
        published_dir = content_path / "site1" / "articles" / "published"
        assert (published_dir / "article-one.json").exists()
        assert (published_dir / "article-two.json").exists()
        assert (published_dir / "article-three.json").exists()

        # Verify metadata
        pub_data = json.loads((published_dir / "article-one.json").read_text())
        assert pub_data["status"] == "published"
        assert pub_data["cms"] == "hugo"
        assert "published_at" in pub_data

        # Verify markdown files updated (draft: true → draft: false)
        markdown_dir = content_path / "site1" / "articles" / "markdown"
        content = (markdown_dir / "article-one.md").read_text()
        assert "draft: false" in content
        assert "draft: true" not in content

        # Verify deploy and build were called once
        hugo.deploy_content_directory.assert_called_once()
        hugo.build_site.assert_called_once_with("example.com")

    def test_skips_already_published(self, tmp_path):
        """Test resumable behavior - skips already published posts."""
        # Setup
        csv_path = _setup_site_config(tmp_path)
        content_path = tmp_path / "content"
        self._setup_hugo_files(tmp_path)

        # Create one already published post
        published_dir = content_path / "site1" / "articles" / "published"
        published_dir.mkdir(parents=True, exist_ok=True)

        pub_data_published = {
            "slug": "article-one",
            "status": "published",
            "published_at": "2024-01-01T00:00:00Z",
            "cms": "hugo",
        }
        (published_dir / "article-one.json").write_text(json.dumps(pub_data_published))

        # Mock Hugo deployer
        hugo = Mock()

        # Execute
        with patch.dict(
            "os.environ",
            {
                "SITES_CONFIG_PATH": csv_path,
                "SITES_CONTENT_PATH": str(content_path),
            },
        ):
            publish_posts_hugo("site1", hugo)

        # Verify only 2 new posts were published (article-two and article-three)
        assert (published_dir / "article-two.json").exists()
        assert (published_dir / "article-three.json").exists()

        # Verify article-one was not modified (still has old timestamp)
        pub_data = json.loads((published_dir / "article-one.json").read_text())
        assert pub_data["published_at"] == "2024-01-01T00:00:00Z"

        # Verify deploy and build were still called (2 posts published)
        hugo.deploy_content_directory.assert_called_once()
        hugo.build_site.assert_called_once()

    def test_respects_limit_parameter(self, tmp_path):
        """Test limit parameter restricts number of posts published."""
        # Setup
        csv_path = _setup_site_config(tmp_path)
        content_path = tmp_path / "content"
        self._setup_hugo_files(tmp_path)

        # Mock Hugo deployer
        hugo = Mock()

        # Execute with limit=2
        with patch.dict(
            "os.environ",
            {
                "SITES_CONFIG_PATH": csv_path,
                "SITES_CONTENT_PATH": str(content_path),
            },
        ):
            publish_posts_hugo("site1", hugo, limit=2)

        # Verify only 2 posts published (not all 3)
        published_dir = content_path / "site1" / "articles" / "published"
        assert (published_dir / "article-one.json").exists()
        assert (published_dir / "article-two.json").exists()
        assert not (published_dir / "article-three.json").exists()

        # Verify deploy and build were called
        hugo.deploy_content_directory.assert_called_once()
        hugo.build_site.assert_called_once()
