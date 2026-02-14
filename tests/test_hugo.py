"""Tests for Hugo deployer."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from site_automator.hugo import HugoDeployer


class TestLoadThemes:
    """Test _load_themes method."""

    def test_loads_themes_from_default_config(self, tmp_path):
        """Test that themes are loaded from default config/themes.toml."""
        # Create a mock themes.toml with new structure
        themes_content = """
[themes.ananke]
url = "https://github.com/theNewDynamic/gohugo-theme-ananke.git"
commit = "a5f3dd61ce53879019049d9a2ba8f049abdfee68"

[themes.hermit-v2]
url = "https://github.com/1bl4z3r/hermit-V2.git"
commit = "1234567890abcdef1234567890abcdef12345678"
"""
        themes_file = tmp_path / "themes.toml"
        themes_file.write_text(themes_content)

        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh, themes_file=themes_file)

        assert len(hugo.themes) == 2
        assert (
            hugo.themes["ananke"]
            == "https://github.com/theNewDynamic/gohugo-theme-ananke.git"
        )
        assert hugo.themes["hermit-v2"] == "https://github.com/1bl4z3r/hermit-V2.git"

        # Verify commits are loaded
        assert len(hugo.theme_commits) == 2
        assert (
            hugo.theme_commits["ananke"] == "a5f3dd61ce53879019049d9a2ba8f049abdfee68"
        )
        assert (
            hugo.theme_commits["hermit-v2"]
            == "1234567890abcdef1234567890abcdef12345678"
        )

    def test_raises_error_when_file_not_found(self):
        """Test that FileNotFoundError is raised when themes file doesn't exist."""
        mock_ssh = Mock()

        with pytest.raises(FileNotFoundError, match="Theme registry not found"):
            HugoDeployer(mock_ssh, themes_file=Path("/nonexistent/themes.toml"))

    def test_raises_error_when_no_themes_defined(self, tmp_path):
        """Test that RuntimeError is raised when no themes are defined."""
        # Create empty themes.toml
        themes_file = tmp_path / "themes.toml"
        themes_file.write_text("[themes]\n")

        mock_ssh = Mock()

        with pytest.raises(RuntimeError, match="No themes defined"):
            HugoDeployer(mock_ssh, themes_file=themes_file)

    def test_raises_error_when_url_missing(self, tmp_path):
        """Test that RuntimeError is raised when theme is missing 'url' field."""
        themes_content = """
[themes.ananke]
commit = "a5f3dd61ce53879019049d9a2ba8f049abdfee68"
"""
        themes_file = tmp_path / "themes.toml"
        themes_file.write_text(themes_content)

        mock_ssh = Mock()

        with pytest.raises(RuntimeError, match="Theme 'ananke' missing 'url' field"):
            HugoDeployer(mock_ssh, themes_file=themes_file)

    def test_raises_error_when_commit_missing(self, tmp_path):
        """Test that RuntimeError is raised when theme is missing 'commit' field."""
        themes_content = """
[themes.ananke]
url = "https://github.com/theNewDynamic/gohugo-theme-ananke.git"
"""
        themes_file = tmp_path / "themes.toml"
        themes_file.write_text(themes_content)

        mock_ssh = Mock()

        with pytest.raises(RuntimeError, match="Theme 'ananke' missing 'commit' field"):
            HugoDeployer(mock_ssh, themes_file=themes_file)

    def test_raises_error_when_theme_not_dict(self, tmp_path):
        """Test that RuntimeError is raised when theme value is not a dict."""
        themes_content = """
[themes]
ananke = "https://github.com/theNewDynamic/gohugo-theme-ananke.git"
"""
        themes_file = tmp_path / "themes.toml"
        themes_file.write_text(themes_content)

        mock_ssh = Mock()

        with pytest.raises(RuntimeError, match="Invalid theme config for 'ananke'"):
            HugoDeployer(mock_ssh, themes_file=themes_file)


class TestCreateTempBundleStructure:
    """Test _create_temp_bundle_structure method."""

    def test_creates_bundle_structure_from_flat_files(self, tmp_path):
        """Test that flat markdown files are converted to page bundles."""
        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)

        # Create flat markdown files
        markdown_dir = tmp_path / "content"
        markdown_dir.mkdir()
        (markdown_dir / "article1.md").write_text("# Article 1")
        (markdown_dir / "article2.md").write_text("# Article 2")

        # Convert to bundle structure
        temp_dir = hugo._create_temp_bundle_structure(markdown_dir)

        try:
            # Verify bundle structure
            assert (temp_dir / "posts").exists()
            assert (temp_dir / "posts" / "article1" / "index.md").exists()
            assert (temp_dir / "posts" / "article2" / "index.md").exists()

            # Verify content is preserved
            assert (
                temp_dir / "posts" / "article1" / "index.md"
            ).read_text() == "# Article 1"
            assert (
                temp_dir / "posts" / "article2" / "index.md"
            ).read_text() == "# Article 2"
        finally:
            # Clean up
            import shutil

            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_raises_error_if_directory_not_found(self):
        """Test that ValueError is raised if markdown directory doesn't exist."""
        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)

        non_existent_dir = Path("/tmp/does-not-exist")

        with pytest.raises(ValueError, match="Markdown directory not found"):
            hugo._create_temp_bundle_structure(non_existent_dir)

    def test_raises_error_if_path_is_not_directory(self, tmp_path):
        """Test that ValueError is raised if path is a file, not a directory."""
        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)

        # Create a file instead of directory
        markdown_file = tmp_path / "test.md"
        markdown_file.write_text("# Test")

        with pytest.raises(ValueError, match="Markdown directory not found"):
            hugo._create_temp_bundle_structure(markdown_file)

    def test_handles_empty_directory(self, tmp_path):
        """Test that empty directory creates empty posts directory."""
        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)

        # Create empty directory
        markdown_dir = tmp_path / "content"
        markdown_dir.mkdir()

        # Convert to bundle structure
        temp_dir = hugo._create_temp_bundle_structure(markdown_dir)

        try:
            # Verify posts directory exists but is empty
            assert (temp_dir / "posts").exists()
            assert list((temp_dir / "posts").iterdir()) == []
        finally:
            # Clean up
            import shutil

            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_ignores_non_markdown_files(self, tmp_path):
        """Test that non-markdown files are ignored."""
        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)

        # Create directory with mixed files
        markdown_dir = tmp_path / "content"
        markdown_dir.mkdir()
        (markdown_dir / "article.md").write_text("# Article")
        (markdown_dir / "image.png").write_text("fake image")
        (markdown_dir / "data.json").write_text("{}")

        # Convert to bundle structure
        temp_dir = hugo._create_temp_bundle_structure(markdown_dir)

        try:
            # Verify only markdown file was converted
            assert (temp_dir / "posts" / "article" / "index.md").exists()
            assert not (temp_dir / "posts" / "image").exists()
            assert not (temp_dir / "posts" / "data").exists()
        finally:
            # Clean up
            import shutil

            shutil.rmtree(temp_dir, ignore_errors=True)


