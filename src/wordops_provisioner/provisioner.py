"""WordOps Provisioner - SSH-based WordPress site provisioning."""

import logging
import os

import paramiko
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class WordOpsProvisioner:
    """Provision WordPress sites via WordOps over SSH."""

    host: str
    user: str
    password: str | None
    _client: paramiko.SSHClient | None

    def __init__(
        self,
        host: str,
        user: str = "root",
        password: str | None = None,
    ) -> None:
        """Connect to server via SSH.

        Args:
            host: Server hostname or IP address
            user: SSH username (default: root)
            password: SSH password
        """
        self.host = host
        self.user = user
        self.password = password
        self._client: paramiko.SSHClient | None = None
        self._connect()

    def _connect(self) -> None:
        """Establish SSH connection."""
        logger.info(f"Connecting to {self.host} as {self.user}")
        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self._client.connect(
            hostname=self.host,
            username=self.user,
            password=self.password,
        )
        logger.info("SSH connection established")

    def close(self) -> None:
        """Close SSH connection."""
        if self._client:
            self._client.close()
            self._client = None

    def run_command(self, command: str, check: bool = True) -> tuple[str, int]:
        """Run SSH command. Returns (output, exit_code).

        Args:
            command: Shell command to execute
            check: If True, raise exception on non-zero exit code

        Returns:
            Tuple of (stdout output, exit code)

        Raises:
            RuntimeError: If check=True and command returns non-zero exit code
        """
        if not self._client:
            raise RuntimeError("SSH client not connected")

        logger.debug(f"Running command: {command}")
        _, stdout, stderr = self._client.exec_command(command)
        exit_code = stdout.channel.recv_exit_status()
        output = stdout.read().decode("utf-8").strip()
        error = stderr.read().decode("utf-8").strip()
        logger.debug(f"Command exit code: {exit_code}")

        if check and exit_code != 0:
            logger.error(f"Command failed: {command} (exit code {exit_code})")
            raise RuntimeError(
                f"Command failed with exit code {exit_code}: {command}\n"
                f"Error: {error}\n"
                f"Output: {output}"
            )

        # Return combined output if there's error output
        full_output = output if not error else f"{output}\n{error}".strip()
        return full_output, exit_code

    def wp(
        self,
        domain: str,
        wp_command: str,
        check: bool = True,
    ) -> tuple[str, int]:
        """Run WP-CLI command for a domain with --allow-root.

        Args:
            domain: Domain name of the site
            wp_command: WP-CLI command (e.g., "post create --post_title='Test'")
            check: If True, raise exception on non-zero exit code

        Returns:
            Tuple of (stdout output, exit code)

        Raises:
            RuntimeError: If check=True and command returns non-zero exit code
        """
        command = f"cd /var/www/{domain}/htdocs && wp {wp_command} --allow-root"
        return self.run_command(command, check=check)

    def site_exists(self, domain: str) -> bool:
        """Check if WordPress is installed for the domain.

        Args:
            domain: Domain name to check

        Returns:
            True if WordPress is installed, False otherwise
        """
        _, exit_code = self.wp(domain, "core is-installed", check=False)
        return exit_code == 0

    def create_site(
        self,
        domain: str,
        flags: list[str] | None = None,
    ) -> None:
        """Create site via `wo site create`.

        Args:
            domain: Domain name for the site
            flags: Additional flags to pass to WordOps (e.g., ["--wp", "--php81"])

        Raises:
            RuntimeError: If site creation fails
        """
        flags = flags or []
        flags_str = " ".join(flags)
        command = f"wo site create {domain} {flags_str}".strip()

        logger.info(f"Creating site: {domain}")
        logger.info(f"Flags: {flags_str}".strip())
        output, _ = self.run_command(command, check=True)
        logger.info(f"Site created successfully: {domain}")
        logger.debug(f"Site creation output:\n{output}")

    def configure_site(
        self,
        domain: str,
        title: str,
        description: str,
        timezone: str = "UTC",
        public: bool = True,
        permalink_structure: str = "/%postname%/",
    ) -> None:
        """Configure WordPress site settings.

        Args:
            domain: Domain name of the site
            title: Site title (blogname)
            description: Site tagline (blogdescription)
            timezone: Timezone string (e.g., "America/New_York", "UTC")
            public: Search engine visibility (True=visible, False=discourage)
            permalink_structure: URL structure (e.g., "/%postname%/")

        Raises:
            RuntimeError: If configuration fails
        """
        import shlex

        logger.info(f"Configuring site settings for {domain}")

        # Update site title
        self.wp(domain, f"option update blogname {shlex.quote(title)}", check=True)

        # Update site description
        self.wp(
            domain,
            f"option update blogdescription {shlex.quote(description)}",
            check=True,
        )

        # Update timezone
        self.wp(
            domain, f"option update timezone_string {shlex.quote(timezone)}", check=True
        )

        # Update search engine visibility (1=visible, 0=discourage)
        public_value = "1" if public else "0"
        self.wp(domain, f"option update blog_public {public_value}", check=True)

        # Update permalink structure
        self.wp(
            domain,
            f"rewrite structure {shlex.quote(permalink_structure)}",
            check=True,
        )

        logger.info(f"Site settings configured successfully for {domain}")

    def delete_demo_content(self, domain: str) -> None:
        """Delete default WordPress demo content.

        This method is idempotent. It can be run multiple times safely.
        If content is already deleted, it will be skipped.

        Deletes:
        - Post ID 1: "Hello world!"
        - Page ID 2: "Sample Page"
        - Page ID 3: "Privacy Policy"
        - Comment ID 1: Default comment

        Keeps:
        - Active theme
        - All plugins (including nginx-helper)
        - Default admin user

        Args:
            domain: Domain name of the site
        """
        logger.info(f"Deleting demo content for {domain}")

        # Delete default post (Hello world!)
        _, exit_code = self.wp(domain, "post delete 1 --force", check=False)
        if exit_code == 0:
            logger.debug("Deleted post ID 1 (Hello world!)")
        else:
            logger.debug("Post ID 1 not found (already deleted)")

        # Delete default pages (Sample Page, Privacy Policy)
        _, exit_code = self.wp(domain, "post delete 2 --force", check=False)
        if exit_code == 0:
            logger.debug("Deleted page ID 2 (Sample Page)")
        else:
            logger.debug("Page ID 2 not found (already deleted)")

        _, exit_code = self.wp(domain, "post delete 3 --force", check=False)
        if exit_code == 0:
            logger.debug("Deleted page ID 3 (Privacy Policy)")
        else:
            logger.debug("Page ID 3 not found (already deleted)")

        # Delete default comment (may already be deleted with post)
        _, exit_code = self.wp(domain, "comment delete 1 --force", check=False)
        if exit_code == 0:
            logger.debug("Deleted comment ID 1")
        else:
            logger.debug("Comment ID 1 not found (already deleted)")

        logger.info(f"Demo content deleted successfully for {domain}")

    def create_post(
        self,
        domain: str,
        title: str,
        content: str,
        status: str = "publish",
        post_type: str | None = None,
        author: str | None = None,
        date: str | None = None,
        slug: str | None = None,
        additional_flags: list[str] | None = None,
    ) -> int:
        """Create a WordPress post using WP-CLI.

        Args:
            domain: Domain name of the site
            title: Post title
            content: Post content
            status: Post status (default: "publish")
            post_type: Post type (e.g., "post", "page")
            author: Post author (user ID or login)
            date: Post date (e.g., "2024-01-01 12:00:00")
            slug: Post slug
            additional_flags: Additional WP-CLI flags (e.g., ["--key=value"])
                              These are passed verbatim to WP-CLI, so should be properly escaped

        Returns:
            Post ID

        Raises:
            RuntimeError: If post creation fails
        """
        import shlex

        # Use shlex.quote for proper shell escaping
        title_escaped = shlex.quote(title)
        content_escaped = shlex.quote(content)
        status_escaped = shlex.quote(status)

        command_parts = [
            "post create",
            f"--post_title={title_escaped}",
            f"--post_content={content_escaped}",
            f"--post_status={status_escaped}",
        ]

        # Add optional parameters with escaping
        if post_type:
            command_parts.append(f"--post_type={shlex.quote(post_type)}")
        if author:
            command_parts.append(f"--post_author={shlex.quote(author)}")
        if date:
            command_parts.append(f"--post_date={shlex.quote(date)}")
        if slug:
            command_parts.append(f"--post_name={shlex.quote(slug)}")

        # Add additional flags (already should be properly formatted)
        if additional_flags:
            command_parts.extend(additional_flags)

        command_parts.append("--porcelain")
        wp_command = " ".join(command_parts)

        logger.info(f"Creating post on {domain}: {title}")
        output, _ = self.wp(domain, wp_command, check=True)
        post_id = int(output.strip())
        logger.info(f"Post created successfully: ID {post_id}")
        logger.debug(f"Post creation output: {output}")

        return post_id

    def ensure_attachment(
        self,
        domain: str,
        image_path: str,
        title: str | None = None,
        alt_text: str | None = None,
    ) -> int:
        """Ensure an attachment exists for the given image path.

        If an attachment with this image_path already exists (identified by
        _import_source meta key), returns its ID. Otherwise, imports the
        image and returns the new attachment ID.

        Args:
            domain: Domain name of the site
            image_path: Path to image file on the server
            title: Optional title for the image
            alt_text: Optional alt text for the image

        Returns:
            Attachment ID (existing or newly created)

        Raises:
            RuntimeError: If import fails
        """
        import shlex

        logger.info(f"Ensuring attachment exists for {image_path} on {domain}")

        # Check if attachment already exists with this import source
        search_cmd = (
            f"post list --post_type=attachment --meta_key=_import_source "
            f"--meta_value={shlex.quote(image_path)} --field=ID"
        )
        output, _ = self.wp(domain, search_cmd, check=False)

        if output.strip():
            # Attachment exists, return first ID (if multiple exist, reuse the first)
            attachment_id = int(output.strip().split()[0])
            logger.info(f"Attachment already exists (ID: {attachment_id})")
            return attachment_id

        # Import new attachment
        logger.info(f"Importing new attachment from {image_path}")
        cmd_parts = [
            "media import",
            shlex.quote(image_path),
            "--porcelain",
        ]

        if title:
            cmd_parts.append(f"--title={shlex.quote(title)}")
        if alt_text:
            cmd_parts.append(f"--alt={shlex.quote(alt_text)}")

        cmd = " ".join(cmd_parts)
        output, _ = self.wp(domain, cmd, check=True)

        attachment_id = int(output.strip())

        # Set _import_source meta to enable deduplication (use 'set' not 'add' for idempotency)
        self.wp(
            domain,
            f"post meta set {attachment_id} _import_source {shlex.quote(image_path)}",
            check=True,
        )

        logger.info(f"Attachment imported successfully (ID: {attachment_id})")
        return attachment_id

    def set_featured_image(
        self,
        domain: str,
        post_id: int,
        attachment_id: int,
    ) -> None:
        """Set an existing attachment as the featured image for a post.

        Args:
            domain: Domain name of the site
            post_id: Post ID to set featured image for
            attachment_id: Attachment ID to use as featured image

        Raises:
            RuntimeError: If setting featured image fails
        """
        logger.info(f"Setting featured image for post {post_id} on {domain}")

        self.wp(
            domain,
            f"post meta update {post_id} _thumbnail_id {attachment_id}",
            check=True,
        )

        logger.info(f"Featured image set successfully (attachment ID: {attachment_id})")

    def restart_nginx(self) -> None:
        """Restart Nginx service.

        Raises:
            RuntimeError: If restart fails
        """
        logger.info("Restarting Nginx")
        self.run_command("systemctl restart nginx", check=True)
        logger.info("Nginx restarted successfully")

    def ensure_ssl(self, domain: str) -> None:
        """Enable SSL for domain if not already enabled.

        Args:
            domain: Domain name

        Raises:
            RuntimeError: If SSL enablement fails
        """
        # Check if SSL is already enabled by looking for SSL certificate files
        check_cmd = f"test -f /var/www/{domain}/conf/nginx/ssl.conf"
        _, exit_code = self.run_command(check_cmd, check=False)

        if exit_code == 0:
            logger.info(f"SSL already enabled for {domain}")
            return

        # Enable SSL using WordOps
        logger.info(f"Enabling SSL for {domain}")
        self.run_command(f"wo site update {domain} --letsencrypt", check=True)
        logger.info(f"SSL enabled successfully for {domain}")

    def ensure_swap(self, size_gb: int = 2) -> None:
        """Create swap file if not already present.

        Args:
            size_gb: Swap file size in GB (default: 2)

        Raises:
            RuntimeError: If swap creation fails
        """
        # Check if swap is already enabled
        output, _ = self.run_command("swapon --show", check=False)

        if output.strip():
            logger.info("Swap already exists")
            return

        # Create swap file
        logger.info(f"Creating {size_gb}GB swap file")
        self.run_command(f"fallocate -l {size_gb}G /swapfile", check=True)
        self.run_command("chmod 600 /swapfile", check=True)
        self.run_command("mkswap /swapfile", check=True)
        self.run_command("swapon /swapfile", check=True)

        # Add to fstab only if not already present (idempotent)
        self.run_command(
            "grep -q '^/swapfile ' /etc/fstab || "
            "echo '/swapfile none swap sw 0 0' >> /etc/fstab",
            check=True,
        )

        logger.info(f"Swap file created successfully: {size_gb}GB")

    @classmethod
    def from_env(cls) -> "WordOpsProvisioner":
        """Create provisioner from .env file.

        Expects environment variables:
            - SERVER_HOST: Server hostname or IP
            - SSH_USER: SSH username (optional, defaults to 'root')
            - SSH_PASSWORD: SSH password

        Returns:
            WordOpsProvisioner instance

        Raises:
            ValueError: If required environment variables are missing
        """
        load_dotenv()

        host = os.getenv("SERVER_HOST")
        if not host:
            raise ValueError("SERVER_HOST environment variable is required")

        user = os.getenv("SSH_USER", "root")
        password = os.getenv("SSH_PASSWORD")

        return cls(host=host, user=user, password=password)
