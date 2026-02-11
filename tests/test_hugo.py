"""Tests for Hugo deployer."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from site_automator.hugo import HugoDeployer


class TestInjectTrackingIntoBaseof:
    """Test _inject_tracking_into_baseof method."""

    def test_injects_tracking_before_body_tag(self):
        """Test that tracking partial is injected before </body> tag."""
        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)

        content = """<!DOCTYPE html>
<html>
<head><title>Test</title></head>
<body>
  <h1>Hello</h1>
</body>
</html>"""

        result = hugo._inject_tracking_into_baseof(content)

        assert '{{ partial "pageview-tracking.html" . }}' in result
        assert result.index('{{ partial "pageview-tracking.html" . }}') < result.index(
            "</body>"
        )

    def test_idempotent_when_already_injected(self):
        """Test that injection is skipped if tracking already present."""
        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)

        content = """<!DOCTYPE html>
<html>
<body>
  {{ partial "pageview-tracking.html" . }}
</body>
</html>"""

        result = hugo._inject_tracking_into_baseof(content)

        # Should return unchanged
        assert result == content
        # Should only appear once
        assert result.count("pageview-tracking.html") == 1

    def test_raises_error_when_no_body_tag(self):
        """Test that RuntimeError is raised when </body> tag is missing."""
        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)

        content = """<!DOCTYPE html>
<html>
<head><title>Test</title></head>
</html>"""

        with pytest.raises(RuntimeError, match="missing </body> tag"):
            hugo._inject_tracking_into_baseof(content)


class TestFindThemeBaseof:
    """Test _find_theme_baseof method."""

    def test_finds_baseof_in_layouts_root(self):
        """Test that baseof is found in layouts/ (modern themes)."""
        mock_ssh = Mock()
        # First test succeeds (layouts/baseof.html exists)
        mock_ssh.run_command.return_value = ("", 0)

        hugo = HugoDeployer(mock_ssh)
        result = hugo._find_theme_baseof("/var/www/example.com", "ananke")

        assert result == "/var/www/example.com/themes/ananke/layouts/baseof.html"
        # Should only check first location
        assert mock_ssh.run_command.call_count == 1

    def test_finds_baseof_in_layouts_default(self):
        """Test that baseof is found in layouts/_default/ (legacy themes)."""
        mock_ssh = Mock()
        # First test fails, second succeeds
        mock_ssh.run_command.side_effect = [
            ("", 1),  # layouts/baseof.html doesn't exist
            ("", 0),  # layouts/_default/baseof.html exists
        ]

        hugo = HugoDeployer(mock_ssh)
        result = hugo._find_theme_baseof("/var/www/example.com", "beautifulhugo")

        assert (
            result
            == "/var/www/example.com/themes/beautifulhugo/layouts/_default/baseof.html"
        )
        # Should check both locations
        assert mock_ssh.run_command.call_count == 2

    def test_returns_none_when_no_baseof_found(self):
        """Test that None is returned when baseof doesn't exist."""
        mock_ssh = Mock()
        # Both tests fail
        mock_ssh.run_command.return_value = ("", 1)

        hugo = HugoDeployer(mock_ssh)
        result = hugo._find_theme_baseof("/var/www/example.com", "custom-theme")

        assert result is None
        # Should check both locations
        assert mock_ssh.run_command.call_count == 2


class TestGenerateMinimalBaseofWithTracking:
    """Test _generate_minimal_baseof_with_tracking method."""

    def test_generates_valid_html_structure(self):
        """Test that generated baseof has valid HTML structure."""
        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)

        result = hugo._generate_minimal_baseof_with_tracking()

        assert "<!DOCTYPE html>" in result
        assert "<html" in result
        assert "<head>" in result
        assert "<body>" in result
        assert "</body>" in result
        assert "</html>" in result

    def test_includes_tracking_partial(self):
        """Test that generated baseof includes tracking partial."""
        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)

        result = hugo._generate_minimal_baseof_with_tracking()

        assert '{{ partial "pageview-tracking.html" . }}' in result

    def test_includes_hugo_blocks(self):
        """Test that generated baseof includes Hugo blocks for theme compatibility."""
        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)

        result = hugo._generate_minimal_baseof_with_tracking()

        assert '{{ block "head" . }}{{ end }}' in result
        assert '{{ block "main" . }}{{ end }}' in result