class TestIsHugoContentRendering:
    """Test _is_hugo_content_rendering static method."""

    def test_detects_direct_content_rendering(self):
        """Test that direct .Content rendering is detected."""
        assert HugoDeployer._is_hugo_content_rendering("{{ .Content }}")
        assert HugoDeployer._is_hugo_content_rendering("  {{ .Content }}  ")
        assert HugoDeployer._is_hugo_content_rendering("{{- .Content -}}")

    def test_detects_content_with_pipes(self):
        """Test that .Content with piped functions is detected."""
        assert HugoDeployer._is_hugo_content_rendering("{{ .Content | safeHTML }}")
        assert HugoDeployer._is_hugo_content_rendering(
            '{{ .Content | replaceRE "pattern" "replacement" }}'
        )

    def test_ignores_if_content_conditional(self):
        """Test that {{ if .Content }} is not considered rendering."""
        assert not HugoDeployer._is_hugo_content_rendering("{{ if .Content }}")
        assert not HugoDeployer._is_hugo_content_rendering("{{- if .Content -}}")

    def test_ignores_with_content_block(self):
        """Test that {{ with .Content }} is not considered rendering."""
        assert not HugoDeployer._is_hugo_content_rendering("{{ with .Content }}")
        assert not HugoDeployer._is_hugo_content_rendering("{{- with .Content -}}")

    def test_ignores_lines_without_content(self):
        """Test that lines without .Content return False."""
        assert not HugoDeployer._is_hugo_content_rendering("<div>Hello</div>")
        assert not HugoDeployer._is_hugo_content_rendering("{{ .Title }}")
        assert not HugoDeployer._is_hugo_content_rendering("")

    def test_ignores_content_as_part_of_word(self):
        """Test that .ContentType or similar is not matched."""
        assert not HugoDeployer._is_hugo_content_rendering("{{ .ContentType }}")


class TestFindHugoBlockEnd:
    """Test _find_hugo_block_end static method."""

    def test_finds_simple_block_end(self):
        """Test finding {{ end }} for simple block."""
        lines = [
            "{{ if .Params.tags }}\n",
            "  <div>Tags</div>\n",
            "{{ end }}\n",
        ]
        result = HugoDeployer._find_hugo_block_end(lines, 0)
        assert result == 2

    def test_finds_nested_block_end(self):
        """Test finding {{ end }} with nested blocks."""
        lines = [
            "{{ if .Params.tags }}\n",
            "  {{ range .Params.tags }}\n",
            "    <a>{{ . }}</a>\n",
            "  {{ end }}\n",
            "{{ end }}\n",
        ]
        result = HugoDeployer._find_hugo_block_end(lines, 0)
        assert result == 4  # Outer {{ end }}

    def test_finds_define_block_end(self):
        """Test finding {{ end }} for {{ define }} block."""
        lines = [
            '{{ define "main" }}\n',
            "  <main>\n",
            "    {{ .Content }}\n",
            "  </main>\n",
            "{{ end }}\n",
        ]
        result = HugoDeployer._find_hugo_block_end(lines, 0)
        assert result == 4

    def test_handles_whitespace_variations(self):
        """Test that whitespace variations are handled."""
        lines = [
            "{{- if .Params.tags -}}\n",
            "  <div>Tags</div>\n",
            "{{- end -}}\n",
        ]
        result = HugoDeployer._find_hugo_block_end(lines, 0)
        assert result == 2

    def test_returns_none_when_no_end_found(self):
        """Test that None is returned when {{ end }} is missing."""
        lines = [
            "{{ if .Params.tags }}\n",
            "  <div>Tags</div>\n",
        ]
        result = HugoDeployer._find_hugo_block_end(lines, 0)
        assert result is None


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


