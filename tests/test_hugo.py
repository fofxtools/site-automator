"""Tests for Hugo deployer."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from site_automator.hugo import HugoDeployer


class TestCheckHugoInstalled:
    """Test check_hugo_installed method."""

    def test_raises_error_when_hugo_not_installed(self):
        """Test that RuntimeError is raised when Hugo is not installed."""
        mock_ssh = Mock()
        mock_ssh.run_command.return_value = ("", 1)

        hugo = HugoDeployer(mock_ssh)

        with pytest.raises(RuntimeError, match="Hugo is not installed"):
            hugo.check_hugo_installed()

    def test_passes_when_hugo_installed(self):
        """Test that no error is raised when Hugo is installed."""
        mock_ssh = Mock()
        mock_ssh.run_command.return_value = ("/usr/local/bin/hugo", 0)

        hugo = HugoDeployer(mock_ssh)
        hugo.check_hugo_installed()  # Should not raise


class TestEnsureSiteInitialized:
    """Test ensure_site_initialized method."""

    def test_validates_domain(self):
        """Test that domain is validated."""
        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)

        with pytest.raises(ValueError, match="Invalid domain"):
            hugo.ensure_site_initialized("invalid/domain")

    def test_skips_if_already_initialized(self):
        """Test that initialization is skipped if hugo.toml exists."""
        mock_ssh = Mock()
        mock_ssh.run_command.return_value = ("", 0)

        hugo = HugoDeployer(mock_ssh)
        hugo.ensure_site_initialized("example.com")

        # Should only check for hugo.toml, not create site
        assert mock_ssh.run_command.call_count == 1

    def test_creates_site_if_missing(self):
        """Test that site is created if hugo.toml doesn't exist."""
        mock_ssh = Mock()
        # First call (test) returns 1, subsequent calls return 0
        mock_ssh.run_command.side_effect = [("", 1), ("", 0), ("", 0)]

        hugo = HugoDeployer(mock_ssh)
        hugo.ensure_site_initialized("example.com")

        # Should check, mkdir, and hugo new site
        assert mock_ssh.run_command.call_count == 3


class TestEnsurePermissions:
    """Test ensure_permissions method."""

    def test_validates_domain(self):
        """Test that domain is validated."""
        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)

        with pytest.raises(ValueError, match="Invalid domain"):
            hugo.ensure_permissions("invalid/domain")

    def test_sets_permissions_with_default_user(self):
        """Test that permissions are set with default caddy user."""
        mock_ssh = Mock()
        mock_ssh.run_command.return_value = ("", 0)

        hugo = HugoDeployer(mock_ssh)
        hugo.ensure_permissions("example.com")

        calls = [call[0][0] for call in mock_ssh.run_command.call_args_list]
        assert any("chown -R caddy:caddy" in c for c in calls)
        assert any("chmod -R 755" in c for c in calls)

    def test_sets_permissions_with_custom_user(self):
        """Test that permissions are set with custom user."""
        mock_ssh = Mock()
        mock_ssh.run_command.return_value = ("", 0)

        hugo = HugoDeployer(mock_ssh)
        hugo.ensure_permissions("example.com", user="www-data")

        calls = [call[0][0] for call in mock_ssh.run_command.call_args_list]
        assert any("chown -R www-data:www-data" in c for c in calls)


class TestEnsureBaseUrl:
    """Test ensure_base_url method."""

    def test_validates_domain(self):
        """Test that domain is validated."""
        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)

        with pytest.raises(ValueError, match="Invalid domain"):
            hugo.ensure_base_url("invalid/domain")

    def test_skips_if_already_correct(self):
        """Test that baseURL update is skipped if already correct."""
        mock_ssh = Mock()
        mock_ssh.run_command.return_value = ("baseURL = 'https://example.com/'", 0)

        hugo = HugoDeployer(mock_ssh)
        hugo.ensure_base_url("example.com")

        # Should only check, not update
        assert mock_ssh.run_command.call_count == 1

    def test_sets_base_url_when_missing(self):
        """Test that baseURL is set when missing or incorrect."""
        mock_ssh = Mock()
        # First call (grep) returns wrong/missing baseURL
        # Subsequent calls (sed commands) succeed
        mock_ssh.run_command.side_effect = [
            ("baseURL = 'https://wrong-domain.com/'", 0),  # grep (wrong baseURL)
            ("", 0),
            ("", 0),
        ]

        hugo = HugoDeployer(mock_ssh)
        hugo.ensure_base_url("example.com")

        # Should check, delete old, insert new
        assert mock_ssh.run_command.call_count == 3
        calls = [call[0][0] for call in mock_ssh.run_command.call_args_list]

        # Verify deletion and insertion
        assert any("sed -i '/^baseURL/d'" in c for c in calls)
        assert any("sed -i \"1ibaseURL = 'https://example.com/'\"" in c for c in calls)