class TestCreateTrackingPartial:
    """Test _create_tracking_partial method."""

    def test_creates_partials_directory(self):
        """Test that partials directory is created."""
        mock_ssh = Mock()
        mock_ssh.run_command.return_value = ("", 0)

        hugo = HugoDeployer(mock_ssh)
        hugo._create_tracking_partial("example.com")

        calls = [call[0][0] for call in mock_ssh.run_command.call_args_list]
        assert any("mkdir -p" in c and "layouts/partials" in c for c in calls)

    def test_uploads_tracking_partial(self):
        """Test that tracking partial is uploaded to correct location."""
        mock_ssh = Mock()
        mock_ssh.run_command.return_value = ("", 0)

        hugo = HugoDeployer(mock_ssh)
        hugo._create_tracking_partial("example.com")

        # Verify upload_file was called
        assert mock_ssh.upload_file.called
        call_args = mock_ssh.upload_file.call_args
        # Second argument should be the remote path
        assert (
            call_args[0][1]
            == "/var/www/example.com/layouts/partials/pageview-tracking.html"
        )

    def test_partial_contains_pixel_and_script(self):
        """Test that partial content includes both pixel and script."""
        mock_ssh = Mock()
        mock_ssh.run_command.return_value = ("", 0)

        # Capture the uploaded content
        uploaded_content = None

        def capture_upload(local_path, remote_path):
            nonlocal uploaded_content
            with open(local_path, "r") as f:
                uploaded_content = f.read()

        mock_ssh.upload_file.side_effect = capture_upload

        hugo = HugoDeployer(mock_ssh)
        hugo._create_tracking_partial("example.com")

        assert uploaded_content is not None
        assert "pixel.php" in uploaded_content
        assert "track_pageview.js" in uploaded_content
        assert "{{ .RelPermalink }}" in uploaded_content