class TestFindThemeSingle:
    """Test _find_theme_single method."""

    def test_finds_posts_single_html(self):
        """Test that posts/single.html is found first (hermit-v2 case)."""
        mock_ssh = Mock()
        # First test succeeds (posts/single.html exists)
        mock_ssh.run_command.return_value = ("", 0)

        hugo = HugoDeployer(mock_ssh)
        path, target = hugo._find_theme_single("/var/www/example.com", "hermit-v2")

        assert path == "/var/www/example.com/themes/hermit-v2/layouts/posts/single.html"
        assert target == "posts"
        # Should only check first location
        assert mock_ssh.run_command.call_count == 1

    def test_finds_default_single_html(self):
        """Test that _default/single.html is found when posts/ doesn't exist."""
        mock_ssh = Mock()
        # First test fails, second succeeds
        mock_ssh.run_command.side_effect = [
            ("", 1),  # posts/single.html doesn't exist
            ("", 0),  # _default/single.html exists
        ]

        hugo = HugoDeployer(mock_ssh)
        path, target = hugo._find_theme_single("/var/www/example.com", "ananke")

        assert path == "/var/www/example.com/themes/ananke/layouts/_default/single.html"
        assert target == "_default"
        assert mock_ssh.run_command.call_count == 2

    def test_finds_root_single_html(self):
        """Test that root single.html is found as fallback."""
        mock_ssh = Mock()
        # First two fail, third succeeds
        mock_ssh.run_command.side_effect = [
            ("", 1),  # posts/single.html doesn't exist
            ("", 1),  # _default/single.html doesn't exist
            ("", 0),  # single.html exists
        ]

        hugo = HugoDeployer(mock_ssh)
        path, target = hugo._find_theme_single("/var/www/example.com", "minimal")

        assert path == "/var/www/example.com/themes/minimal/layouts/single.html"
        assert target == "_default"
        assert mock_ssh.run_command.call_count == 3

    def test_returns_none_when_no_single_found(self):
        """Test that None is returned when no single.html exists."""
        mock_ssh = Mock()
        # All tests fail
        mock_ssh.run_command.return_value = ("", 1)

        hugo = HugoDeployer(mock_ssh)
        path, target = hugo._find_theme_single("/var/www/example.com", "custom-theme")

        assert path is None
        assert target == "_default"
        # Should check all three locations
        assert mock_ssh.run_command.call_count == 3


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


class TestSetupTracking:
    """Test setup_tracking method."""

    def test_calls_both_setup_methods(self):
        """Test that setup_tracking calls both _create_tracking_partial and _create_baseof_with_tracking."""
        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)

        with (
            patch.object(hugo, "_create_tracking_partial") as mock_create_partial,
            patch.object(hugo, "_create_baseof_with_tracking") as mock_create_baseof,
        ):
            hugo.setup_tracking("example.com", "ananke")

            mock_create_partial.assert_called_once_with("example.com")
            mock_create_baseof.assert_called_once_with("example.com", "ananke")


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


class TestWriteHugoConfig:
    """Test write_hugo_config method."""

    def test_validates_domain(self):
        """Test that domain is validated."""
        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)

        with pytest.raises(ValueError, match="Invalid domain"):
            hugo.write_hugo_config("invalid/domain", "ananke", "Test Site")

    def test_writes_complete_config(self, tmp_path):
        """Test that complete hugo.toml is written with all required fields."""
        mock_ssh = Mock()

        # Capture uploaded content
        uploaded_content = None

        def capture_upload(local_path, remote_path):
            nonlocal uploaded_content
            with open(local_path, "r") as f:
                uploaded_content = f.read()

        mock_ssh.upload_file.side_effect = capture_upload

        hugo = HugoDeployer(mock_ssh)
        hugo.write_hugo_config("example.com", "ananke", "My Test Site")

        # Verify upload_file was called
        assert mock_ssh.upload_file.called
        call_args = mock_ssh.upload_file.call_args
        assert call_args[0][1] == "/var/www/example.com/hugo.toml"

        # Verify content has all required fields
        assert uploaded_content is not None
        assert "baseURL = 'https://example.com/'" in uploaded_content
        assert "languageCode = 'en-us'" in uploaded_content
        assert "title = 'My Test Site'" in uploaded_content
        assert "publishDir = 'public'" in uploaded_content
        assert "theme = 'ananke'" in uploaded_content
        assert "[permalinks]" in uploaded_content
        assert 'posts = "/:slug/"' in uploaded_content

    def test_overwrites_existing_config(self):
        """Test that config is always overwritten (no checking)."""
        mock_ssh = Mock()

        hugo = HugoDeployer(mock_ssh)
        hugo.write_hugo_config("example.com", "hermit-v2", "Another Site")

        # Should only call upload_file, no grep/sed commands
        assert mock_ssh.upload_file.called
        # run_command should not be called (no checking)
        assert not mock_ssh.run_command.called


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

    def test_skips_if_theme_already_installed(self):
        """Test that theme installation is skipped if directory already exists."""
        mock_ssh = Mock()
        # Theme dir exists
        mock_ssh.run_command.return_value = ("", 0)  # test -d (theme dir exists)

        hugo = HugoDeployer(mock_ssh)
        hugo.ensure_theme_installed("example.com", theme="ananke")

        # Should only check dir, then return (no git clone, no config manipulation)
        assert mock_ssh.run_command.call_count == 1
        calls = [call[0][0] for call in mock_ssh.run_command.call_args_list]
        assert "test -d" in calls[0]

    def test_clones_theme_and_checks_out_commit(self):
        """Test that theme is cloned and specific commit is checked out."""
        mock_ssh = Mock()
        # Theme dir doesn't exist
        mock_ssh.run_command.side_effect = [
            ("", 1),  # test -d (theme dir missing)
            ("", 0),  # git clone
            ("", 0),  # git checkout
        ]

        hugo = HugoDeployer(mock_ssh)
        hugo.ensure_theme_installed("example.com", theme="ananke")

        calls = [call[0][0] for call in mock_ssh.run_command.call_args_list]

        # Verify git clone was called
        assert any("git clone" in c and "gohugo-theme-ananke" in c for c in calls)

        # Verify git checkout was called with commit hash
        assert any(
            "git checkout" in c and hugo.theme_commits["ananke"] in c for c in calls
        )

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


