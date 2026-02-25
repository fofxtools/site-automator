"""Hugo Deployer - SSH-based Hugo static site deployment."""

import logging
import os
import re
import shutil
import tempfile
import tomllib
from pathlib import Path
from typing import Any

import frontmatter
from slugify import slugify

from site_automator.ssh import SSHConnection
from site_automator.utils import validate_domain, is_local_domain
from site_automator.tracking import PageviewTrackingSetup
from site_automator.sites import load_site_config_by_domain

logger = logging.getLogger(__name__)

# Theme storage and resources directories
THEME_STORAGE_DIR = Path(__file__).parent.parent.parent / "storage" / "hugo" / "themes"
THEME_RESOURCES_DIR = (
    Path(__file__).parent.parent.parent / "resources" / "hugo" / "themes"
)
THEME_FEATURED_IMAGE_MAP: dict[str, dict[str, Any]] = {
    "ananke": {
        "front_matter": {
            "featured_image": "{image_url}",
        },
    },
    "beautifulhugo": {
        "front_matter": {
            "image": "{image_url}",
        },
    },
    "clarity": {
        "front_matter": {
            "featureImage": "{image_url}",
            "thumbnail": "{image_url}",
        },
    },
    "mainroad": {
        "front_matter": {
            "thumbnail": "{image_url}",
        },
    },
    "papermod": {
        "front_matter": {
            "cover": {
                "image": "{image_url}",
            },
        },
    },
    "terminal": {
        "front_matter": {
            "cover": "{image_url}",
        },
    },
}