class TestEnsurePublishDir:
    """Test ensure_publish_dir method."""

    def test_validates_domain(self):
        """Test that domain is validated."""
        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)

        with pytest.raises(ValueError, match="Invalid domain"):
            hugo.ensure_publish_dir("invalid/domain")

    def test_skips_if_already_correct(self):
        """Test that publishDir update is skipped if already correct."""
        mock_ssh = Mock()
        mock_ssh.run_command.return_value = ('publishDir = "public"', 0)

        hugo = HugoDeployer(mock_ssh)
        hugo.ensure_publish_dir("example.com")

        # Should only check, not update
        assert mock_ssh.run_command.call_count == 1

    def test_sets_publish_dir_when_missing(self):
        """Test that publishDir is set when missing or incorrect."""
        mock_ssh = Mock()
        # First call (grep) returns wrong/missing publishDir
        # Subsequent calls (sed commands) succeed
        mock_ssh.run_command.side_effect = [
            ('publishDir = "dist"', 0),  # grep (wrong publishDir)
            ("", 0),
            ("", 0),
        ]

        hugo = HugoDeployer(mock_ssh)
        hugo.ensure_publish_dir("example.com")

        # Should check, delete old, insert new
        assert mock_ssh.run_command.call_count == 3
        calls = [call[0][0] for call in mock_ssh.run_command.call_args_list]

        # Verify deletion and insertion
        assert any("sed -i '/^publishDir/d'" in c for c in calls)
        assert any('publishDir = "public"' in c for c in calls)


class TestEnsureRobotsTxt:
    """Test ensure_robots_txt method."""

    def test_validates_domain(self):
        """Test that domain is validated."""
        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)

        with pytest.raises(ValueError, match="Invalid domain"):
            hugo.ensure_robots_txt("invalid/domain")

    def test_creates_robots_txt(self):
        """Test that robots.txt is created with correct content."""
        mock_ssh = Mock()
        mock_ssh.run_command.return_value = ("", 0)

        hugo = HugoDeployer(mock_ssh)
        hugo.ensure_robots_txt("example.com")

        calls = [call[0][0] for call in mock_ssh.run_command.call_args_list]
        assert len(calls) == 1
        assert "User-agent: *" in calls[0]
        assert "Allow: /" in calls[0]
        assert "Sitemap: https://example.com/sitemap.xml" in calls[0]


class TestEnsureThemeInstalled:
    """Test ensure_theme_installed method."""

    def test_validates_domain(self):
        """Test that domain is validated."""
        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)

        with pytest.raises(ValueError, match="Invalid domain"):
            hugo.ensure_theme_installed("invalid/domain")

    def test_skips_if_already_correct(self):
        """Test that theme setup is skipped if already correct."""
        mock_ssh = Mock()
        # Theme dir exists and theme in config with single quotes
        mock_ssh.run_command.side_effect = [
            ("", 0),  # test -d (theme dir exists)
            ("theme = 'ananke'", 0),  # grep (theme in config)
        ]

        hugo = HugoDeployer(mock_ssh)
        hugo.ensure_theme_installed("example.com", theme="ananke")

        # Should check dir and config, then return
        assert mock_ssh.run_command.call_count == 2

    def test_clones_theme_and_adds_to_config(self):
        """Test that theme is cloned and added to config when missing."""
        mock_ssh = Mock()
        # Theme dir doesn't exist, config doesn't have theme
        mock_ssh.run_command.side_effect = [
            ("", 1),  # test -d (theme dir missing)
            ("", 0),  # git clone
            ("", 0),  # grep (no theme in config)
            ("", 0),  # sed delete
            ("", 0),  # echo add
        ]

        hugo = HugoDeployer(mock_ssh)
        hugo.ensure_theme_installed("example.com", theme="ananke")

        calls = [call[0][0] for call in mock_ssh.run_command.call_args_list]

        # Verify git clone
        assert any("git clone" in c and "gohugo-theme-ananke" in c for c in calls)

        # Verify theme added to config
        assert any("echo \"theme = 'ananke'\"" in c for c in calls)

    def test_adds_to_config_when_dir_exists_but_not_configured(self):
        """Test that theme is added to config when dir exists but not configured."""
        mock_ssh = Mock()
        # Theme dir exists but not in config
        mock_ssh.run_command.side_effect = [
            ("", 0),  # test -d (theme dir exists)
            ("", 0),  # grep (no theme in config)
            ("", 0),  # sed delete
            ("", 0),  # echo add
        ]

        hugo = HugoDeployer(mock_ssh)
        hugo.ensure_theme_installed("example.com", theme="ananke")

        calls = [call[0][0] for call in mock_ssh.run_command.call_args_list]

        # Should NOT git clone (dir exists)
        assert not any("git clone" in c for c in calls)

        # Should add to config
        assert any("echo \"theme = 'ananke'\"" in c for c in calls)