class TestUploadTheme:
    """Test upload_theme method."""

    def test_validates_domain(self):
        """Test that domain is validated."""
        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)

        with pytest.raises(ValueError, match="Invalid domain"):
            hugo.upload_theme("invalid/domain", "ananke")

    def test_raises_error_if_theme_not_in_storage(self, tmp_path):
        """Test that FileNotFoundError is raised if theme not found in storage."""
        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)

        with pytest.raises(FileNotFoundError, match="Theme not found in storage"):
            hugo.upload_theme("example.com", "nonexistent-theme")

    @patch("site_automator.hugo.THEME_STORAGE_DIR")
    def test_uploads_theme_directory(self, mock_storage_dir, tmp_path):
        """Test that theme directory is uploaded via rsync."""
        # Create fake theme directory
        theme_dir = tmp_path / "ananke"
        theme_dir.mkdir()
        (theme_dir / "theme.toml").write_text("name = 'ananke'")

        mock_storage_dir.__truediv__ = lambda self, x: theme_dir

        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)
        hugo.upload_theme("example.com", "ananke")

        # Verify mkdir was called
        calls = [call[0][0] for call in mock_ssh.run_command.call_args_list]
        assert any("mkdir -p /var/www/example.com/themes" in c for c in calls)

        # Verify upload_directory_rsync was called
        mock_ssh.upload_directory_rsync.assert_called_once()
        args = mock_ssh.upload_directory_rsync.call_args[0]
        assert str(args[0]) == str(theme_dir)
        assert args[1] == "/var/www/example.com/themes/ananke"


