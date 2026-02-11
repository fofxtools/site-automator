"""Caddy Provisioner - SSH-based static site provisioning with Caddy."""

import logging
import tempfile
from pathlib import Path

from site_automator.ssh import SSHConnection
from site_automator.utils import validate_domain

logger = logging.getLogger(__name__)


class CaddyProvisioner:
    """Provision static sites via Caddy over SSH."""

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

    def reload_caddy(self) -> None:
        """Validate then gracefully reload Caddy (zero-downtime).

        Validates config before reloading to prevent breaking the server.

        Raises:
            RuntimeError: If validation or reload fails
        """
        # Validate config
        self.ssh.run_command("caddy validate --config /etc/caddy/Caddyfile", check=True)

        # Graceful reload
        self.ssh.run_command("caddy reload --config /etc/caddy/Caddyfile", check=True)

    def _generate_config(self, domain: str) -> str:
        """Generate Caddy site configuration.

        Creates a Caddy config with:
        - PHP 8.3 FPM support
        - JSON access logging with rotation (GoAccess compatible)
        - Static file serving with gzip

        Args:
            domain: Domain name (e.g., "example.com")

        Returns:
            Caddy configuration string
        """
        return f"""{domain} {{
    root * /var/www/{domain}/public

    php_fastcgi unix//run/php/php8.3-fpm.sock

    encode gzip
    file_server

    log {{
        output file /var/log/caddy/{domain}-access.log {{
            roll_size 100MiB
            roll_keep 20
            roll_keep_for 87600h
        }}
        format json
    }}
}}"""

    def ensure_caddyfile_import(self) -> None:
        """Set up import directive structure (idempotent).

        Creates:
        - /etc/caddy/sites-available/ directory
        - /etc/caddy/sites-enabled/ directory
        - Ensures main /etc/caddy/Caddyfile contains 'import sites-enabled/*'
        - Validates Caddy config

        This method is idempotent and can be run multiple times safely.

        Raises:
            RuntimeError: If setup fails or validation fails
        """
        # Create directories
        self.ssh.run_command("mkdir -p /etc/caddy/sites-available", check=True)
        self.ssh.run_command("mkdir -p /etc/caddy/sites-enabled", check=True)

        # Check if import directive already exists
        check_cmd = (
            "grep -q 'import sites-enabled/\\*' /etc/caddy/Caddyfile 2>/dev/null"
        )
        _, exit_code = self.ssh.run_command(check_cmd, check=False)

        if exit_code != 0:
            # Add import directive
            logger.info("Adding import directive to Caddyfile")
            self.ssh.run_command(
                "echo 'import sites-enabled/*' >> /etc/caddy/Caddyfile",
                check=True,
            )

        # Validate config
        self.ssh.run_command("caddy validate --config /etc/caddy/Caddyfile", check=True)
        logger.info("Caddyfile import structure configured")

    def enable_domain(self, domain: str) -> None:
        """Add domain using import directive pattern.

        Creates:
        - /var/www/{domain}/public directory
        - Site config at /etc/caddy/sites-available/{domain}.caddy
        - Symlink at /etc/caddy/sites-enabled/{domain}.caddy

        This method is idempotent and can be run multiple times safely.

        Args:
            domain: Domain name (e.g., "example.com")

        Raises:
            ValueError: If domain is invalid
            RuntimeError: If site creation fails or validation fails
        """
        validate_domain(domain)

        # Ensure Caddyfile structure is set up
        self.ensure_caddyfile_import()

        logger.info(f"Ensuring site is enabled: {domain}")

        # Ensure web root exists with correct permissions
        self.ssh.run_command(f"mkdir -p /var/www/{domain}/public", check=True)
        self.ssh.run_command(f"chown -R caddy:caddy /var/www/{domain}", check=True)
        self.ssh.run_command(f"chmod -R 755 /var/www/{domain}", check=True)

        # Ensure log directory exists with correct permissions
        self.ssh.run_command("mkdir -p /var/log/caddy", check=True)
        self.ssh.run_command("chown -R caddy:caddy /var/log/caddy", check=True)
        self.ssh.run_command("chmod -R 755 /var/log/caddy", check=True)

        # Generate and write site config
        site_config = self._generate_config(domain)
        config_path = f"/etc/caddy/sites-available/{domain}.caddy"

        # Write to temp file and upload
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".caddy") as f:
            f.write(site_config)
            temp_path = Path(f.name)

        try:
            self.ssh.upload_file(temp_path, config_path)
        finally:
            temp_path.unlink()

        # Ensure symlink exists
        self.ssh.run_command(
            f"ln -sf /etc/caddy/sites-available/{domain}.caddy /etc/caddy/sites-enabled/{domain}.caddy",
            check=True,
        )

        # Validate and reload
        self.reload_caddy()
        logger.info(f"Site enabled: {domain}")

    def disable_domain(self, domain: str) -> None:
        """Disable domain in Caddy (preserves config file).

        Removes:
        - Symlink from /etc/caddy/sites-enabled/{domain}.caddy
        - Validates and reloads Caddy

        Note: Site config is preserved in sites-available directory.

        Args:
            domain: Domain name (e.g., "example.com")

        Raises:
            ValueError: If domain is invalid
            RuntimeError: If site disabling fails or validation fails
        """
        validate_domain(domain)

        logger.info(f"Disabling domain: {domain}")

        # Remove symlink
        self.ssh.run_command(
            f"rm -f /etc/caddy/sites-enabled/{domain}.caddy",
            check=True,
        )

        # Validate and reload
        self.reload_caddy()
        logger.info(f"Domain disabled: {domain}")