class TestEnsureInternalLinksPartial:
    """Test ensure_internal_links_partial method."""

    def test_validates_domain(self):
        """Test that domain is validated."""
        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)

        with pytest.raises(ValueError, match="Invalid domain"):
            hugo.ensure_internal_links_partial("invalid/domain")

    def test_skips_if_already_exists(self):
        """Test that partial creation is skipped if file already exists."""
        mock_ssh = Mock()
        mock_ssh.run_command.return_value = ("", 0)

        hugo = HugoDeployer(mock_ssh)
        hugo.ensure_internal_links_partial("example.com")

        # Should only check for file existence, not create it
        assert mock_ssh.run_command.call_count == 1
        calls = [call[0][0] for call in mock_ssh.run_command.call_args_list]
        assert "test -f" in calls[0]

    def test_creates_partial_with_default_count(self):
        """Test that partial is created with default count of 10."""
        mock_ssh = Mock()
        # First call (test) returns 1, subsequent calls return 0
        mock_ssh.run_command.side_effect = [("", 1), ("", 0), ("", 0)]

        hugo = HugoDeployer(mock_ssh)
        hugo.ensure_internal_links_partial("example.com")

        # Should check, mkdir, and cat
        assert mock_ssh.run_command.call_count == 3

        calls = [call[0][0] for call in mock_ssh.run_command.call_args_list]

        # Verify mkdir was called
        assert any("mkdir -p" in c and "layouts/partials" in c for c in calls)

        # Verify cat command contains the partial content with count=10
        cat_call = [c for c in calls if "cat >" in c][0]
        assert "internal-links.html" in cat_call
        assert "first 10" in cat_call
        assert "Other Articles" in cat_call

    def test_creates_partial_with_custom_count(self):
        """Test that partial is created with custom count."""
        mock_ssh = Mock()
        mock_ssh.run_command.side_effect = [("", 1), ("", 0), ("", 0)]

        hugo = HugoDeployer(mock_ssh)
        hugo.ensure_internal_links_partial("example.com", count=5)

        calls = [call[0][0] for call in mock_ssh.run_command.call_args_list]
        cat_call = [c for c in calls if "cat >" in c][0]

        # Verify custom count is used
        assert "first 5" in cat_call


class TestEnsureSingleLayoutOverride:
    """Test ensure_single_layout_override method."""

    def test_validates_domain(self):
        """Test that domain is validated."""
        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)

        with pytest.raises(ValueError, match="Invalid domain"):
            hugo.ensure_single_layout_override("invalid/domain")

    def test_skips_if_already_exists(self):
        """Test that layout creation is skipped if file already exists."""
        mock_ssh = Mock()
        mock_ssh.run_command.return_value = ("", 0)

        hugo = HugoDeployer(mock_ssh)
        hugo.ensure_single_layout_override("example.com")

        # Should only check for file existence, not create it
        assert mock_ssh.run_command.call_count == 1
        calls = [call[0][0] for call in mock_ssh.run_command.call_args_list]
        assert "test -f" in calls[0]

    def test_creates_layout_override(self):
        """Test that layout override is created with correct content."""
        mock_ssh = Mock()
        # First call (test) returns 1, subsequent calls return 0
        mock_ssh.run_command.side_effect = [("", 1), ("", 0), ("", 0)]

        hugo = HugoDeployer(mock_ssh)
        hugo.ensure_single_layout_override("example.com")

        # Should check, mkdir, and cat
        assert mock_ssh.run_command.call_count == 3

        calls = [call[0][0] for call in mock_ssh.run_command.call_args_list]

        # Verify mkdir was called
        assert any("mkdir -p" in c and "layouts/_default" in c for c in calls)

        # Verify cat command contains the layout content
        cat_call = [c for c in calls if "cat >" in c][0]
        assert "single.html" in cat_call
        assert 'define "main"' in cat_call
        assert "{{ .Title }}" in cat_call
        assert "{{ .Content }}" in cat_call
        assert 'partial "internal-links.html"' in cat_call