class TestApplyThemeOverrides:
    """Test apply_theme_overrides method."""

    def test_validates_domain(self):
        """Test that domain is validated."""
        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)

        with pytest.raises(ValueError, match="Invalid domain"):
            hugo.apply_theme_overrides("invalid/domain", "ananke")

    @patch("site_automator.hugo.THEME_RESOURCES_DIR")
    def test_skips_if_no_overrides_exist(self, mock_resources_dir, tmp_path):
        """Test that method returns early if no overrides exist for theme."""
        # Point to non-existent directory
        nonexistent = tmp_path / "nonexistent"
        mock_resources_dir.__truediv__ = lambda self, x: nonexistent

        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)
        hugo.apply_theme_overrides("example.com", "ananke")

        # Should not call upload_directory_rsync
        mock_ssh.upload_directory_rsync.assert_not_called()

    @patch("site_automator.hugo.THEME_RESOURCES_DIR")
    def test_uploads_overrides_to_site_root(self, mock_resources_dir, tmp_path):
        """Test that overrides are uploaded to site root (not layouts/)."""
        # Create fake overrides directory with layouts/ subdirectory
        overrides_dir = tmp_path / "ananke"
        layouts_dir = overrides_dir / "layouts"
        layouts_dir.mkdir(parents=True)
        (layouts_dir / "baseof.html").write_text("<html></html>")

        mock_resources_dir.__truediv__ = lambda self, x: overrides_dir

        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)
        hugo.apply_theme_overrides("example.com", "ananke")

        # Verify upload_directory_rsync was called with site root
        mock_ssh.upload_directory_rsync.assert_called_once()
        args = mock_ssh.upload_directory_rsync.call_args[0]
        assert str(args[0]) == str(overrides_dir)
        assert args[1] == "/var/www/example.com"


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
        # First call checks if override exists (returns 0 = exists)
        mock_ssh.run_command.return_value = ("", 0)

        hugo = HugoDeployer(mock_ssh)
        hugo.ensure_single_layout_override("example.com", "ananke")

        # Should check for posts/single.html, _default/single.html, single.html
        # then check if site override exists (which returns 0 = exists)
        # So it should stop after finding the override exists
        assert mock_ssh.run_command.call_count >= 1
        calls = [call[0][0] for call in mock_ssh.run_command.call_args_list]
        # First few calls are finding theme template, last call checks site override
        assert any("test -f" in call for call in calls)

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
            ("", 0),  # test -f theme posts/single.html (exists - hermit-v2 has this!)
            ("", 1),  # test -f site posts/single.html (doesn't exist yet)
            ("", 0),  # mkdir -p layouts/posts
            (theme_single_content, 0),  # cat theme posts/single.html
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
            ("", 1),  # test -f theme posts/single.html (doesn't exist)
            ("", 1),  # test -f theme _default/single.html (doesn't exist)
            ("", 1),  # test -f theme single.html (doesn't exist)
            ("", 1),  # test -f site _default/single.html (doesn't exist)
            ("", 0),  # mkdir -p layouts/_default
        ]

        hugo = HugoDeployer(mock_ssh)
        hugo.ensure_single_layout_override("example.com", "custom-theme")

        # Verify upload_file was called
        assert mock_ssh.upload_file.called

        # Verify minimal content was created
        assert uploaded_content is not None
        assert "internal-links.html" in uploaded_content
        assert '{{- define "main" -}}' in uploaded_content

    def test_injects_after_content_rendering(self):
        """Test that internal-links partial is injected after .Content rendering (PASS 1)."""
        mock_ssh = Mock()
        # Template with direct .Content rendering
        theme_single_content = """{{ define "main" }}
<main class="site-main">
  <h1>{{ .Title }}</h1>
  <div class="content">
    {{ .Content }}
  </div>
  <div class="comments">Comments here</div>
</main>
{{ end }}"""

        uploaded_content = None

        def capture_upload(local_path, remote_path):
            nonlocal uploaded_content
            with open(local_path, "r") as f:
                uploaded_content = f.read()

        mock_ssh.upload_file.side_effect = capture_upload
        mock_ssh.run_command.side_effect = [
            ("", 0),  # test -f theme posts/single.html (exists)
            ("", 1),  # test -f site posts/single.html (doesn't exist)
            ("", 0),  # mkdir -p layouts/posts
            (theme_single_content, 0),  # cat theme posts/single.html
        ]

        hugo = HugoDeployer(mock_ssh)
        hugo.ensure_single_layout_override("example.com", "hermit-v2")

        assert uploaded_content is not None
        assert "internal-links.html" in uploaded_content

        # Critical: partial must be AFTER .Content but BEFORE comments
        content_pos = uploaded_content.find("{{ .Content }}")
        partial_pos = uploaded_content.find("internal-links.html")
        comments_pos = uploaded_content.find("Comments here")

        assert content_pos != -1, ".Content not found"
        assert partial_pos != -1, "Partial not found"
        assert comments_pos != -1, "Comments not found"

        assert (
            content_pos < partial_pos
        ), f"Partial at {partial_pos} should be AFTER .Content at {content_pos}"
        assert (
            partial_pos < comments_pos
        ), f"Partial at {partial_pos} should be BEFORE comments at {comments_pos}"

    def test_injects_after_all_content_occurrences(self):
        """Test that partial is injected after ALL .Content occurrences (hermit-v2 case)."""
        mock_ssh = Mock()
        # Template with multiple .Content in different conditional branches
        # This simulates hermit-v2's legacy vs modern layout structure
        theme_single_content = """{{ define "main" }}
<article>
  {{ if .Site.Params.legacyLayout }}
    <div class="legacy-content">
      {{ .Content }}
    </div>
  {{ else }}
    <div class="modern-content">
      {{ .Content }}
    </div>
  {{ end }}
  <footer>Article footer</footer>
</article>
{{ end }}"""

        uploaded_content = None

        def capture_upload(local_path, remote_path):
            nonlocal uploaded_content
            with open(local_path, "r") as f:
                uploaded_content = f.read()

        mock_ssh.upload_file.side_effect = capture_upload
        mock_ssh.run_command.side_effect = [
            ("", 0),  # test -f theme posts/single.html (exists)
            ("", 1),  # test -f site posts/single.html (doesn't exist)
            ("", 0),  # mkdir -p layouts/posts
            (theme_single_content, 0),  # cat theme posts/single.html
        ]

        hugo = HugoDeployer(mock_ssh)
        hugo.ensure_single_layout_override("example.com", "hermit-v2")

        assert uploaded_content is not None
        assert "internal-links.html" in uploaded_content

        # Critical: partial must be injected AFTER BOTH .Content occurrences
        # Count occurrences of internal-links partial
        partial_count = uploaded_content.count("internal-links.html")
        content_count = uploaded_content.count("{{ .Content }}")

        assert (
            content_count == 2
        ), f"Expected 2 .Content occurrences, found {content_count}"
        assert (
            partial_count == 2
        ), f"Expected 2 partial injections, found {partial_count}"

        # Verify each .Content has a partial after it
        lines = uploaded_content.splitlines()
        content_line_indices = [
            i for i, line in enumerate(lines) if "{{ .Content }}" in line
        ]
        partial_line_indices = [
            i for i, line in enumerate(lines) if "internal-links.html" in line
        ]

        assert len(content_line_indices) == 2, "Should have 2 .Content lines"
        assert len(partial_line_indices) == 2, "Should have 2 partial lines"

        # Each partial should come after its corresponding .Content
        for content_idx, partial_idx in zip(content_line_indices, partial_line_indices):
            assert (
                partial_idx > content_idx
            ), f"Partial at line {partial_idx} should be AFTER .Content at line {content_idx}"

    def test_injects_after_with_content_block(self):
        """Test that internal-links partial is injected after {{ with .Content }} block (PASS 2)."""
        mock_ssh = Mock()
        # Template with {{ with .Content }} wrapper
        theme_single_content = """{{ define "main" }}
  <article class="post">
    <h1>{{ .Title }}</h1>
    {{ with .Content }}
      <div class="content">{{ . }}</div>
    {{ end }}
    <div class="sidebar">Sidebar here</div>
  </article>
{{ end }}"""

        uploaded_content = None

        def capture_upload(local_path, remote_path):
            nonlocal uploaded_content
            with open(local_path, "r") as f:
                uploaded_content = f.read()

        mock_ssh.upload_file.side_effect = capture_upload
        mock_ssh.run_command.side_effect = [
            ("", 1),  # test -f theme posts/single.html (doesn't exist)
            ("", 0),  # test -f theme _default/single.html (exists)
            ("", 1),  # test -f site _default/single.html (doesn't exist)
            ("", 0),  # mkdir -p layouts/_default
            (theme_single_content, 0),  # cat theme _default/single.html
        ]

        hugo = HugoDeployer(mock_ssh)
        hugo.ensure_single_layout_override("example.com", "terminal")

        assert uploaded_content is not None
        assert "internal-links.html" in uploaded_content

        # Critical: partial must be AFTER {{ with .Content }} block but BEFORE sidebar
        with_start = uploaded_content.find("{{ with .Content }}")
        with_end = uploaded_content.find("{{ end }}", with_start)
        partial_pos = uploaded_content.find("internal-links.html")
        sidebar_pos = uploaded_content.find("Sidebar here")

        assert with_start != -1, "{{ with .Content }} not found"
        assert with_end != -1, "{{ end }} not found"
        assert partial_pos != -1, "Partial not found"
        assert sidebar_pos != -1, "Sidebar not found"

        assert (
            with_end < partial_pos
        ), f"Partial at {partial_pos} should be AFTER {{ with .Content }} block end at {with_end}"
        assert (
            partial_pos < sidebar_pos
        ), f"Partial at {partial_pos} should be BEFORE sidebar at {sidebar_pos}"

    def test_injects_after_content_not_inside_conditionals(self):
        """Test that partial is injected after .Content, not inside conditional blocks."""
        mock_ssh = Mock()
        # Template with .Content followed by conditional block
        theme_single_content = """{{ define "main" }}
<div class="container">
  <article class="blog-post">
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
{{ end }}"""

        uploaded_content = None

        def capture_upload(local_path, remote_path):
            nonlocal uploaded_content
            with open(local_path, "r") as f:
                uploaded_content = f.read()

        mock_ssh.upload_file.side_effect = capture_upload
        mock_ssh.run_command.side_effect = [
            ("", 1),  # test -f theme posts/single.html (doesn't exist)
            ("", 0),  # test -f theme _default/single.html (exists)
            ("", 1),  # test -f site _default/single.html (doesn't exist)
            ("", 0),  # mkdir -p layouts/_default
            (theme_single_content, 0),  # cat theme _default/single.html
        ]

        hugo = HugoDeployer(mock_ssh)
        hugo.ensure_single_layout_override("example.com", "beautifulhugo")

        assert uploaded_content is not None
        assert "internal-links.html" in uploaded_content

        # Critical: partial must be AFTER .Content but NOT inside {{ if .Params.tags }}
        content_pos = uploaded_content.find("{{ .Content }}")
        partial_pos = uploaded_content.find("internal-links.html")
        tags_if_start = uploaded_content.find("{{ if .Params.tags }}")
        tags_if_end = uploaded_content.find("{{ end }}", tags_if_start)

        assert content_pos != -1, ".Content not found"
        assert partial_pos != -1, "Partial not found"
        assert tags_if_start != -1, "{{ if .Params.tags }} not found"

        assert (
            content_pos < partial_pos
        ), f"Partial at {partial_pos} should be AFTER .Content at {content_pos}"

        # Critical: Make sure it's NOT inside the tags conditional
        assert not (tags_if_start < partial_pos < tags_if_end), (
            f"Partial should NOT be inside {{ if .Params.tags }} block "
            f"(block: {tags_if_start}-{tags_if_end}, partial: {partial_pos})"
        )

    def test_structural_fallback_when_no_content_tag(self):
        """Test structural fallback (PASS 3) when .Content is not directly rendered."""
        mock_ssh = Mock()
        # Template without direct .Content rendering (uses custom partial)
        theme_single_content = """{{ define "main" }}
<main class="site-main">
  <h1>{{ .Title }}</h1>
  {{ partial "render-content.html" . }}
  <div class="footer-nav">Navigation</div>
</main>
{{ end }}"""

        uploaded_content = None

        def capture_upload(local_path, remote_path):
            nonlocal uploaded_content
            with open(local_path, "r") as f:
                uploaded_content = f.read()

        mock_ssh.upload_file.side_effect = capture_upload
        mock_ssh.run_command.side_effect = [
            ("", 1),  # test -f theme posts/single.html (doesn't exist)
            ("", 1),  # test -f theme _default/single.html (doesn't exist)
            ("", 0),  # test -f theme single.html (exists)
            ("", 1),  # test -f site _default/single.html (doesn't exist)
            ("", 0),  # mkdir -p layouts/_default
            (theme_single_content, 0),  # cat theme single.html
        ]

        hugo = HugoDeployer(mock_ssh)
        hugo.ensure_single_layout_override("example.com", "custom-theme")

        assert uploaded_content is not None
        assert "internal-links.html" in uploaded_content

        # Should fall back to injecting before </main>
        partial_pos = uploaded_content.find("internal-links.html")
        main_close_pos = uploaded_content.find("</main>")

        assert partial_pos != -1, "Partial not found"
        assert main_close_pos != -1, "</main> not found"
        assert (
            partial_pos < main_close_pos
        ), f"Partial at {partial_pos} should be before </main> at {main_close_pos}"


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

        # Verify upload_directory_rsync was called
        assert mock_ssh.upload_directory_rsync.called

    def test_raises_error_if_file_not_found(self):
        """Test that FileNotFoundError is raised if markdown file doesn't exist."""
        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)

        non_existent_file = Path("/tmp/does-not-exist.md")

        with pytest.raises(FileNotFoundError, match="Markdown file not found"):
            hugo.deploy_content_file("example.com", "test-slug", non_existent_file)

    def test_deploys_content_file_as_page_bundle(self, tmp_path):
        """Test that content file is deployed as page bundle (posts/slug/index.md)."""
        mock_ssh = Mock()

        # Create a temporary markdown file
        markdown_file = tmp_path / "test-article.md"
        markdown_content = "# Test Article\n\nThis is a test article."
        markdown_file.write_text(markdown_content)

        # Capture temp directory before it's cleaned up
        captured_temp_dir = None

        def capture_upload_call(temp_dir, remote_dir):
            nonlocal captured_temp_dir
            captured_temp_dir = Path(temp_dir)
            # Verify bundle structure exists during the call
            assert (captured_temp_dir / "posts" / "test-article" / "index.md").exists()
            assert (
                captured_temp_dir / "posts" / "test-article" / "index.md"
            ).read_text() == markdown_content

        mock_ssh.upload_directory_rsync.side_effect = capture_upload_call

        hugo = HugoDeployer(mock_ssh)
        hugo.deploy_content_file("example.com", "test-article", markdown_file)

        # Verify upload_directory_rsync was called
        assert mock_ssh.upload_directory_rsync.called
        call_args = mock_ssh.upload_directory_rsync.call_args

        # Verify remote directory is correct
        remote_dir = call_args[0][1]
        assert remote_dir == "/var/www/example.com/content"


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

    def test_deploys_content_directory_as_page_bundles(self, tmp_path):
        """Test that flat markdown files are converted to page bundles."""
        mock_ssh = Mock()

        # Create a temporary directory with flat markdown files
        content_dir = tmp_path / "content"
        content_dir.mkdir()
        (content_dir / "article1.md").write_text("# Article 1")
        (content_dir / "article2.md").write_text("# Article 2")

        # Capture temp directory before it's cleaned up
        def capture_upload_call(temp_dir, remote_dir, delete=False):
            temp_path = Path(temp_dir)
            # Verify bundle structure exists during the call
            assert (temp_path / "posts" / "article1" / "index.md").exists()
            assert (temp_path / "posts" / "article2" / "index.md").exists()
            assert (
                temp_path / "posts" / "article1" / "index.md"
            ).read_text() == "# Article 1"
            assert (
                temp_path / "posts" / "article2" / "index.md"
            ).read_text() == "# Article 2"

        mock_ssh.upload_directory_rsync.side_effect = capture_upload_call

        hugo = HugoDeployer(mock_ssh)
        hugo.deploy_content_directory("example.com", content_dir)

        # Verify upload_directory_rsync was called
        assert mock_ssh.upload_directory_rsync.called
        call_args = mock_ssh.upload_directory_rsync.call_args

        # Verify remote directory and delete flag
        remote_dir = call_args[0][1]
        assert remote_dir == "/var/www/example.com/content"
        assert call_args[1]["delete"] is False

    def test_deploys_content_directory_with_delete(self, tmp_path):
        """Test that content directory is deployed with delete flag."""
        mock_ssh = Mock()

        # Create a temporary directory with markdown files
        content_dir = tmp_path / "content"
        content_dir.mkdir()
        (content_dir / "article.md").write_text("# Article")

        hugo = HugoDeployer(mock_ssh)
        hugo.deploy_content_directory("example.com", content_dir, delete=True)

        # Verify upload_directory_rsync was called with delete=True
        assert mock_ssh.upload_directory_rsync.called
        call_args = mock_ssh.upload_directory_rsync.call_args

        remote_dir = call_args[0][1]
        assert remote_dir == "/var/www/example.com/content"
        assert call_args[1]["delete"] is True


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

    @patch("site_automator.hugo.load_site_config_by_domain")
    @patch("site_automator.hugo.PageviewTrackingSetup")
    def test_orchestrates_all_configuration_steps(
        self, mock_tracking_class, mock_load_config
    ):
        """Test initial_setup calls all expected methods with correct parameters."""
        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)

        # Mock site config
        mock_load_config.return_value = {"site_title": "Test Site"}

        # Setup tracking mock
        mock_tracking = Mock()
        mock_tracking_class.return_value = mock_tracking

        # Mock all the configuration methods
        with (
            patch.object(hugo, "ensure_site_initialized") as mock_init,
            patch.object(hugo, "upload_theme") as mock_upload_theme,
            patch.object(hugo, "apply_theme_overrides") as mock_apply_overrides,
            patch.object(hugo, "write_hugo_config") as mock_write_config,
            patch.object(hugo, "ensure_robots_txt") as mock_robots,
            patch.object(hugo, "ensure_internal_links_partial") as mock_links,
            patch.object(hugo, "_create_tracking_partial") as mock_tracking_partial,
            patch.object(hugo, "ensure_permissions") as mock_perms,
        ):

            # Call initial_setup
            hugo.initial_setup(domain="example.com", theme="ananke")

            # Verify all methods were called with correct parameters
            mock_load_config.assert_called_once_with("example.com")
            mock_init.assert_called_once_with("example.com")
            mock_upload_theme.assert_called_once_with("example.com", "ananke")
            mock_apply_overrides.assert_called_once_with("example.com", "ananke")
            mock_write_config.assert_called_once_with(
                "example.com", "ananke", "Test Site"
            )
            mock_robots.assert_called_once_with("example.com")
            mock_links.assert_called_once_with("example.com")
            mock_tracking_partial.assert_called_once_with("example.com")
            mock_perms.assert_called_once_with("example.com")

            # Verify PageviewTrackingSetup was called
            mock_tracking_class.assert_called_once_with(mock_ssh)
            mock_tracking.setup_tracking_hugo.assert_called_once_with("example.com")


