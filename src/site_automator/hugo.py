"""Hugo Deployer - SSH-based Hugo static site deployment."""

import logging
from pathlib import Path

from slugify import slugify

from site_automator.ssh import SSHConnection
from site_automator.utils import validate_domain

logger = logging.getLogger(__name__)


class HugoDeployer:
    """Deploy Hugo static sites via SSH."""

    ssh: SSHConnection

    def __init__(self, ssh: SSHConnection) -> None:
        """Initialize HugoDeployer.

        Args:
            ssh: SSH connection to the server
        """
        self.ssh = ssh

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

    def ensure_permissions(self, domain: str, user: str = "caddy") -> None:
        """Ensure correct ownership and permissions.

        Args:
            domain: Domain name for the Hugo site
            user: System user for ownership (default: caddy)

        Raises:
            ValueError: If domain is invalid
        """
        validate_domain(domain)
        logger.info(f"Ensuring permissions: {domain}")
        self.ssh.run_command(f"chown -R {user}:{user} /var/www/{domain}", check=True)
        self.ssh.run_command(f"chmod -R 755 /var/www/{domain}", check=True)
        logger.info(f"Permissions set: {domain}")

    def ensure_base_url(self, domain: str) -> None:
        """Ensure baseURL in hugo.toml is set to the domain.

        Args:
            domain: Domain name for the Hugo site

        Raises:
            ValueError: If domain is invalid
        """
        validate_domain(domain)
        logger.info(f"Ensuring baseURL in config: {domain}")

        config_path = f"/var/www/{domain}/hugo.toml"
        base_url = f"https://{domain}/"

        # Check if baseURL is already correct
        output, _ = self.ssh.run_command(
            f"grep '^baseURL' {config_path}",
            check=False,
        )

        if base_url in output:
            logger.info(f"baseURL already correct: {base_url}")
            return

        logger.info(f"Setting baseURL to: {base_url}")

        # Remove any existing baseURL line, then insert at top
        self.ssh.run_command(
            f"sed -i '/^baseURL/d' {config_path}",
            check=True,
        )
        self.ssh.run_command(
            f"sed -i \"1ibaseURL = '{base_url}'\" {config_path}",
            check=True,
        )

        logger.info(f"baseURL configured: {base_url}")

    def ensure_robots_txt(self, domain: str) -> None:
        """Ensure a basic robots.txt exists. With link to sitemap.

        Args:
            domain: Domain name for the Hugo site

        Raises:
            ValueError: If domain is invalid
        """
        validate_domain(domain)
        logger.info(f"Ensuring robots.txt: {domain}")
        content = f"User-agent: *\nAllow: /\n\nSitemap: https://{domain}/sitemap.xml"
        self.ssh.run_command(
            f"cat > /var/www/{domain}/static/robots.txt << 'EOF'\n{content}\nEOF",
            check=True,
        )
        logger.info(f"robots.txt created: {domain}")

    def ensure_theme_installed(self, domain: str, theme: str = "ananke") -> None:
        """Install Hugo theme if missing and ensure it's configured.

        Args:
            domain: Domain name for the Hugo site
            theme: Theme name (default: ananke)

        Raises:
            ValueError: If domain is invalid
        """
        validate_domain(domain)
        logger.info(f"Ensuring theme installed: {domain} ({theme})")

        theme_path = f"/var/www/{domain}/themes/{theme}"
        config_path = f"/var/www/{domain}/hugo.toml"

        # Ensure theme directory exists
        _, exit_code = self.ssh.run_command(f"test -d {theme_path}", check=False)
        if exit_code != 0:
            logger.info(f"Installing theme: {theme}")
            self.ssh.run_command(
                f"git clone https://github.com/theNewDynamic/gohugo-theme-{theme}.git {theme_path}",
                check=True,
            )
        else:
            logger.info(f"Theme directory exists: {theme}")

        # Ensure theme is in config (idempotent check)
        output, _ = self.ssh.run_command(
            f"grep '^theme' {config_path}",
            check=False,
        )

        # Check if already correct (single quotes)
        if f"theme = '{theme}'" in output:
            logger.info(f"Theme already in config: {theme}")
            logger.info(f"Theme ensured: {theme}")
            return

        # Remove any existing theme line, add correct one
        logger.info(f"Adding theme to config: {theme}")
        self.ssh.run_command(
            f"sed -i '/^theme = /d' {config_path}",
            check=True,
        )
        self.ssh.run_command(
            f"echo \"theme = '{theme}'\" >> {config_path}",
            check=True,
        )

        logger.info(f"Theme ensured: {theme}")

    def deploy_content_file(
        self,
        domain: str,
        slug: str,
        markdown_path: Path,
    ) -> None:
        """Copy a generated article into Hugo content directory.

        Args:
            domain: Domain name for the Hugo site
            slug: URL slug for the article
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

        logger.info(f"Deploying content file: {domain}/{slug}")

        # Upload file to Hugo content directory
        remote_path = f"/var/www/{domain}/content/{slug}.md"
        self.ssh.upload_file(markdown_path, remote_path)

        logger.info(f"Content file deployed: {slug}")

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

    def ensure_single_layout_override(self, domain: str) -> None:
        """Ensure article layout includes internal links block.

        Args:
            domain: Domain name for the Hugo site

        Raises:
            ValueError: If domain is invalid
        """
        validate_domain(domain)
        logger.info(f"Ensuring single layout override: {domain}")

        # Check if layout already exists
        check_cmd = f"test -f /var/www/{domain}/layouts/_default/single.html"
        _, exit_code = self.ssh.run_command(check_cmd, check=False)

        if exit_code == 0:
            logger.info(f"Single layout override already exists: {domain}")
            return

        # Create layout content that includes internal links partial
        layout_content = """{{- define "main" -}}
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

        logger.info(f"Creating single layout override: {domain}")

        # Create layouts directory
        self.ssh.run_command(f"mkdir -p /var/www/{domain}/layouts/_default", check=True)

        # Write layout file using heredoc
        self.ssh.run_command(
            f"cat > /var/www/{domain}/layouts/_default/single.html << 'EOF'\n{layout_content}\nEOF",
            check=True,
        )

        logger.info(f"Single layout override created: {domain}")

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
