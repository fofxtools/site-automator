"""WordOps Provisioner - SSH-based WordPress site provisioning."""

import logging

import paramiko

from site_automator.ssh import resolve_ssh_host

logger = logging.getLogger(__name__)


class WordOpsProvisioner:
    """Provision WordPress sites via WordOps over SSH."""

    host: str
    user: str | None
    _client: paramiko.SSHClient | None

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
        self._client: paramiko.SSHClient | None = None
        self._connect()

    def _connect(self) -> None:
        """Establish SSH connection using SSH keys and agent."""
        # Resolve SSH config alias to actual hostname
        hostname, config_user, keyfile = resolve_ssh_host(self.host)

        # Priority: explicit user > SSH config user > default 'root'
        username = self.user or config_user or "root"

        logger.info(f"Connecting to {self.host} (resolved: {hostname}) as {username}")
        logger.info(f"Using key file: {keyfile}")
        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self._client.connect(
            hostname=hostname,
            username=username,
            key_filename=keyfile,
            allow_agent=True,
            look_for_keys=True,
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

    def restart_nginx(self) -> None:
        """Restart Nginx service.

        Raises:
            RuntimeError: If restart fails
        """
        logger.info("Restarting Nginx")
        self.run_command("systemctl restart nginx", check=True)
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
        self.run_command("git config --system --add safe.directory '*'", check=True)
        logger.info("Git safe.directory configured")

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
        _, exit_code = self.run_command(check_cmd, check=False)

        if exit_code == 0:
            logger.info("Default catch-all already exists")
            return

        # Remove distro default if present
        self.run_command(
            "[ -L /etc/nginx/sites-enabled/default ] && rm /etc/nginx/sites-enabled/default",
            check=False,
        )

        # Check for other conflicting default_server blocks
        check_cmd = (
            "grep -R 'listen .*default_server' /etc/nginx/sites-enabled/ 2>/dev/null "
            "| grep -E 'listen (80|443)' "
            "| grep -v 000-catchall || true"
        )
        output, _ = self.run_command(check_cmd, check=False)

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

        self.run_command(
            f"cat > /etc/nginx/sites-available/000-catchall << 'EOF'\n{config}\nEOF",
            check=True,
        )

        self.run_command(
            "ln -sf /etc/nginx/sites-available/000-catchall /etc/nginx/sites-enabled/000-catchall",
            check=True,
        )

        self.run_command("nginx -t", check=True)
        self.run_command("systemctl reload nginx", check=True)

        logger.info("Default catch-all created successfully")

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