class TestDeployContentFile:
    """Test deploy_content_file method."""

    def test_validates_domain(self, tmp_path):
        """Test that domain is validated."""
        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)

        # Create a temporary markdown file
        markdown_file = tmp_path / "test.md"
        markdown_file.write_text("# Test Article")

        with pytest.raises(ValueError, match="Invalid domain"):
            hugo.deploy_content_file("invalid/domain", "test-slug", markdown_file)

    @pytest.mark.parametrize(
        "invalid_slug,reason",
        [
            ("invalid/slug", "contains slash"),
            ("../etc/passwd", "path traversal"),
            ("", "empty string"),
            ("HELLO-WORLD", "uppercase letters"),
            ("hello world", "contains spaces"),
            ("  hello  ", "leading/trailing whitespace"),
            ("Hello-World", "mixed case"),
            ("test_slug", "contains underscore"),
        ],
    )
    def test_validates_slug_rejects_invalid(self, tmp_path, invalid_slug, reason):
        """Test that slug validation rejects invalid slugs."""
        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)

        # Create a temporary markdown file
        markdown_file = tmp_path / "test.md"
        markdown_file.write_text("# Test Article")

        with pytest.raises(ValueError, match="Invalid slug"):
            hugo.deploy_content_file("example.com", invalid_slug, markdown_file)

    @pytest.mark.parametrize(
        "valid_slug",
        [
            "valid-slug",
            "test-article",
            "hello-world-123",
            "a",
            "123",
            "my-post-2024",
        ],
    )
    def test_validates_slug_accepts_valid(self, tmp_path, valid_slug):
        """Test that slug validation accepts valid slugs."""
        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)

        # Create a temporary markdown file
        markdown_file = tmp_path / "test.md"
        markdown_file.write_text("# Test Article")

        # Should not raise
        hugo.deploy_content_file("example.com", valid_slug, markdown_file)

        # Verify upload_file was called
        assert mock_ssh.upload_file.called

    def test_raises_error_if_file_not_found(self):
        """Test that FileNotFoundError is raised if markdown file doesn't exist."""
        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)

        non_existent_file = Path("/tmp/does-not-exist.md")

        with pytest.raises(FileNotFoundError, match="Markdown file not found"):
            hugo.deploy_content_file("example.com", "test-slug", non_existent_file)

    def test_deploys_content_file(self, tmp_path):
        """Test that content file is deployed to Hugo content directory using upload_file."""
        mock_ssh = Mock()

        # Create a temporary markdown file
        markdown_file = tmp_path / "test-article.md"
        markdown_content = "# Test Article\n\nThis is a test article."
        markdown_file.write_text(markdown_content)

        hugo = HugoDeployer(mock_ssh)
        hugo.deploy_content_file("example.com", "test-article", markdown_file)

        # Verify upload_file was called with correct arguments
        mock_ssh.upload_file.assert_called_once_with(
            markdown_file, "/var/www/example.com/content/test-article.md"
        )


class TestDeployContentDirectory:
    """Test deploy_content_directory method."""

    def test_validates_domain(self, tmp_path):
        """Test that domain is validated."""
        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)

        # Create a temporary directory
        content_dir = tmp_path / "content"
        content_dir.mkdir()

        with pytest.raises(ValueError, match="Invalid domain"):
            hugo.deploy_content_directory("invalid/domain", content_dir)

    def test_deploys_content_directory(self, tmp_path):
        """Test that content directory is deployed using upload_directory_rsync."""
        mock_ssh = Mock()

        # Create a temporary directory with markdown files
        content_dir = tmp_path / "content"
        content_dir.mkdir()
        (content_dir / "article1.md").write_text("# Article 1")
        (content_dir / "article2.md").write_text("# Article 2")

        hugo = HugoDeployer(mock_ssh)
        hugo.deploy_content_directory("example.com", content_dir)

        # Verify upload_directory_rsync was called with correct arguments
        mock_ssh.upload_directory_rsync.assert_called_once_with(
            content_dir, "/var/www/example.com/content", delete=False
        )

    def test_deploys_content_directory_with_delete(self, tmp_path):
        """Test that content directory is deployed with delete flag."""
        mock_ssh = Mock()

        # Create a temporary directory
        content_dir = tmp_path / "content"
        content_dir.mkdir()

        hugo = HugoDeployer(mock_ssh)
        hugo.deploy_content_directory("example.com", content_dir, delete=True)

        # Verify upload_directory_rsync was called with delete=True
        mock_ssh.upload_directory_rsync.assert_called_once_with(
            content_dir, "/var/www/example.com/content", delete=True
        )