class HugoDeployer:
    """Deploy Hugo static sites via SSH."""

    ssh: SSHConnection
    themes: dict[str, str]
    theme_commits: dict[str, str]

    def __init__(self, ssh: SSHConnection, themes_file: Path | None = None) -> None:
        """Initialize HugoDeployer.

        Args:
            ssh: SSH connection to the server
            themes_file: Path to themes.toml config (optional)
        """
        self.ssh = ssh
        self.themes, self.theme_commits = self._load_themes(themes_file)

    def _load_themes(
        self, themes_file: Path | None
    ) -> tuple[dict[str, str], dict[str, str]]:
        """Load theme registry from TOML config.

        Args:
            themes_file: Path to themes.toml, defaults to config/themes.toml

        Returns:
            Tuple of (theme_urls, theme_commits) where:
            - theme_urls: Dictionary mapping theme names to git URLs
            - theme_commits: Dictionary mapping theme names to commit hashes

        Raises:
            FileNotFoundError: If themes file doesn't exist
            RuntimeError: If no themes defined in file
        """
        if themes_file is None:
            # Navigate from src/site_automator/hugo.py to config/themes.toml
            themes_file = Path(__file__).parent.parent.parent / "config" / "themes.toml"

        if not themes_file.exists():
            raise FileNotFoundError(f"Theme registry not found: {themes_file}")

        with themes_file.open("rb") as f:
            data = tomllib.load(f)

        themes_raw = data.get("themes", {})
        if not themes_raw:
            raise RuntimeError(f"No themes defined in {themes_file}")

        # Extract URLs and commits from nested structure
        theme_urls: dict[str, str] = {}
        theme_commits: dict[str, str] = {}

        for theme_name, theme_data in themes_raw.items():
            if not isinstance(theme_data, dict):
                raise RuntimeError(
                    f"Invalid theme config for '{theme_name}': expected dict with 'url' and 'commit'"
                )

            url = theme_data.get("url")
            commit = theme_data.get("commit")

            if not url:
                raise RuntimeError(f"Theme '{theme_name}' missing 'url' field")
            if not commit:
                raise RuntimeError(f"Theme '{theme_name}' missing 'commit' field")

            theme_urls[theme_name] = url
            theme_commits[theme_name] = commit

        logger.info(f"Loaded {len(theme_urls)} themes from {themes_file}")
        return theme_urls, theme_commits

    def _create_temp_bundle_structure(self, markdown_dir: Path) -> Path:
        """Create temporary directory with Hugo page bundle structure.

        Converts flat markdown files to page bundles:
            {slug}.md  →  temp/posts/{slug}/index.md

        Args:
            markdown_dir: Directory containing flat markdown files

        Returns:
            Path to temporary directory with posts/slug/index.md structure
            Caller must clean up temp directory
        """
        # Validate input directory
        if not markdown_dir.exists() or not markdown_dir.is_dir():
            raise ValueError(f"Markdown directory not found: {markdown_dir}")

        temp_dir = Path(tempfile.mkdtemp(prefix="hugo_bundles_"))
        bundle_root = temp_dir / "posts"
        bundle_root.mkdir(parents=True)

        for md_file in markdown_dir.glob("*.md"):
            slug = md_file.stem
            bundle_dir = bundle_root / slug
            bundle_dir.mkdir(exist_ok=True)
            shutil.copy2(md_file, bundle_dir / "index.md")
            logger.debug(f"Created bundle: posts/{slug}/index.md")

        return temp_dir

    @staticmethod
    def _is_hugo_content_rendering(line: str) -> bool:
        """Return True if the line renders .Content (not just references it)."""
        if not re.search(r"\.Content(?![A-Za-z])", line):
            return False

        stripped = line.strip()

        # Exclude control flow that references .Content but does not render it
        if re.search(r"\{\{-?\s*if\s+\.Content\s*-?\}\}", stripped):
            return False
        if re.search(r"\{\{-?\s*with\s+\.Content\s*-?\}\}", stripped):
            return False

        return True

    @staticmethod
    def _find_hugo_block_end(lines: list[str], start: int) -> int | None:
        """Find the matching {{ end }} for a Hugo template block using depth tracking.

        Args:
            lines: List of template lines
            start: Index to start searching from

        Returns:
            Index of the matching {{ end }} line, or None if not found"""
        depth = 0
        opener = re.compile(r"\{\{-?\s*(?:if|with|range|define|block)\b")
        closer = re.compile(r"\{\{-?\s*end\s*-?\}\}")

        for i in range(start, len(lines)):
            depth += len(opener.findall(lines[i]))
            depth -= len(closer.findall(lines[i]))
            if depth <= 0:
                return i

        return None

    def _inject_tracking_into_baseof(self, content: str) -> str:
        """Insert tracking partial before </body> if not already present.

        Args:
            content: The baseof.html template content

        Returns:
            Modified content with tracking partial injected

        Raises:
            RuntimeError: If </body> tag is missing"""
        if "pageview-tracking.html" in content:
            return content  # Already injected (idempotent)

        # Add newline before insertion for clean formatting
        insertion = '\n  {{ partial "pageview-tracking.html" . }}\n'

        if "</body>" in content:
            logger.info("Injecting pageview tracking before </body>")
            return content.replace("</body>", insertion + "</body>", 1)

        raise RuntimeError(
            "Theme baseof.html missing </body> tag - cannot inject tracking"
        )

    def _inject_internal_links_into_single(self, content: str) -> str:
        """Insert internal-links partial into single.html at the optimal location.

        Uses a cascade strategy to find the best injection point, prioritizing
        semantic placement (after .Content) over structural fallbacks (before
        closing tags). This ensures internal links appear in the correct location
        across different Hugo themes.

        Strategy cascade (first match wins):
            1. After direct .Content rendering (optimal - right after article content)
            2. After {{ with .Content }} block (handles wrapped content)
            3. Before </article> or </main> tag (structural fallback)
            4. Before {{ define "main" }} block's {{ end }} (last resort)
            5. Raise error (no silent append)

        Args:
            content: The single.html template content

        Returns:
            Modified content with internal-links partial injected

        Raises:
            RuntimeError: If no safe injection point can be found
        """

        if "internal-links.html" in content:
            return content  # Idempotent

        PARTIAL = '{{ partial "internal-links.html" . }}'
        lines = content.splitlines(keepends=True)

        def next_line_is_else(idx: int) -> bool:
            for j in range(idx + 1, len(lines)):
                stripped = lines[j].strip()
                if stripped:
                    return bool(re.match(r"\{\{-?\s*else", stripped))
            return False

        # PASS 1 — After direct .Content rendering
        # Inject after ALL .Content occurrences to handle templates with
        # multiple conditional branches (e.g., hermit-v2's legacy vs modern layout)
        injected = False
        offset = 0  # Track line insertions
        for i, line in enumerate(lines):
            if self._is_hugo_content_rendering(line) and not next_line_is_else(i):
                indent = line[: len(line) - len(line.lstrip())]
                lines.insert(i + 1 + offset, f"{indent}{PARTIAL}\n")
                offset += 1
                injected = True
                logger.info(
                    f"Injecting internal-links after .Content rendering (occurrence {offset})"
                )

        if injected:
            return "".join(lines)

        # PASS 2 — After {{ with .Content }} block end
        for i, line in enumerate(lines):
            if re.search(r"\{\{-?\s*with\s+\.Content\s*-?\}\}", line.strip()):
                end_i = self._find_hugo_block_end(lines, i)
                if end_i is not None:
                    indent = lines[end_i][
                        : len(lines[end_i]) - len(lines[end_i].lstrip())
                    ]
                    lines.insert(end_i + 1, f"{indent}{PARTIAL}\n")
                    logger.info(
                        "Injecting internal-links after {{ with .Content }} block"
                    )
                    return "".join(lines)

        # PASS 3 — Structural fallback before </article> or </main>
        for tag in ("</article>", "</main>"):
            for i in range(len(lines) - 1, -1, -1):
                if tag in lines[i]:
                    indent = lines[i][: len(lines[i]) - len(lines[i].lstrip())] + "  "
                    lines.insert(i, f"{indent}{PARTIAL}\n")
                    logger.info(f"Injecting internal-links before {tag} tag")
                    return "".join(lines)

        # PASS 4 — Before {{ end }} of {{ define "main" }}
        define_main = re.compile(r'\{\{-?\s*define\s+"main"')
        for i, line in enumerate(lines):
            if define_main.search(line):
                end_i = self._find_hugo_block_end(lines, i)
                if end_i is not None:
                    indent = (
                        lines[end_i][: len(lines[end_i]) - len(lines[end_i].lstrip())]
                        + "    "
                    )
                    for j in range(end_i - 1, i, -1):
                        if lines[j].strip():
                            indent = lines[j][: len(lines[j]) - len(lines[j].lstrip())]
                            break

                    lines.insert(end_i, f"{indent}{PARTIAL}\n")
                    logger.info(
                        'Injecting internal-links before {{ define "main" }} block\'s {{ end }}'
                    )
                    return "".join(lines)

        # FAIL — No valid injection point found
        raise RuntimeError(
            "Could not find safe injection point in single.html. "
            "Manual layout override required."
        )

    def _find_theme_baseof(self, site_root: str, theme: str) -> str | None:
        """Find theme's baseof.html in standard locations.

        Checks in Hugo's standard lookup order:
        1. layouts/baseof.html (modern themes)
        2. layouts/_default/baseof.html (legacy themes)

        Args:
            site_root: Site root directory path
            theme: Theme name

        Returns:
            Path to baseof.html if found, None otherwise
        """
        candidates = [
            f"{site_root}/themes/{theme}/layouts/baseof.html",
            f"{site_root}/themes/{theme}/layouts/_default/baseof.html",
        ]

        for path in candidates:
            _, exit_code = self.ssh.run_command(f'test -f "{path}"', check=False)
            if exit_code == 0:
                logger.info(f"Found theme baseof: {path}")
                return path

        logger.warning(
            f"No baseof.html found for theme '{theme}' in standard locations"
        )
        return None

    def _find_theme_single(self, site_root: str, theme: str) -> tuple[str | None, str]:
        """Find theme's single.html following Hugo's template lookup order.

        For content in the posts/ section, Hugo's lookup order is:
        1. layouts/posts/single.html (section-specific)
        2. layouts/_default/single.html (default)
        3. layouts/single.html (root)

        This method returns the FIRST match found, along with the target
        section where we should create our override.

        Args:
            site_root: Site root directory path
            theme: Theme name

        Returns:
            Tuple of (template_path, target_section) where:
            - template_path: Path to theme's single.html if found, None otherwise
            - target_section: Either "posts" or "_default" indicating where to
              create the site-level override
        """
        # Check in Hugo's priority order for posts/ section
        candidates = [
            (f"{site_root}/themes/{theme}/layouts/posts/single.html", "posts"),
            (f"{site_root}/themes/{theme}/layouts/_default/single.html", "_default"),
            (f"{site_root}/themes/{theme}/layouts/single.html", "_default"),
        ]

        for path, target in candidates:
            _, exit_code = self.ssh.run_command(f'test -f "{path}"', check=False)
            if exit_code == 0:
                logger.info(
                    f"Found theme single.html: {path} (will override at {target})"
                )
                return path, target

        logger.warning(
            f"No single.html found for theme '{theme}' in standard locations"
        )
        return None, "_default"

    def _generate_minimal_baseof_with_tracking(self) -> str:
        """Generate minimal baseof.html for themes without one.

        Uses blocks instead of partials for maximum theme compatibility.
        """
        return """<!DOCTYPE html>
<html lang="{{ .Site.Language.Lang | default "en" }}">
<head>
  {{ block "head" . }}{{ end }}
</head>
<body>
  {{ block "main" . }}{{ end }}
  {{ partial "pageview-tracking.html" . }}
</body>
</html>
    """

    def _create_tracking_partial(self, domain: str) -> None:
        """Create Hugo tracking partial."""
        site_root = f"/var/www/{domain}"
        partials_dir = f"{site_root}/layouts/partials"

        self.ssh.run_command(f"mkdir -p {partials_dir}", check=True)

        # Pixel before JS - works even if JS fails (bots)
        # Pass permalink through urlquery to ensure URL is properly encoded
        # Set trackUrl so track_pageview.js knows where to send tracking data
        partial_content = """<!-- Pageview Tracking -->
<img src="/pageview-tracking/pixel.php?url={{ .RelPermalink | urlquery }}"
  alt="" width="1" height="1" />
<script>
var PVT = {"trackUrl": "/pageview-tracking/track_pageview.php"};
</script>
<script src="/pageview-tracking/track_pageview.js" defer></script>
    """

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".html") as f:
            f.write(partial_content)
            temp_path = Path(f.name)

        try:
            self.ssh.upload_file(temp_path, f"{partials_dir}/pageview-tracking.html")
            logger.info(f"Created tracking partial for {domain}")
        finally:
            temp_path.unlink()

    def _create_baseof_with_tracking(self, domain: str, theme: str) -> None:
        """Create site-level baseof.html with tracking.

        Searches for theme's baseof.html in standard locations and injects tracking.
        If theme has no baseof, creates a minimal one with warning.

        Args:
            domain: Site domain
            theme: Theme name (e.g., "hugo-theme-stack")
        """
        site_root = f"/var/www/{domain}"
        site_layout_dir = f"{site_root}/layouts/_default"

        self.ssh.run_command(f"mkdir -p {site_layout_dir}", check=True)

        # Find theme baseof in standard locations
        theme_baseof = self._find_theme_baseof(site_root, theme)

        if theme_baseof:
            # Read and patch theme's baseof
            content, _ = self.ssh.run_command(f'cat "{theme_baseof}"', check=True)
            patched = self._inject_tracking_into_baseof(content)
            logger.info(f"Copied and patched theme baseof for {domain}")
        else:
            # Theme has no baseof - create minimal one with warning
            logger.warning(
                f"Theme '{theme}' has no baseof.html in standard locations. "
                f"Creating minimal layout for {domain}. Site may lose theme styling."
            )
            patched = self._generate_minimal_baseof_with_tracking()

        # Upload to site layouts
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".html") as f:
            f.write(patched)
            temp_path = Path(f.name)

        try:
            site_baseof = f"{site_layout_dir}/baseof.html"
            self.ssh.upload_file(temp_path, site_baseof)
        finally:
            temp_path.unlink()

    def check_hugo_installed(self) -> None:
        """Raise error if Hugo is not installed on server.

        Raises:
            RuntimeError: If Hugo is not installed
        """
        logger.info("Checking if Hugo is installed")
        _, exit_code = self.ssh.run_command("command -v hugo", check=False)
        if exit_code != 0:
            logger.error("Hugo is not installed on server")
            raise RuntimeError("Hugo is not installed on server")
        logger.info("Hugo is installed")

    def ensure_site_initialized(self, domain: str) -> None:
        """Create Hugo project skeleton if missing.

        Args:
            domain: Domain name for the Hugo site

        Raises:
            ValueError: If domain is invalid
        """
        validate_domain(domain)
        logger.info(f"Ensuring Hugo site initialized: {domain}")
        _, exit_code = self.ssh.run_command(
            f"test -f /var/www/{domain}/hugo.toml", check=False
        )
        if exit_code == 0:
            logger.info(f"Hugo site already initialized: {domain}")
            return

        logger.info(f"Initializing Hugo site: {domain}")
        self.ssh.run_command(f"mkdir -p /var/www/{domain}", check=True)
        self.ssh.run_command(
            f"cd /var/www/{domain} && hugo new site . --force", check=True
        )
        logger.info(f"Hugo site initialized: {domain}")

    def set_permissions(self, domain: str, user: str = "caddy") -> None:
        """Set correct ownership and permissions.

        Args:
            domain: Domain name for the Hugo site
            user: System user for ownership (default: caddy)

        Raises:
            ValueError: If domain is invalid
        """
        validate_domain(domain)
        logger.info(f"Setting permissions: {domain}")
        self.ssh.run_command(f"chown -R {user}:{user} /var/www/{domain}", check=True)
        self.ssh.run_command(f"chmod -R 755 /var/www/{domain}", check=True)
        logger.info(f"Permissions set: {domain}")

    def write_robots_txt(self, domain: str) -> None:
        """Write robots.txt with link to sitemap.

        Args:
            domain: Domain name for the Hugo site

        Raises:
            ValueError: If domain is invalid
        """
        validate_domain(domain)
        logger.info(f"Writing robots.txt: {domain}")
        content = f"User-agent: *\nAllow: /\n\nSitemap: https://{domain}/sitemap.xml"
        self.ssh.run_command(
            f"cat > /var/www/{domain}/static/robots.txt << 'EOF'\n{content}\nEOF",
            check=True,
        )
        logger.info(f"robots.txt created: {domain}")

    def ensure_theme_installed(self, domain: str, theme: str = "ananke") -> None:
        """Install Hugo theme if missing and checkout pinned commit.

        Args:
            domain: Domain name for the Hugo site
            theme: Theme name from themes.toml (default: ananke)

        Raises:
            ValueError: If domain is invalid
            RuntimeError: If theme not found in registry
        """
        validate_domain(domain)
        logger.info(f"Ensuring theme installed: {domain} ({theme})")

        theme_path = f"/var/www/{domain}/themes/{theme}"

        # Ensure theme directory exists
        _, exit_code = self.ssh.run_command(f"test -d {theme_path}", check=False)
        if exit_code != 0:
            # Look up theme URL and commit from registry
            try:
                repo_url = self.themes[theme]
                commit_hash = self.theme_commits[theme]
            except KeyError:
                available = ", ".join(sorted(self.themes.keys()))
                raise RuntimeError(
                    f"Theme '{theme}' not found in themes.toml. "
                    f"Available themes: {available}"
                )

            logger.info(f"Installing theme: {theme} from {repo_url} @ {commit_hash}")

            # Clone and checkout specific commit
            self.ssh.run_command(
                f"git clone {repo_url} {theme_path}",
                check=True,
            )
            self.ssh.run_command(
                f"cd {theme_path} && git checkout {commit_hash}",
                check=True,
            )
        else:
            logger.info(f"Theme directory exists: {theme}")

        logger.info(f"Theme ensured: {theme}")

    def upload_theme(self, domain: str, theme: str) -> None:
        """Upload theme from local storage to remote server.

        Args:
            domain: Domain name for the Hugo site
            theme: Theme name (must exist in storage/hugo/themes/)

        Raises:
            ValueError: If domain is invalid
            FileNotFoundError: If theme not found in storage
        """
        validate_domain(domain)

        theme_storage_path = THEME_STORAGE_DIR / theme
        if not theme_storage_path.exists():
            raise FileNotFoundError(f"Theme not found in storage: {theme_storage_path}")

        logger.info(f"Uploading theme {theme} to {domain}")

        remote_themes_dir = f"/var/www/{domain}/themes"
        self.ssh.run_command(f"mkdir -p {remote_themes_dir}", check=True)

        # Upload theme directory
        remote_theme_path = f"{remote_themes_dir}/{theme}"
        self.ssh.upload_directory_rsync(theme_storage_path, remote_theme_path)

        logger.info(f"Theme uploaded: {theme}")

    def apply_theme_overrides(self, domain: str, theme: str) -> None:
        """Apply theme override files from resources to remote server.

        Args:
            domain: Domain name for the Hugo site
            theme: Theme name (must exist in resources/hugo/themes/)

        Raises:
            ValueError: If domain is invalid
        """
        validate_domain(domain)

        theme_resources_path = THEME_RESOURCES_DIR / theme
        if not theme_resources_path.exists():
            logger.info(f"No theme overrides found for {theme}")
            return

        logger.info(f"Applying theme overrides for {theme} to {domain}")

        # Upload to site root (resources contain layouts/ subdirectory)
        remote_site_root = f"/var/www/{domain}"
        self.ssh.upload_directory_rsync(theme_resources_path, remote_site_root)

        logger.info(f"Theme overrides applied: {theme}")

    def write_hugo_config(self, domain: str, theme: str, title: str) -> None:
        """Write complete hugo.toml configuration (overwrites existing).

        For local domains (.test, .local, .localhost, .internal, or "localhost"),
        uses http://{domain}:8080 as baseURL for local development.

        Args:
            domain: Domain name for the site
            theme: Theme name (e.g., "ananke")
            title: Site title
        """
        validate_domain(domain)
        logger.info(f"Writing hugo.toml for {domain}")

        # Use http://{domain}:8080 for local domains, https://{domain}/ for production
        if is_local_domain(domain):
            base_url = f"http://{domain}:8080/"
        else:
            base_url = f"https://{domain}/"

        # Inline config template
        config_content = f"""baseURL = '{base_url}'
languageCode = 'en-us'
title = '{title}'
publishDir = 'public'
theme = '{theme}'

[permalinks]
  posts = "/:slug/"
"""

        # Use tempfile + upload_file pattern
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".toml") as f:
            f.write(config_content)
            temp_path = Path(f.name)

        try:
            config_path = f"/var/www/{domain}/hugo.toml"
            self.ssh.upload_file(temp_path, config_path)
            logger.info(f"hugo.toml written for {domain}")
        finally:
            temp_path.unlink()

    def ensure_internal_links_partial(self, domain: str, count: int = 10) -> None:
        """Ensure a random internal links partial exists.

        Creates a Hugo partial template at layouts/partials/internal-links.html
        that displays random internal links to other articles on the site.

        Args:
            domain: Domain name for the Hugo site
            count: Number of random links to display (default: 10)

        Raises:
            ValueError: If domain is invalid
        """
        validate_domain(domain)
        logger.info(f"Ensuring internal links partial: {domain} (count={count})")

        # Check if partial already exists
        check_cmd = f"test -f /var/www/{domain}/layouts/partials/internal-links.html"
        _, exit_code = self.ssh.run_command(check_cmd, check=False)

        if exit_code == 0:
            logger.info(f"Internal links partial already exists: {domain}")
            return

        # Create partial content - displays N random articles
        # Uses site.RegularPages without Type filter for maximum theme compatibility
        partial_content = f"""{{{{- $currentPage := . -}}}}
{{{{- $pages := site.RegularPages -}}}}
{{{{- $pages = where $pages "Permalink" "!=" $currentPage.Permalink -}}}}
{{{{- if ge (len $pages) 1 -}}}}
<aside class="internal-links">
  <h3>Other Articles</h3>
  <ul>
  {{{{- range first {count} (shuffle $pages) -}}}}
    <li><a href="{{{{ .Permalink }}}}">{{{{ .Title }}}}</a></li>
  {{{{- end -}}}}
  </ul>
</aside>
{{{{- end -}}}}"""

        logger.info(f"Creating internal links partial: {domain}")

        # Create partials directory
        self.ssh.run_command(f"mkdir -p /var/www/{domain}/layouts/partials", check=True)

        # Write partial file using heredoc (small file, simple content)
        self.ssh.run_command(
            f"cat > /var/www/{domain}/layouts/partials/internal-links.html << 'EOF'\n{partial_content}\nEOF",
            check=True,
        )

        logger.info(f"Internal links partial created: {domain}")

    def ensure_single_layout_override(self, domain: str, theme: str) -> None:
        """Ensure article layout includes internal links block.

        Searches for theme's single.html following Hugo's template lookup order
        and creates an override at the appropriate level (section-specific or default).

        For themes with section-specific templates (e.g., posts/single.html),
        creates override at layouts/posts/single.html to ensure proper precedence.

        Args:
            domain: Domain name for the Hugo site
            theme: Theme name (e.g., "hermit-v2")

        Raises:
            ValueError: If domain is invalid
        """
        validate_domain(domain)
        logger.info(f"Ensuring single layout override: {domain}")

        site_root = f"/var/www/{domain}"

        # Find theme's single.html and determine target section
        theme_single, target_section = self._find_theme_single(site_root, theme)

        # Determine site layout directory based on target section
        site_layout_dir = f"{site_root}/layouts/{target_section}"

        # Check if layout already exists
        check_cmd = f"test -f {site_layout_dir}/single.html"
        _, exit_code = self.ssh.run_command(check_cmd, check=False)

        if exit_code == 0:
            logger.info(f"Single layout override already exists: {domain}")
            return

        # Create layouts directory
        self.ssh.run_command(f"mkdir -p {site_layout_dir}", check=True)

        if theme_single:
            # Read and patch theme's single.html
            content, _ = self.ssh.run_command(f'cat "{theme_single}"', check=True)
            patched = self._inject_internal_links_into_single(content)
            logger.info(f"Copied and patched theme single.html for {domain}")
        else:
            # Theme has no single.html - create minimal one with warning
            logger.warning(
                f"Theme '{theme}' has no single.html. "
                f"Creating minimal layout for {domain}. Site may lose theme styling."
            )
            patched = """{{- define "main" -}}
<article>
  <header>
    <h1>{{ .Title }}</h1>
  </header>
  <div class="content">
    {{ .Content }}
  </div>
  {{- partial "internal-links.html" . -}}
</article>
{{- end -}}"""

        # Upload to site layouts
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".html") as f:
            f.write(patched)
            temp_path = Path(f.name)

        try:
            self.ssh.upload_file(temp_path, f"{site_layout_dir}/single.html")
            logger.info(f"Single layout override created: {domain}")
        finally:
            temp_path.unlink()

    def setup_tracking(self, domain: str, theme: str) -> None:
        """Setup pageview tracking for Hugo site.

        Args:
            domain: Site domain
            theme: Theme name for baseof.html detection
        """
        self._create_tracking_partial(domain)
        self._create_baseof_with_tracking(domain, theme)

    def symlink_shared_image(self, domain: str, image_filename: str) -> None:
        """Create symlink from shared images to site static directory.

        Args:
            domain: Domain name for the Hugo site
            image_filename: Filename of the image (e.g., "cover.jpg")

        Raises:
            ValueError: If domain is invalid
        """
        validate_domain(domain)

        shared_images_path = os.getenv("SHARED_IMAGES_PATH", "/var/www/shared/images")
        source_path = f"{shared_images_path}/{image_filename}"
        target_dir = f"/var/www/{domain}/static/images"
        target_path = f"{target_dir}/{image_filename}"

        logger.info(f"Creating symlink for {image_filename} in {domain}")

        self.ssh.run_command(f'mkdir -p "{target_dir}"', check=True)
        self.ssh.run_command(f'ln -sfn "{source_path}" "{target_path}"', check=True)

        logger.info(f"Symlink created: {target_path} -> {source_path}")

    def set_featured_image_local(
        self, site_id: str, slug: str, theme: str, image_url: str
    ) -> None:
        """Set featured image in local article front matter based on theme.

        Args:
            site_id: Site identifier (from sites.csv)
            slug: Article slug
            theme: Theme name (must exist in THEME_FEATURED_IMAGE_MAP)
            image_url: Public Hugo URL (e.g., "/images/cover.jpg")

        Raises:
            ValueError: If slug is invalid
            RuntimeError: If theme does not support featured images
            FileNotFoundError: If markdown file doesn't exist
        """
        if not slug or slug != slugify(slug):
            raise ValueError("Invalid slug")

        if theme not in THEME_FEATURED_IMAGE_MAP:
            supported = ", ".join(sorted(THEME_FEATURED_IMAGE_MAP.keys()))
            raise RuntimeError(
                f"Theme '{theme}' does not support featured images. "
                f"Supported themes: {supported}"
            )

        # Local markdown path
        content_root = Path(os.getenv("SITES_CONTENT_PATH", "storage/content"))
        markdown_path = content_root / site_id / "articles" / "markdown" / f"{slug}.md"

        if not markdown_path.exists():
            raise FileNotFoundError(f"Markdown file not found: {markdown_path}")

        logger.info(f"Setting featured image for {site_id}/{slug} (theme: {theme})")

        # Read original content
        with markdown_path.open("r", encoding="utf-8") as f:
            original_content = f.read()
            post = frontmatter.loads(original_content)

        # Get theme config and recursively replace placeholders
        theme_config: dict[str, Any] = THEME_FEATURED_IMAGE_MAP[theme]["front_matter"]

        def replace_placeholders(obj: dict[str, Any] | str) -> dict[str, Any] | str:
            """Recursively replace {image_url} placeholders in nested dicts."""
            if isinstance(obj, dict):
                return {k: replace_placeholders(v) for k, v in obj.items()}
            elif isinstance(obj, str):
                return obj.replace("{image_url}", image_url)
            return obj

        updated_fields = replace_placeholders(theme_config)

        # Update front matter only if values changed (idempotent)
        if isinstance(updated_fields, dict):
            for key, value in updated_fields.items():
                if post.metadata.get(key) != value:
                    post.metadata[key] = value

        # Only write if content changed
        updated_content = frontmatter.dumps(post)
        if updated_content != original_content:
            with markdown_path.open("w", encoding="utf-8") as f:
                f.write(updated_content)
            logger.info(f"Featured image set: {site_id}/{slug}")
        else:
            logger.info(f"Featured image already set: {site_id}/{slug}")

    def deploy_content_file(
        self,
        domain: str,
        slug: str,
        markdown_path: Path,
    ) -> None:
        """Deploy article as Hugo page bundle (leaf bundle).

        Creates page bundle structure:
            posts/slug/index.md

        This allows bundling images and other resources with content.

        Args:
            domain: Domain name for the Hugo site
            slug: URL slug for the article (becomes bundle directory name)
            markdown_path: Local path to the markdown file

        Raises:
            ValueError: If domain or slug is invalid
            FileNotFoundError: If markdown_path doesn't exist
        """
        validate_domain(domain)

        # Validate slug by re-slugifying and comparing
        if not slug or slug != slugify(slug):
            raise ValueError("Invalid slug")

        # Check if local file exists
        if not markdown_path.exists():
            raise FileNotFoundError(f"Markdown file not found: {markdown_path}")

        logger.info(f"Deploying content file as page bundle: {domain}/{slug}")

        # Create temporary bundle structure for single file
        temp_dir = Path(tempfile.mkdtemp(prefix=f"hugo_bundle_{slug}_"))
        bundle_dir = temp_dir / "posts" / slug
        bundle_dir.mkdir(parents=True)
        shutil.copy2(markdown_path, bundle_dir / "index.md")

        try:
            # Upload bundle directory to Hugo content folder
            remote_content_dir = f"/var/www/{domain}/content"
            self.ssh.upload_directory_rsync(temp_dir, remote_content_dir)

            logger.info(f"Page bundle deployed: {slug}")
        finally:
            # Clean up temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)

    def deploy_content_directory(
        self,
        domain: str,
        local_content_dir: Path | str,
        *,
        delete: bool = False,
    ) -> None:
        """Bulk upload flat markdown files as Hugo page bundles.

        Converts flat markdown files to page bundle structure:
            Input:  local_content_dir/{slug}.md
            Output: /var/www/{domain}/content/posts/{slug}/index.md

        This allows bundling images and other resources with content in the future.

        Args:
            domain: Domain name for the Hugo site
            local_content_dir: Local directory containing flat markdown files (*.md)
            delete: If True, delete remote content not present locally (default: False)

        Raises:
            ValueError: If domain is invalid
            FileNotFoundError: If local directory doesn't exist
        """
        validate_domain(domain)

        logger.info(f"Deploying content directory to {domain}")

        # Convert flat markdown files to bundle structure
        temp_dir = self._create_temp_bundle_structure(Path(local_content_dir))

        try:
            # Upload bundles to Hugo content directory
            remote_content_dir = f"/var/www/{domain}/content"
            self.ssh.upload_directory_rsync(temp_dir, remote_content_dir, delete=delete)

            logger.info(f"Content directory deployed: {domain}")
        finally:
            # Clean up temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)

    def build_site(self, domain: str) -> None:
        """Run hugo build and output into /public.

        Args:
            domain: Domain name for the Hugo site

        Raises:
            ValueError: If domain is invalid
            RuntimeError: If hugo build fails
        """
        validate_domain(domain)
        logger.info(f"Building Hugo site: {domain}")

        # Run hugo build in the site directory
        output, exit_code = self.ssh.run_command(
            f"cd /var/www/{domain} && hugo", check=False
        )

        if exit_code != 0:
            logger.error(f"Hugo build failed for {domain}\nOutput: {output}")
            raise RuntimeError(f"Hugo build failed for {domain}")

        logger.info(f"Hugo site built: {domain}")

    def wipe_site(
        self,
        domain: str,
        *,
        confirm: bool = False,
        exclude_dirs: list[str] | None = None,
    ) -> None:
        """Wipe Hugo site files.

        This is a destructive operation that deletes content, layouts,
        themes, static files, and build output.

        Args:
            domain: Domain name of the site
            confirm: Must be True to proceed. Prevents accidental wipes.
            exclude_dirs: Optional list of paths to preserve (e.g., ["public/stats"]).
                          Supports both top-level directories and nested paths.
                          By default, wipes everything.

        Raises:
            ValueError: If domain is invalid or confirm is not True
            RuntimeError: If any step fails
        """
        validate_domain(domain)

        if not confirm:
            raise ValueError(
                "wipe_site() requires confirm=True. This destroys all site data."
            )

        # Default to no exclusions (wipe everything)
        if exclude_dirs is None:
            exclude_dirs = []

        # Check if site directory exists
        site_path = f"/var/www/{domain}"
        stdout, _ = self.ssh.run_command(
            f"test -d {site_path} && echo 'exists' || echo 'missing'"
        )

        if "missing" in stdout:
            logger.info(f"Site directory does not exist, nothing to wipe: {domain}")
            return

        logger.info(
            f"Wiping Hugo site for {domain}"
            + (f" (preserving: {', '.join(exclude_dirs)})" if exclude_dirs else "")
        )

        # Build exclusion conditions for find command
        if exclude_dirs:
            # Build path exclusion conditions
            path_exclusions = []
            for path in exclude_dirs:
                # Exclude the path itself
                path_exclusions.append(f"! -path '/var/www/{domain}/{path}'")
                # Exclude everything under the path
                path_exclusions.append(f"! -path '/var/www/{domain}/{path}/*'")
            exclusion_expr = " ".join(path_exclusions)

            # Two-step deletion to properly handle nested exclusions:
            # Step 1: Delete all files except those in excluded paths
            delete_files_cmd = (
                f"find /var/www/{domain} -type f {exclusion_expr} -delete"
            )
            self.ssh.run_command(delete_files_cmd, check=True)

            # Step 2: Delete empty directories (won't delete parents of excluded paths)
            delete_dirs_cmd = (
                f"find /var/www/{domain} -depth -mindepth 1 -type d "
                f"{exclusion_expr} -empty -delete"
            )
            self.ssh.run_command(delete_dirs_cmd, check=True)
        else:
            # No exclusions: delete everything in one command
            delete_cmd = f"find /var/www/{domain} -mindepth 1 -delete"
            self.ssh.run_command(delete_cmd, check=True)

        logger.info(f"Hugo site wiped: {domain}")

    def initial_setup(self, domain: str, theme: str | None = None) -> None:
        """Perform complete initial Hugo site setup.

        This method orchestrates the complete initial setup of a Hugo site,
        from initialization through full configuration.

        Steps performed:
        - Initialize Hugo site skeleton (if not already initialized)
        - Upload theme from storage
        - Apply theme overrides from resources
        - Write complete hugo.toml configuration
        - Create robots.txt with sitemap link
        - Create internal links partial template
        - Setup pageview tracking
        - Set correct ownership and permissions

        Args:
            domain: Domain name of the site
            theme: Theme name to install (default: from config or ananke)

        Raises:
            RuntimeError: If any setup step fails
        """
        logger.info(f"Starting initial setup for {domain}")

        # Load site config to get theme and title
        site_config = load_site_config_by_domain(domain)

        # Get theme from config if not provided
        resolved_theme: str = (
            theme if theme is not None else site_config.get("theme", "ananke")
        )

        title = site_config.get("site_title", domain)

        self.ensure_site_initialized(domain)
        self.upload_theme(domain, resolved_theme)
        self.apply_theme_overrides(domain, resolved_theme)
        self.write_hugo_config(domain, resolved_theme, title)
        self.write_robots_txt(domain)
        self.ensure_internal_links_partial(domain)
        self._create_tracking_partial(domain)
        self.set_permissions(domain)

        # Setup pageview tracking
        tracking = PageviewTrackingSetup(self.ssh)
        tracking.setup_tracking_hugo(domain)

        logger.info(f"Initial setup complete for {domain}")