class TestSymlinkSharedImage:
    """Test symlink_shared_image method."""

    def test_validates_domain(self):
        """Test that domain is validated."""
        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)

        with pytest.raises(ValueError, match="Invalid domain"):
            hugo.symlink_shared_image("invalid/domain", "test.jpg")

    def test_creates_symlink_with_default_shared_path(self, monkeypatch):
        """Test that symlink is created with default SHARED_IMAGES_PATH."""
        # Ensure env var is not set to force default value
        monkeypatch.delenv("SHARED_IMAGES_PATH", raising=False)

        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)

        hugo.symlink_shared_image("example.com", "cover.jpg")

        # Verify mkdir was called
        calls = [call[0][0] for call in mock_ssh.run_command.call_args_list]
        assert any('mkdir -p "/var/www/example.com/static/images"' in c for c in calls)

        # Verify symlink was created with default path
        assert any(
            'ln -sfn "/var/www/shared/images/cover.jpg" "/var/www/example.com/static/images/cover.jpg"'
            in c
            for c in calls
        )

    def test_creates_symlink_with_custom_shared_path(self, monkeypatch):
        """Test that symlink is created with custom SHARED_IMAGES_PATH from env."""
        monkeypatch.setenv("SHARED_IMAGES_PATH", "/custom/images")
        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)

        hugo.symlink_shared_image("example.com", "photo.jpg")

        # Verify symlink uses custom path
        calls = [call[0][0] for call in mock_ssh.run_command.call_args_list]
        assert any(
            'ln -sfn "/custom/images/photo.jpg" "/var/www/example.com/static/images/photo.jpg"'
            in c
            for c in calls
        )