class TestBuildSite:
    """Test build_site method."""

    def test_validates_domain(self):
        """Test that domain is validated."""
        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)

        with pytest.raises(ValueError, match="Invalid domain"):
            hugo.build_site("invalid/domain")

    def test_builds_site_successfully(self):
        """Test that hugo build runs successfully."""
        mock_ssh = Mock()
        mock_ssh.run_command.return_value = ("", 0)

        hugo = HugoDeployer(mock_ssh)
        hugo.build_site("example.com")

        # Verify hugo command was called
        calls = [call[0][0] for call in mock_ssh.run_command.call_args_list]
        assert len(calls) == 1
        assert "cd /var/www/example.com" in calls[0]
        assert "hugo" in calls[0]

    def test_raises_error_on_build_failure(self):
        """Test that RuntimeError is raised when hugo build fails."""
        mock_ssh = Mock()
        mock_ssh.run_command.return_value = ("", 1)

        hugo = HugoDeployer(mock_ssh)

        with pytest.raises(RuntimeError, match="Hugo build failed"):
            hugo.build_site("example.com")


class TestWipeSite:
    """Test wipe_site method."""

    def test_validates_domain(self):
        """Test that domain is validated."""
        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)

        with pytest.raises(ValueError, match="Invalid domain"):
            hugo.wipe_site("invalid/domain", confirm=True)

    def test_wipe_site_without_confirm_raises(self):
        """Test wipe_site raises ValueError when confirm is not True."""
        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)

        with pytest.raises(ValueError, match="confirm=True"):
            hugo.wipe_site("example.com")

        assert mock_ssh.run_command.call_count == 0

    def test_wipe_site_skips_if_directory_missing(self):
        """Test wipe_site returns early if site directory doesn't exist."""
        mock_ssh = Mock()
        mock_ssh.run_command.return_value = ("missing", 0)

        hugo = HugoDeployer(mock_ssh)
        hugo.wipe_site("example.com", confirm=True)

        # Should only check existence, not attempt delete
        calls = [call[0][0] for call in mock_ssh.run_command.call_args_list]
        assert len(calls) == 1
        assert "test -d /var/www/example.com" in calls[0]

    def test_wipe_site_with_confirm(self):
        """Test wipe_site executes find command (default wipes everything)."""
        mock_ssh = Mock()
        mock_ssh.run_command.return_value = ("exists", 0)

        hugo = HugoDeployer(mock_ssh)
        hugo.wipe_site("example.com", confirm=True)

        calls = [call[0][0] for call in mock_ssh.run_command.call_args_list]
        assert len(calls) == 2  # Check existence + wipe
        # First call: check if directory exists
        assert "test -d /var/www/example.com" in calls[0]
        # Second call: wipe everything in one command
        assert "find /var/www/example.com -mindepth 1 -delete" in calls[1]

    def test_wipe_site_with_exclude_top_level_dir(self):
        """Test wipe_site with top-level directory exclusion."""
        mock_ssh = Mock()
        mock_ssh.run_command.return_value = ("exists", 0)

        hugo = HugoDeployer(mock_ssh)
        hugo.wipe_site("example.com", confirm=True, exclude_dirs=["stats"])

        calls = [call[0][0] for call in mock_ssh.run_command.call_args_list]
        assert len(calls) == 3  # Check existence + two-step deletion

        # First call: check if directory exists
        assert "test -d /var/www/example.com" in calls[0]

        # Second call: Delete files
        assert "find /var/www/example.com -type f" in calls[1]
        assert "! -path '/var/www/example.com/stats'" in calls[1]
        assert "! -path '/var/www/example.com/stats/*'" in calls[1]
        assert "-delete" in calls[1]

        # Third call: Delete empty directories
        assert "find /var/www/example.com -depth -mindepth 1 -type d" in calls[2]
        assert "! -path '/var/www/example.com/stats'" in calls[2]
        assert "! -path '/var/www/example.com/stats/*'" in calls[2]
        assert "-empty -delete" in calls[2]

    def test_wipe_site_with_exclude_nested_path(self):
        """Test wipe_site with nested path exclusion."""
        mock_ssh = Mock()
        mock_ssh.run_command.return_value = ("exists", 0)

        hugo = HugoDeployer(mock_ssh)
        hugo.wipe_site("example.com", confirm=True, exclude_dirs=["public/stats"])

        calls = [call[0][0] for call in mock_ssh.run_command.call_args_list]
        assert len(calls) == 3  # Check existence + two-step deletion

        # First call: check if directory exists
        assert "test -d /var/www/example.com" in calls[0]

        # Second call: Delete files
        assert "find /var/www/example.com -type f" in calls[1]
        assert "! -path '/var/www/example.com/public/stats'" in calls[1]
        assert "! -path '/var/www/example.com/public/stats/*'" in calls[1]
        assert "-delete" in calls[1]

        # Third call: Delete empty directories
        assert "find /var/www/example.com -depth -mindepth 1 -type d" in calls[2]
        assert "! -path '/var/www/example.com/public/stats'" in calls[2]
        assert "! -path '/var/www/example.com/public/stats/*'" in calls[2]
        assert "-empty -delete" in calls[2]

    def test_wipe_site_with_mixed_exclusions(self):
        """Test wipe_site with both top-level and nested path exclusions."""
        mock_ssh = Mock()
        mock_ssh.run_command.return_value = ("exists", 0)

        hugo = HugoDeployer(mock_ssh)
        hugo.wipe_site(
            "example.com",
            confirm=True,
            exclude_dirs=["backups", "public/stats", "themes/custom"],
        )

        calls = [call[0][0] for call in mock_ssh.run_command.call_args_list]
        assert len(calls) == 3  # Check existence + two-step deletion

        # First call: check if directory exists
        assert "test -d /var/www/example.com" in calls[0]

        # Second call: Delete files - check all exclusions are present
        cmd1 = calls[1]
        assert "find /var/www/example.com -type f" in cmd1
        assert "! -path '/var/www/example.com/backups'" in cmd1
        assert "! -path '/var/www/example.com/backups/*'" in cmd1
        assert "! -path '/var/www/example.com/public/stats'" in cmd1
        assert "! -path '/var/www/example.com/public/stats/*'" in cmd1
        assert "! -path '/var/www/example.com/themes/custom'" in cmd1
        assert "! -path '/var/www/example.com/themes/custom/*'" in cmd1
        assert "-delete" in cmd1

        # Third call: Delete empty directories - check all exclusions are present
        cmd2 = calls[2]
        assert "find /var/www/example.com -depth -mindepth 1 -type d" in cmd2
        assert "! -path '/var/www/example.com/backups'" in cmd2
        assert "! -path '/var/www/example.com/backups/*'" in cmd2
        assert "! -path '/var/www/example.com/public/stats'" in cmd2
        assert "! -path '/var/www/example.com/public/stats/*'" in cmd2
        assert "! -path '/var/www/example.com/themes/custom'" in cmd2
        assert "! -path '/var/www/example.com/themes/custom/*'" in cmd2
        assert "-empty -delete" in cmd2


class TestInitialSetup:
    """Test initial_setup method."""

    def test_orchestrates_all_configuration_steps(self):
        """Test initial_setup calls all expected methods with correct parameters."""
        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)

        # Mock all the configuration methods
        with (
            patch.object(hugo, "ensure_base_url") as mock_base_url,
            patch.object(hugo, "ensure_publish_dir") as mock_publish_dir,
            patch.object(hugo, "ensure_theme_installed") as mock_theme,
            patch.object(hugo, "ensure_robots_txt") as mock_robots,
            patch.object(hugo, "ensure_internal_links_partial") as mock_links,
            patch.object(hugo, "ensure_single_layout_override") as mock_layout,
            patch.object(hugo, "ensure_permissions") as mock_perms,
        ):

            # Call initial_setup
            hugo.initial_setup(domain="example.com", theme="ananke")

            # Verify all methods were called with correct parameters
            mock_base_url.assert_called_once_with("example.com")
            mock_publish_dir.assert_called_once_with("example.com")
            mock_theme.assert_called_once_with("example.com", "ananke")
            mock_robots.assert_called_once_with("example.com")
            mock_links.assert_called_once_with("example.com")
            mock_layout.assert_called_once_with("example.com")
            mock_perms.assert_called_once_with("example.com")
