"""WordOps Provisioner - SSH-based WordPress site provisioning."""

import logging
import tempfile
from pathlib import Path

from site_automator.ssh import resolve_ssh_host, SSHConnection

logger = logging.getLogger(__name__)


class WordOpsProvisioner:
    """Provision WordPress sites via WordOps over SSH."""

    host: str
    user: str | None
    ssh: SSHConnection

    def __init__(
        self,
        host: str,
        user: str | None = None,
    ) -> None:
        """Connect to server via SSH.

        Args:
            host: SSH host alias from ~/.ssh/config or IP/hostname
            user: SSH username (default: None, uses SSH config or falls back to 'root')
        """
        self.host = host
        self.user = user
        self.ssh = SSHConnection(host, user)

    def close(self) -> None:
        """Close SSH connection."""
        self.ssh.close()

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
        output, _ = self.ssh.run_command(command, check=True)
        logger.info(f"Site created successfully: {domain}")
        logger.debug(f"Site creation output:\n{output}")

    def restart_nginx(self) -> None:
        """Restart Nginx service.

        Raises:
            RuntimeError: If restart fails
        """
        logger.info("Restarting Nginx")
        self.ssh.run_command("systemctl restart nginx", check=True)
        logger.info("Nginx restarted successfully")

    def ensure_git_safe_directory(self) -> None:
        """Configure git to allow WordOps to manage site configs.

        Git blocks operations in repositories owned by another user.
        WordOps creates site config repos as www-data but runs commands as root,
        which can trigger "dubious ownership" errors.

        Set safe.directory='*' at the system level so automation can
        operate on WordOps-managed repositories without git failures.

        This should be run once during initial server setup.
        """
        logger.info("Configuring git safe.directory for WordOps")
        self.ssh.run_command("git config --system --add safe.directory '*'", check=True)
        logger.info("Git safe.directory configured")

    def ensure_ssl(self, domain: str) -> bool:
        """Enable SSL for domain if not already enabled.

        Checks DNS propagation before attempting SSL issuance.
        If DNS doesn't point to this server, skips SSL with a warning.

        Args:
            domain: Domain name

        Returns:
            True if SSL was enabled or already exists, False if skipped due to DNS mismatch
        """
        # Check if SSL is already enabled by looking for SSL certificate files
        check_cmd = f"test -f /var/www/{domain}/conf/nginx/ssl.conf"
        _, exit_code = self.ssh.run_command(check_cmd, check=False)

        if exit_code == 0:
            logger.info(f"SSL already enabled for {domain}")
            return True

        # Get server IP
        server_ip, _, _ = resolve_ssh_host(self.host)

        # Check DNS propagation using Google's DNS (8.8.8.8)
        logger.info(f"Checking DNS propagation for {domain} (expected IP: {server_ip})")
        dns_check = f"dig +short {domain} @8.8.8.8 | grep -q '^{server_ip}$'"
        _, exit_code = self.ssh.run_command(dns_check, check=False)

        if exit_code != 0:
            logger.warning(
                f"DNS for {domain} not pointing to {server_ip} yet. "
                f"Skipping SSL. Add manually later with: wo site update {domain} --letsencrypt"
            )
            return False

        # Enable SSL using WordOps
        logger.info(f"Enabling SSL for {domain}")
        self.ssh.run_command(f"wo site update {domain} --letsencrypt", check=True)
        logger.info(f"SSL enabled successfully for {domain}")
        return True

    def ensure_default_catchall(self, return_code: int = 444) -> None:
        """Create default catch-all Nginx server block if not already present.

        Prevents unmatched domains from being served by the first available site.
        Creates /etc/nginx/sites-available/000-catchall that handles both HTTP
        and HTTPS requests for any domain without a specific server block.

        Removes /etc/nginx/sites-enabled/default if present to avoid conflicts.

        Args:
            return_code: HTTP status code to return for HTTP requests
                        (default: 444 = close connection)

        Raises:
            RuntimeError: If catch-all creation fails or conflicting default_server exists
        """
        # Check if our catch-all already exists
        check_cmd = "test -L /etc/nginx/sites-enabled/000-catchall"
        _, exit_code = self.ssh.run_command(check_cmd, check=False)

        if exit_code == 0:
            logger.info("Default catch-all already exists")
            return

        # Remove distro default if present
        self.ssh.run_command(
            "[ -L /etc/nginx/sites-enabled/default ] && rm /etc/nginx/sites-enabled/default",
            check=False,
        )

        # Check for other conflicting default_server blocks
        check_cmd = (
            "grep -R 'listen .*default_server' /etc/nginx/sites-enabled/ 2>/dev/null "
            "| grep -E 'listen (80|443)' "
            "| grep -v 000-catchall || true"
        )
        output, _ = self.ssh.run_command(check_cmd, check=False)

        if output.strip():
            raise RuntimeError(
                f"Conflicting default_server blocks found:\n{output}\n"
                "Remove these before creating catch-all."
            )

        logger.info("Creating default catch-all server block")

        config = f"""server {{
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    return {return_code};
}}

server {{
    listen 443 ssl default_server;
    listen [::]:443 ssl default_server;
    server_name _;
    ssl_reject_handshake on;
}}"""

        config_path = "/etc/nginx/sites-available/000-catchall"

        # Write to temp file and upload
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".conf") as f:
            f.write(config)
            temp_path = Path(f.name)

        try:
            self.ssh.upload_file(temp_path, config_path)
        finally:
            temp_path.unlink()

        self.ssh.run_command(
            "ln -sf /etc/nginx/sites-available/000-catchall /etc/nginx/sites-enabled/000-catchall",
            check=True,
        )

        self.ssh.run_command("nginx -t", check=True)
        self.ssh.run_command("systemctl reload nginx", check=True)

        logger.info("Default catch-all created successfully")