class TestSetFeaturedImageLocal:
    """Test set_featured_image_local method."""

    def test_validates_slug(self, tmp_path):
        """Test that slug is validated."""
        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)

        with pytest.raises(ValueError, match="Invalid slug"):
            hugo.set_featured_image_local(
                "test_site", "Invalid/Slug", "ananke", "/images/test.jpg"
            )

    def test_raises_error_when_markdown_not_found(self, tmp_path, monkeypatch):
        """Test that FileNotFoundError is raised when markdown file doesn't exist."""
        monkeypatch.setenv("SITES_CONTENT_PATH", str(tmp_path))
        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)

        with pytest.raises(FileNotFoundError, match="Markdown file not found"):
            hugo.set_featured_image_local(
                "test_site", "test-slug", "ananke", "/images/test.jpg"
            )

    def test_raises_when_theme_not_in_map(self, tmp_path, monkeypatch):
        """Test that method raises RuntimeError when theme is not in THEME_FEATURED_IMAGE_MAP."""
        # Create markdown file
        content_dir = tmp_path / "test_site" / "articles" / "markdown"
        content_dir.mkdir(parents=True)
        markdown_file = content_dir / "test-slug.md"
        markdown_file.write_text("---\ntitle: Test\n---\n\nContent")

        monkeypatch.setenv("SITES_CONTENT_PATH", str(tmp_path))
        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)

        # Should raise RuntimeError with helpful message
        with pytest.raises(RuntimeError, match="does not support featured images"):
            hugo.set_featured_image_local(
                "test_site", "test-slug", "unknown-theme", "/images/test.jpg"
            )

        # File should not be modified
        assert markdown_file.read_text() == "---\ntitle: Test\n---\n\nContent"

    def test_sets_featured_image_for_ananke_theme(self, tmp_path, monkeypatch):
        """Test that featured image is set correctly for ananke theme."""
        # Create markdown file
        content_dir = tmp_path / "test_site" / "articles" / "markdown"
        content_dir.mkdir(parents=True)
        markdown_file = content_dir / "test-slug.md"
        markdown_file.write_text("---\ntitle: Test Article\n---\n\nContent here")

        monkeypatch.setenv("SITES_CONTENT_PATH", str(tmp_path))
        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)

        hugo.set_featured_image_local(
            "test_site", "test-slug", "ananke", "/images/cover.jpg"
        )

        # Verify frontmatter was updated
        content = markdown_file.read_text()
        assert "featured_image: /images/cover.jpg" in content
        assert "title: Test Article" in content
        assert "Content here" in content

    def test_sets_featured_image_for_papermod_theme(self, tmp_path, monkeypatch):
        """Test that featured image is set correctly for papermod theme with nested structure."""
        # Create markdown file
        content_dir = tmp_path / "test_site" / "articles" / "markdown"
        content_dir.mkdir(parents=True)
        markdown_file = content_dir / "test-slug.md"
        markdown_file.write_text("---\ntitle: Test Article\n---\n\nContent here")

        monkeypatch.setenv("SITES_CONTENT_PATH", str(tmp_path))
        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)

        hugo.set_featured_image_local(
            "test_site", "test-slug", "papermod", "/images/cover.jpg"
        )

        # Verify nested frontmatter was updated
        content = markdown_file.read_text()
        assert "cover:" in content
        assert "image: /images/cover.jpg" in content
        assert "title: Test Article" in content

    def test_sets_featured_image_for_clarity_theme(self, tmp_path, monkeypatch):
        """Test that featured image is set correctly for clarity theme with multiple fields."""
        # Create markdown file
        content_dir = tmp_path / "test_site" / "articles" / "markdown"
        content_dir.mkdir(parents=True)
        markdown_file = content_dir / "test-slug.md"
        markdown_file.write_text("---\ntitle: Test Article\n---\n\nContent here")

        monkeypatch.setenv("SITES_CONTENT_PATH", str(tmp_path))
        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)

        hugo.set_featured_image_local(
            "test_site", "test-slug", "clarity", "/images/cover.jpg"
        )

        # Verify BOTH fields are set to same value
        content = markdown_file.read_text()
        assert "featureImage: /images/cover.jpg" in content
        assert "thumbnail: /images/cover.jpg" in content
        assert "title: Test Article" in content
        assert "Content here" in content

    def test_idempotent_does_not_modify_if_already_set(self, tmp_path, monkeypatch):
        """Test that method is idempotent and doesn't modify file if already set."""
        # Create markdown file with featured image already set
        content_dir = tmp_path / "test_site" / "articles" / "markdown"
        content_dir.mkdir(parents=True)
        markdown_file = content_dir / "test-slug.md"
        original_content = "---\nfeatured_image: /images/cover.jpg\ntitle: Test Article\n---\n\nContent here"
        markdown_file.write_text(original_content)

        monkeypatch.setenv("SITES_CONTENT_PATH", str(tmp_path))
        mock_ssh = Mock()
        hugo = HugoDeployer(mock_ssh)

        hugo.set_featured_image_local(
            "test_site", "test-slug", "ananke", "/images/cover.jpg"
        )

        # File should not be modified (content should be identical)
        assert markdown_file.read_text() == original_content