class TestCreateBaseofWithTracking:
    """Test _create_baseof_with_tracking method."""

    def test_creates_layout_directory(self):
        """Test that layouts/_default directory is created."""
        mock_ssh = Mock()
        # Theme baseof doesn't exist in either location
        mock_ssh.run_command.side_effect = [
            ("", 0),  # mkdir
            ("", 1),  # test -f layouts/baseof.html (doesn't exist)
            ("", 1),  # test -f layouts/_default/baseof.html (doesn't exist)
        ]

        hugo = HugoDeployer(mock_ssh)
        hugo._create_baseof_with_tracking("example.com", "ananke")

        calls = [call[0][0] for call in mock_ssh.run_command.call_args_list]
        assert any("mkdir -p" in c and "layouts/_default" in c for c in calls)

    def test_uses_theme_baseof_from_layouts_root(self):
        """Test that theme baseof is copied from layouts/ (modern themes)."""
        mock_ssh = Mock()
        theme_content = """<!DOCTYPE html>
<html>
<body>
  <h1>Theme Content</h1>
</body>
</html>"""
        mock_ssh.run_command.side_effect = [
            ("", 0),  # mkdir
            ("", 0),  # test -f layouts/baseof.html (exists)
            (theme_content, 0),  # cat theme baseof
        ]

        hugo = HugoDeployer(mock_ssh)
        hugo._create_baseof_with_tracking("example.com", "ananke")

        # Verify theme baseof was read from layouts/
        calls = [call[0][0] for call in mock_ssh.run_command.call_args_list]
        assert any(
            'cat "/var/www/example.com/themes/ananke/layouts/baseof.html"' in c
            for c in calls
        )

        # Verify upload_file was called
        assert mock_ssh.upload_file.called

    def test_uses_theme_baseof_from_layouts_default(self):
        """Test that theme baseof is copied from layouts/_default/ (legacy themes)."""
        mock_ssh = Mock()
        theme_content = """<!DOCTYPE html>
<html>
<body>
  <h1>Legacy Theme Content</h1>
</body>
</html>"""
        mock_ssh.run_command.side_effect = [
            ("", 0),  # mkdir
            ("", 1),  # test -f layouts/baseof.html (doesn't exist)
            ("", 0),  # test -f layouts/_default/baseof.html (exists)
            (theme_content, 0),  # cat theme baseof
        ]

        hugo = HugoDeployer(mock_ssh)
        hugo._create_baseof_with_tracking("example.com", "beautifulhugo")

        # Verify theme baseof was read from layouts/_default/
        calls = [call[0][0] for call in mock_ssh.run_command.call_args_list]
        assert any(
            'cat "/var/www/example.com/themes/beautifulhugo/layouts/_default/baseof.html"'
            in c
            for c in calls
        )

        # Verify upload_file was called
        assert mock_ssh.upload_file.called

    def test_creates_minimal_baseof_when_theme_has_none(self):
        """Test that minimal baseof is created when theme doesn't have one."""
        mock_ssh = Mock()
        mock_ssh.run_command.side_effect = [
            ("", 0),  # mkdir
            ("", 1),  # test -f layouts/baseof.html (doesn't exist)
            ("", 1),  # test -f layouts/_default/baseof.html (doesn't exist)
        ]

        # Capture the uploaded content
        uploaded_content = None

        def capture_upload(local_path, remote_path):
            nonlocal uploaded_content
            with open(local_path, "r") as f:
                uploaded_content = f.read()

        mock_ssh.upload_file.side_effect = capture_upload

        hugo = HugoDeployer(mock_ssh)
        hugo._create_baseof_with_tracking("example.com", "custom-theme")

        # Verify minimal baseof was generated
        assert uploaded_content is not None
        assert "<!DOCTYPE html>" in uploaded_content
        assert '{{ block "head" . }}{{ end }}' in uploaded_content
        assert '{{ block "main" . }}{{ end }}' in uploaded_content
        assert '{{ partial "pageview-tracking.html" . }}' in uploaded_content

    def test_uploads_to_site_layouts(self):
        """Test that baseof is uploaded to site layouts directory."""
        mock_ssh = Mock()
        mock_ssh.run_command.side_effect = [
            ("", 0),  # mkdir
            ("", 1),  # test -f layouts/baseof.html (doesn't exist)
            ("", 1),  # test -f layouts/_default/baseof.html (doesn't exist)
        ]

        hugo = HugoDeployer(mock_ssh)
        hugo._create_baseof_with_tracking("example.com", "ananke")

        # Verify upload_file was called with correct remote path
        assert mock_ssh.upload_file.called
        call_args = mock_ssh.upload_file.call_args
        assert call_args[0][1] == "/var/www/example.com/layouts/_default/baseof.html"

    def test_patches_theme_baseof_with_tracking(self):
        """Test that existing theme baseof is patched with tracking."""
        uploaded_content = None

        def capture_upload(local_path, remote_path):
            nonlocal uploaded_content
            with open(local_path, "r") as f:
                uploaded_content = f.read()

        mock_ssh = Mock()
        # Theme baseof exists and contains theme-specific content
        mock_ssh.run_command.side_effect = [
            ("", 0),  # mkdir
            ("", 0),  # test -f (theme baseof exists)
            (
                "<html><head>{{ .Title }}</head><body>Theme content here</body></html>",
                0,
            ),  # cat theme baseof
        ]
        mock_ssh.upload_file.side_effect = capture_upload

        hugo = HugoDeployer(mock_ssh)
        hugo._create_baseof_with_tracking("example.com", "ananke")

        # Verify theme content was preserved AND tracking was injected
        assert uploaded_content is not None
        assert "Theme content here" in uploaded_content
        assert "{{ .Title }}" in uploaded_content
        assert '{{ partial "pageview-tracking.html" . }}' in uploaded_content
        # Verify tracking comes before </body>
        assert uploaded_content.index("pageview-tracking") < uploaded_content.index(
            "</body>"
        )


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

    def test_raises_error_for_unknown_theme(self):
        """Test that RuntimeError is raised for theme not in registry."""
        mock_ssh = Mock()
        # Theme dir doesn't exist (will trigger lookup)
        mock_ssh.run_command.return_value = ("", 1)

        hugo = HugoDeployer(mock_ssh)

        with pytest.raises(
            RuntimeError, match="Theme 'nonexistent' not found in themes.toml"
        ):
            hugo.ensure_theme_installed("example.com", theme="nonexistent")


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
            hugo.ensure_single_layout_override("invalid/domain", "ananke")

    def test_skips_if_already_exists(self):
        """Test that layout creation is skipped if file already exists."""
        mock_ssh = Mock()
        mock_ssh.run_command.return_value = ("", 0)

        hugo = HugoDeployer(mock_ssh)
        hugo.ensure_single_layout_override("example.com", "ananke")

        # Should only check for file existence, not create it
        assert mock_ssh.run_command.call_count == 1
        calls = [call[0][0] for call in mock_ssh.run_command.call_args_list]
        assert "test -f" in calls[0]

    def test_creates_layout_override_from_theme(self):
        """Test that theme's single.html is copied and patched."""
        mock_ssh = Mock()
        theme_single_content = """{{ define "main" }}
<main class="site-main">
  <h1>{{ .Title }}</h1>
  <div class="content">
    {{ .Content }}
  </div>
</main>
{{ end }}"""

        # Capture uploaded content
        uploaded_content = None

        def capture_upload(local_path, remote_path):
            nonlocal uploaded_content
            with open(local_path, "r") as f:
                uploaded_content = f.read()

        mock_ssh.upload_file.side_effect = capture_upload
        mock_ssh.run_command.side_effect = [
            ("", 1),  # test -f site single.html (doesn't exist)
            ("", 0),  # mkdir
            ("", 0),  # test -f baseof layouts/ (exists)
            ("", 0),  # test -f theme single.html (exists)
            (theme_single_content, 0),  # cat theme single.html
        ]

        hugo = HugoDeployer(mock_ssh)
        hugo.ensure_single_layout_override("example.com", "hermit-v2")

        # Verify upload_file was called
        assert mock_ssh.upload_file.called

        # Verify the uploaded content includes internal-links partial
        assert uploaded_content is not None
        assert "internal-links.html" in uploaded_content
        assert "{{ .Title }}" in uploaded_content  # Original theme content preserved

    def test_creates_minimal_layout_when_theme_has_none(self):
        """Test that minimal single.html is created when theme doesn't have one."""
        mock_ssh = Mock()

        # Capture uploaded content
        uploaded_content = None

        def capture_upload(local_path, remote_path):
            nonlocal uploaded_content
            with open(local_path, "r") as f:
                uploaded_content = f.read()

        mock_ssh.upload_file.side_effect = capture_upload
        mock_ssh.run_command.side_effect = [
            ("", 1),  # test -f site single.html (doesn't exist)
            ("", 0),  # mkdir
            ("", 1),  # test -f baseof layouts/ (doesn't exist)
            ("", 1),  # test -f baseof layouts/_default/ (doesn't exist)
        ]

        hugo = HugoDeployer(mock_ssh)
        hugo.ensure_single_layout_override("example.com", "custom-theme")

        # Verify upload_file was called
        assert mock_ssh.upload_file.called

        # Verify minimal content was created
        assert uploaded_content is not None
        assert "internal-links.html" in uploaded_content
        assert '{{- define "main" -}}' in uploaded_content

    def test_injects_before_main_tag_not_footer(self):
        """Test that internal-links partial is injected before </main>, not in footer."""
        mock_ssh = Mock()
        # Hermit-v2 style template with .Content piped through replaceRE
        theme_single_content = """{{ define "main" }}
<main class="site-main">
  <h1>{{ .Title }}</h1>
  <div class="content">
    {{ .Content | replaceRE "pattern" "replacement" | safeHTML }}
  </div>
</main>
{{ end }}

{{ define "footer" }}<footer id="site-footer">{{- partial "footer.html" . -}}</footer>
{{ end }}"""

        # Capture uploaded content
        uploaded_content = None

        def capture_upload(local_path, remote_path):
            nonlocal uploaded_content
            with open(local_path, "r") as f:
                uploaded_content = f.read()

        mock_ssh.upload_file.side_effect = capture_upload
        mock_ssh.run_command.side_effect = [
            ("", 1),  # test -f site single.html (doesn't exist)
            ("", 0),  # mkdir
            ("", 0),  # test -f baseof layouts/ (exists)
            ("", 0),  # test -f theme single.html (exists)
            (theme_single_content, 0),  # cat theme single.html
        ]

        hugo = HugoDeployer(mock_ssh)
        hugo.ensure_single_layout_override("example.com", "hermit-v2")

        # Verify upload_file was called
        assert mock_ssh.upload_file.called
        assert uploaded_content is not None

        # Verify internal-links partial is present
        assert "internal-links.html" in uploaded_content

        # Verify it's injected BEFORE </main> tag, not in footer
        partial_pos = uploaded_content.find("internal-links.html")
        main_close_pos = uploaded_content.find("</main>")
        footer_start_pos = uploaded_content.find('{{ define "footer" }}')

        assert partial_pos != -1, "Partial not found in output"
        assert main_close_pos != -1, "</main> tag not found"
        assert footer_start_pos != -1, "Footer block not found"

        # Critical assertions: partial must be before </main> and before footer
        assert (
            partial_pos < main_close_pos
        ), f"Partial at {partial_pos} should be before </main> at {main_close_pos}"
        assert (
            partial_pos < footer_start_pos
        ), f"Partial at {partial_pos} should be before footer at {footer_start_pos}"

    def test_injects_before_article_tag_ananke(self):
        """Test that internal-links partial is injected before </article> for Ananke theme."""
        mock_ssh = Mock()
        # Ananke style template (no <main>, uses <article>)
        theme_single_content = """{{ define "main" }}
  <article class="flex-l mw7 center">
    <header class="mt4 w-100">
      <h1 class="f1 athelas mt3 mb1">{{- .Title -}}</h1>
    </header>
    <div class="nested-copy-line-height lh-copy serif f4">
      {{- .Content -}}
      {{- partials.Include "tags.html" . -}}
    </div>
  </article>
{{ end }}"""

        uploaded_content = None

        def capture_upload(local_path, remote_path):
            nonlocal uploaded_content
            with open(local_path, "r") as f:
                uploaded_content = f.read()

        mock_ssh.upload_file.side_effect = capture_upload
        mock_ssh.run_command.side_effect = [
            ("", 1),  # test -f site single.html (doesn't exist)
            ("", 0),  # mkdir
            ("", 0),  # test -f baseof layouts/ (exists)
            ("", 0),  # test -f theme single.html (exists)
            (theme_single_content, 0),  # cat theme single.html
        ]

        hugo = HugoDeployer(mock_ssh)
        hugo.ensure_single_layout_override("example.com", "ananke")

        assert uploaded_content is not None
        assert "internal-links.html" in uploaded_content

        # Verify it's injected BEFORE </article> tag
        partial_pos = uploaded_content.find("internal-links.html")
        article_close_pos = uploaded_content.find("</article>")

        assert partial_pos != -1, "Partial not found"
        assert article_close_pos != -1, "</article> not found"
        assert (
            partial_pos < article_close_pos
        ), f"Partial at {partial_pos} should be before </article> at {article_close_pos}"

    def test_injects_before_article_tag_beautifulhugo(self):
        """Test that internal-links partial is injected before </article> for BeautifulHugo theme."""
        mock_ssh = Mock()
        # BeautifulHugo style template (no <main>, uses <article>)
        theme_single_content = """{{ define "main" }}
<div class="container" role="main">
  <div class="row">
    <div class="col-lg-8">
      <article role="main" class="blog-post">
        {{ .Content }}

        {{ if .Params.tags }}
          <div class="blog-tags">
            {{ range .Params.tags }}
              <a href="/tags/{{ . }}/">{{ . }}</a>
            {{ end }}
          </div>
        {{ end }}
      </article>
    </div>
  </div>
</div>
{{ end }}"""

        uploaded_content = None

        def capture_upload(local_path, remote_path):
            nonlocal uploaded_content
            with open(local_path, "r") as f:
                uploaded_content = f.read()

        mock_ssh.upload_file.side_effect = capture_upload
        mock_ssh.run_command.side_effect = [
            ("", 1),  # test -f site single.html (doesn't exist)
            ("", 0),  # mkdir
            ("", 0),  # test -f baseof layouts/ (exists)
            ("", 0),  # test -f theme single.html (exists)
            (theme_single_content, 0),  # cat theme single.html
        ]

        hugo = HugoDeployer(mock_ssh)
        hugo.ensure_single_layout_override("example.com", "beautifulhugo")

        assert uploaded_content is not None
        assert "internal-links.html" in uploaded_content

        # Verify it's injected BEFORE </article> tag
        partial_pos = uploaded_content.find("internal-links.html")
        article_close_pos = uploaded_content.find("</article>")

        # Make sure it's NOT inside the {{ if .Params.tags }} block
        tags_if_start = uploaded_content.find("{{ if .Params.tags }}")
        tags_if_end = uploaded_content.find("{{ end }}", tags_if_start)

        assert partial_pos != -1, "Partial not found"
        assert article_close_pos != -1, "</article> not found"
        assert (
            partial_pos < article_close_pos
        ), f"Partial at {partial_pos} should be before </article> at {article_close_pos}"

        # Critical: Make sure it's NOT inside the tags conditional
        if tags_if_start != -1 and tags_if_end != -1:
            assert not (tags_if_start < partial_pos < tags_if_end), (
                f"Partial should NOT be inside {{ if .Params.tags }} block "
                f"(block: {tags_if_start}-{tags_if_end}, partial: {partial_pos})"
            )


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

    @patch("site_automator.hugo.PageviewTrackingSetup")
    def test_orchestrates_all_configuration_steps(self, mock_tracking_class):
        """Test initial_setup calls all expected methods with correct parameters."""
        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)

        # Setup tracking mock
        mock_tracking = Mock()
        mock_tracking_class.return_value = mock_tracking

        # Mock all the configuration methods
        with (
            patch.object(hugo, "ensure_site_initialized") as mock_init,
            patch.object(hugo, "ensure_base_url") as mock_base_url,
            patch.object(hugo, "ensure_publish_dir") as mock_publish_dir,
            patch.object(hugo, "ensure_theme_installed") as mock_theme,
            patch.object(hugo, "ensure_robots_txt") as mock_robots,
            patch.object(hugo, "ensure_internal_links_partial") as mock_links,
            patch.object(hugo, "ensure_single_layout_override") as mock_layout,
            patch.object(hugo, "setup_tracking") as mock_setup_tracking,
            patch.object(hugo, "ensure_permissions") as mock_perms,
        ):

            # Call initial_setup
            hugo.initial_setup(domain="example.com", theme="ananke")

            # Verify all methods were called with correct parameters
            mock_init.assert_called_once_with("example.com")
            mock_base_url.assert_called_once_with("example.com")
            mock_publish_dir.assert_called_once_with("example.com")
            mock_theme.assert_called_once_with("example.com", "ananke")
            mock_robots.assert_called_once_with("example.com")
            mock_links.assert_called_once_with("example.com")
            mock_layout.assert_called_once_with("example.com", "ananke")
            mock_setup_tracking.assert_called_once_with("example.com", "ananke")
            mock_perms.assert_called_once_with("example.com")

            # Verify PageviewTrackingSetup was called
            mock_tracking_class.assert_called_once_with(mock_ssh)
            mock_tracking.setup_tracking_hugo.assert_called_once_with("example.com")
