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

    def ensure_publish_dir(self, domain: str) -> None:
        """Ensure publishDir in hugo.toml is set to 'public'.

        Args:
            domain: Domain name for the Hugo site

        Raises:
            ValueError: If domain is invalid
        """
        validate_domain(domain)
        logger.info(f"Ensuring publishDir in config: {domain}")

        config_path = f"/var/www/{domain}/hugo.toml"
        publish_dir = "public"

        # Check if publishDir is already correct
        output, _ = self.ssh.run_command(
            f"grep '^publishDir' {config_path}",
            check=False,
        )

        if f'publishDir = "{publish_dir}"' in output:
            logger.info(f"publishDir already correct: {publish_dir}")
            return

        logger.info(f"Setting publishDir to: {publish_dir}")

        # Remove any existing publishDir line, then append to end
        self.ssh.run_command(
            f"sed -i '/^publishDir/d' {config_path}",
            check=True,
        )
        self.ssh.run_command(
            f"sed -i '$a publishDir = \"{publish_dir}\"' {config_path}",
            check=True,
        )

        logger.info(f"publishDir configured: {publish_dir}")

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

    def deploy_content_directory(
        self,
        domain: str,
        local_content_dir: Path | str,
        *,
        delete: bool = False,
    ) -> None:
        """Bulk upload content directory to Hugo site using rsync.

        Args:
            domain: Domain name for the Hugo site
            local_content_dir: Local directory containing markdown files
            delete: If True, delete remote content not present locally (default: False)

        Raises:
            ValueError: If domain is invalid
            FileNotFoundError: If local directory doesn't exist
        """
        validate_domain(domain)

        logger.info(f"Deploying content directory to {domain}")

        remote_content_dir = f"/var/www/{domain}/content"
        self.ssh.upload_directory_rsync(
            local_content_dir, remote_content_dir, delete=delete
        )

        logger.info(f"Content directory deployed: {domain}")

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

    def initial_setup(self, domain: str, theme: str = "ananke") -> None:
        """Perform initial Hugo site setup after initialization.

        This method orchestrates the complete initial configuration of a Hugo site,
        including setting base URL, configuring publish directory, installing theme,
        creating robots.txt, setting up internal linking, and ensuring correct permissions.

        Steps performed:
        - Set baseURL in hugo.toml
        - Set publishDir in hugo.toml
        - Install and configure theme
        - Create robots.txt with sitemap link
        - Create internal links partial template
        - Create single layout override to include internal links
        - Set correct ownership and permissions

        Args:
            domain: Domain name of the site
            theme: Theme name to install (default: ananke)

        Raises:
            RuntimeError: If any setup step fails
        """
        logger.info(f"Starting initial setup for {domain}")

        self.ensure_base_url(domain)
        self.ensure_publish_dir(domain)
        self.ensure_theme_installed(domain, theme)
        self.ensure_robots_txt(domain)
        self.ensure_internal_links_partial(domain)
        self.ensure_single_layout_override(domain)
        self.ensure_permissions(domain)

        logger.info(f"Initial setup complete for {domain}")
