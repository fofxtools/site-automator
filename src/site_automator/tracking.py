"""Pageview Tracking Setup - Install and configure pageview tracking."""

import logging
import shlex
import tempfile
from pathlib import Path

from site_automator.ssh import SSHConnection

logger = logging.getLogger(__name__)


class PageviewTrackingSetup:
    """Setup pageview tracking plugin with flat file storage."""

    ssh: SSHConnection

    def __init__(self, ssh: SSHConnection) -> None:
        """Initialize PageviewTrackingSetup.

        Args:
            ssh: SSHConnection instance
        """
        self.ssh = ssh

    def _upload_tracking_resources(self, remote_folder: str = "/shared") -> None:
        """Upload tracking plugin to remote server.

        Uploads the following file from local /resources/ folder if it
        doesn't already exist on the remote server:
        - pageview-tracking.zip

        Args:
            remote_folder: Remote folder path (default: "/shared")

        Raises:
            RuntimeError: If file upload fails
            FileNotFoundError: If local file is missing
        """
        from pathlib import Path

        logger.info(f"Uploading tracking resources to {remote_folder}")

        # Define files to upload
        files = [
            "pageview-tracking.zip",
        ]

        # Get local resources directory
        resources_dir = Path(__file__).parent.parent.parent / "resources"

        # Ensure remote folder exists
        logger.debug(f"Ensuring remote folder exists: {remote_folder}")
        self.ssh.run_command(f"mkdir -p {shlex.quote(remote_folder)}", check=True)

        for filename in files:
            local_path = resources_dir / filename
            remote_path = f"{remote_folder}/{filename}"

            # Always upload (overwrite if exists)
            logger.info(f"Uploading {filename} to {remote_path}")
            self.ssh.upload_file(local_path, remote_path)
            logger.debug(f"Upload completed: {remote_path}")

        logger.info("Tracking resources upload completed")

    def _create_env_file(self, domain: str) -> None:
        """Create .env file in site parent directory.

        Args:
            domain: Domain name (e.g., "example.com")

        Raises:
            RuntimeError: If .env file creation fails
        """
        logger.info(f"Creating .env file for {domain}")

        # .env file path
        env_file_path = f"/var/www/{domain}/.env"

        # .env file content
        env_content = "TRACKING_ENABLED=true\n"

        # Escape for shell
        env_file_path_escaped = shlex.quote(env_file_path)
        env_content_escaped = shlex.quote(env_content)

        # Create .env file
        logger.debug(f"Creating .env file at: {env_file_path}")
        command = f"echo {env_content_escaped} > {env_file_path_escaped}"
        self.ssh.run_command(command, check=True)

        logger.info(f".env file created successfully at: {env_file_path}")

    def _install_plugins(self, domain: str) -> None:
        """Install and activate tracking plugin.

        Installs:
        - /shared/pageview-tracking.zip

        Args:
            domain: Domain name

        Raises:
            RuntimeError: If plugin installation fails
        """
        logger.info(f"Installing tracking plugin for {domain}")

        # Plugin path
        plugin = "/shared/pageview-tracking.zip"
        plugin_escaped = shlex.quote(plugin)

        logger.debug(f"Installing plugin: {plugin}")

        command = (
            f"cd /var/www/{domain}/htdocs && "
            f"wp plugin install {plugin_escaped} --activate --force --allow-root"
        )

        self.ssh.run_command(command, check=True)
        logger.debug(f"Plugin installed and activated: {plugin}")

        logger.info(f"Tracking plugin installed successfully for {domain}")

    def _update_track_config(self, domain: str, config_path: str | None = None) -> None:
        """Update track_config.php with settings from .env file.

        Reads configuration from .env file and updates the track_config.php
        file in the pageview-tracking plugin. Automatically calculates the
        relative path from track_config.php to the .env file based on the
        config_path location.

        Environment variables:
        - TRACKING_DATA_ROOT: Data root directory (default: '/var/lib/pageview-tracking')
        - TRACKING_EXCLUDE_IPS: Comma-delimited IP addresses (becomes array)
        - TRACKING_EXCLUDE_IPS_CIDR: Comma-delimited CIDR ranges (becomes array)
        - TRACKING_EXCLUDE_USER_AGENTS_EXACT: Comma-delimited exact matches (becomes array)
        - TRACKING_EXCLUDE_USER_AGENTS_SUBSTRING: Comma-delimited substrings (becomes array)

        Args:
            domain: Domain name
            config_path: Full path to track_config.php file. If None, defaults to
                        WordPress plugin path (/var/www/{domain}/htdocs/wp-content/plugins/
                        pageview-tracking/track_config.php)

        Raises:
            RuntimeError: If config update fails
        """
        import os

        logger.info(f"Updating track_config.php for {domain}")

        # Read local .env file to get configuration
        logger.debug("Reading local .env file for tracking configuration")

        # Get config values from local environment (with defaults)
        data_root = os.getenv("TRACKING_DATA_ROOT", "/var/lib/pageview-tracking")
        exclude_ips = os.getenv("TRACKING_EXCLUDE_IPS", "")
        exclude_ips_cidr = os.getenv("TRACKING_EXCLUDE_IPS_CIDR", "")
        exclude_user_agents_exact = os.getenv("TRACKING_EXCLUDE_USER_AGENTS_EXACT", "")
        exclude_user_agents_substring = os.getenv(
            "TRACKING_EXCLUDE_USER_AGENTS_SUBSTRING", ""
        )

        # Default to WordPress config file path if not specified
        config_file_path = (
            config_path
            or f"/var/www/{domain}/htdocs/wp-content/plugins/pageview-tracking/track_config.php"
        )

        # Auto-calculate relative path from track_config.php to .env
        env_file_location = f"/var/www/{domain}/.env"
        config_dir = os.path.dirname(config_file_path)
        env_file = os.path.relpath(env_file_location, config_dir)
        logger.debug(f"Calculated relative path to .env: {env_file}")

        # Convert comma-delimited strings to PHP arrays
        def to_php_array(csv_string: str) -> str:
            """Convert comma-delimited string to PHP array syntax."""
            if not csv_string:
                return "[]"
            items = [item.strip() for item in csv_string.split(",") if item.strip()]
            quoted_items = [f"'{item}'" for item in items]
            return "[" + ", ".join(quoted_items) + "]"

        # Build PHP config file content
        php_config = f"""<?php

declare(strict_types=1);

/**
 * Tracking Configuration
 *
 * Data storage and exclude IP and user agent settings.
 */

return [
    /**
     * Path to .env file for loading environment variables.
     *
     * Example:
     * - '../../../../.env' (site root, one level above document root)
     */
    'env_file' => '{env_file}',

    /**
     * Data root directory for flat file storage.
     *
     * Example:
     * - '/var/lib/pageview-tracking'
     */
    'data_root' => '{data_root}',

    /**
     * Individual IP addresses to exclude (IPv4 or IPv6).
     *
     * e.g. admin IP, banned IPs, etc.
     * 
     * Only applies to pageview tracking (track_pageview.php), not bot tracking (track_bots.php).
     *
     * Example: ['127.0.0.1', '192.168.1.100', '2001:db8::1']
     */
    'exclude_ips' => {to_php_array(exclude_ips)},

    /**
     * CIDR ranges to exclude (IPv4 or IPv6).
     * 
     * Only applies to pageview tracking (track_pageview.php), not bot tracking (track_bots.php).
     *
     * Example: ['192.168.1.0/24', '2001:db8::/32']
     */
    'exclude_ips_cidr' => {to_php_array(exclude_ips_cidr)},

    /**
     * User agent strings to exclude (exact match, case-insensitive).
     * 
     * Only applies to pageview tracking (track_pageview.php), not bot tracking (track_bots.php).
     *
     * Example: ['BadBot/1.0', 'Scraper/2.0']
     */
    'exclude_user_agents_exact' => {to_php_array(exclude_user_agents_exact)},

    /**
     * User agent substrings to exclude (substring match, case-insensitive).
     * 
     * Only applies to pageview tracking (track_pageview.php), not bot tracking (track_bots.php).
     *
     * Example: ['badbot', 'scraper']
     */
    'exclude_user_agents_substring' => {to_php_array(exclude_user_agents_substring)},
];
"""

        logger.debug(f"Writing track_config.php: {config_file_path}")

        # Write to temp file and upload
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".php") as f:
            f.write(php_config)
            temp_path = Path(f.name)

        try:
            self.ssh.upload_file(temp_path, config_file_path)
            logger.info(f"track_config.php updated successfully for {domain}")
        finally:
            temp_path.unlink()

    def _create_data_directory(self) -> None:
        """Create flat file storage directory with proper permissions.

        Creates /var/lib/pageview-tracking directory with subdirectories:
        - raw/          - Raw JSONL logs by domain/date
        - agg/daily/    - Aggregated daily statistics
        - scripts/      - Python processing scripts

        Permissions:
        - Owner: www-data
        - Group: www-data
        - Permissions: 775 (rwxrwxr-x)
        - Setgid bit: Ensures new files inherit group ownership

        This method is idempotent - ensures subdirectories exist even if base directory exists.

        Raises:
            RuntimeError: If directory creation fails
        """
        logger.info("Setting up flat file storage directory")

        # Always ensure subdirectories exist (mkdir -p is idempotent)
        logger.debug("Creating directory structure with subdirectories")

        commands = [
            "sudo mkdir -p /var/lib/pageview-tracking/raw",
            "sudo mkdir -p /var/lib/pageview-tracking/agg/daily",
            "sudo mkdir -p /var/lib/pageview-tracking/scripts",
            "sudo chown -R www-data:www-data /var/lib/pageview-tracking",
            "sudo chmod -R 775 /var/lib/pageview-tracking",
            "sudo chmod g+s /var/lib/pageview-tracking",
        ]

        for command in commands:
            logger.debug(f"Executing: {command}")
            self.ssh.run_command(command, check=True)

        logger.info("Flat file storage directory created successfully")

    def _upload_processing_scripts(self) -> None:
        """Upload Python log processing scripts to server.

        Uploads:
        - process_daily_logs.py (required for stats generation)
        - generate_dummy_logs.py (optional, for testing)

        Destination: /var/lib/pageview-tracking/scripts/

        Raises:
            RuntimeError: If script upload fails
        """
        logger.info("Uploading Python processing scripts")

        scripts = [
            "process_daily_logs.py",  # Required
            "generate_dummy_logs.py",  # Optional (testing)
        ]

        for script in scripts:
            # Path: src/site_automator/tracking.py -> src/ -> project_root/ -> pageview-tracking/
            local_path = (
                Path(__file__).parent.parent.parent
                / "pageview-tracking"
                / "python"
                / script
            )
            remote_path = f"/var/lib/pageview-tracking/scripts/{script}"

            logger.info(f"Uploading {script} to {remote_path}")
            self.ssh.upload_file(local_path, remote_path)
            logger.debug(f"Upload completed: {remote_path}")

            # Make executable
            command = f"chmod +x {shlex.quote(remote_path)}"
            self.ssh.run_command(command, check=True)

        logger.info("Python processing scripts uploaded successfully")

    def _setup_cron_job(self) -> None:
        """Setup cron job to process pageview logs.

        Adds cron job to run process_daily_logs.py.
        This method is idempotent - won't add duplicate entries.

        Raises:
            RuntimeError: If cron setup fails
        """
        logger.info("Setting up cron job for log processing")

        cron_line = "0 * * * * /usr/bin/python3 /var/lib/pageview-tracking/scripts/process_daily_logs.py"

        # Add to crontab if not already present
        command = (
            f"(crontab -l 2>/dev/null | grep -q 'process_daily_logs.py') || "
            f"(crontab -l 2>/dev/null; echo {shlex.quote(cron_line)}) | crontab -"
        )

        self.ssh.run_command(command, check=True)
        logger.info("Cron job setup completed")

    def setup_tracking_wordpress(self, domain: str) -> None:
        """Setup complete pageview tracking system for a domain.

        This method:
        - Uploads tracking plugin to /shared/
        - Creates .env file in site parent directory
        - Installs and activates tracking plugin
        - Updates track_config.php with settings from .env
        - Creates flat file storage directory (/var/lib/pageview-tracking)
        - Uploads Python processing scripts
        - Sets up cron job for log processing

        Environment variables (optional):
        - TRACKING_DATA_ROOT: Data root directory (default: '/var/lib/pageview-tracking')
        - TRACKING_EXCLUDE_IPS: Comma-delimited IP addresses to exclude
        - TRACKING_EXCLUDE_IPS_CIDR: Comma-delimited CIDR ranges to exclude
        - TRACKING_EXCLUDE_USER_AGENTS_EXACT: Comma-delimited exact user agents to exclude
        - TRACKING_EXCLUDE_USER_AGENTS_SUBSTRING: Comma-delimited user agent substrings to exclude

        Args:
            domain: Domain name of the site (e.g., "example.com")

        Raises:
            RuntimeError: If setup fails
        """
        logger.info(f"Setting up pageview tracking for {domain}")

        # Upload tracking resources
        self._upload_tracking_resources()

        # Create .env file
        self._create_env_file(domain)

        # Install and activate plugin
        self._install_plugins(domain)

        # Update track_config.php
        self._update_track_config(domain)

        # Create flat file storage directory
        self._create_data_directory()

        # Upload Python processing scripts
        self._upload_processing_scripts()

        # Setup cron job for log processing
        self._setup_cron_job()

        logger.info(f"Pageview tracking setup completed successfully for {domain}")

    def setup_tracking_hugo(self, domain: str) -> None:
        """Setup pageview tracking for Hugo static site.

        Deploys tracking files to Hugo's static directory and configures
        backend processing. Hugo will copy files from /static/ to /public/
        during site builds.

        This method:
        - Uploads tracking plugin files to /static/pageview-tracking/
        - Creates .env file in site parent directory
        - Creates flat file storage directory (/var/lib/pageview-tracking)
        - Uploads Python processing scripts
        - Sets up cron job for log processing

        Note: Caddy must be configured to handle PHP files via php-fpm.
        Note: Include tracking script in Hugo base template manually:
              <script src="/pageview-tracking/track_pageview.js"></script>

        Args:
            domain: Domain name of the site (e.g., "example.com")

        Raises:
            RuntimeError: If setup fails
        """
        logger.info(f"Setting up Hugo pageview tracking for {domain}")

        # Create tracking directory in Hugo's static folder
        tracking_dir = f"/var/www/{domain}/static/pageview-tracking"
        self.ssh.run_command(f"mkdir -p {tracking_dir}", check=True)
        logger.info(f"Created tracking directory: {tracking_dir}")

        # Upload entire plugin directory using rsync
        local_plugin_dir = (
            Path(__file__).parent.parent.parent
            / "pageview-tracking/php/plugins/pageview-tracking"
        )

        logger.info("Uploading tracking files via rsync...")
        self.ssh.upload_directory_rsync(
            local_plugin_dir,
            tracking_dir,
            exclude=["pageview-tracking.php"],  # Skip WordPress plugin main file
        )
        logger.info("Tracking files uploaded successfully")

        # Create .env file
        self._create_env_file(domain)

        # Update track_config.php
        hugo_config_path = f"{tracking_dir}/track_config.php"
        self._update_track_config(domain, hugo_config_path)

        # Create flat file storage directory
        self._create_data_directory()

        # Upload Python processing scripts
        self._upload_processing_scripts()

        # Setup cron job for log processing
        self._setup_cron_job()

        logger.info(f"Hugo pageview tracking setup completed for {domain}")
        logger.info("Next steps:")
        logger.info("  - Ensure Caddy is configured to handle PHP files via php-fpm")
        logger.info(
            "  - Add to Hugo base template: "
            "<script src='/pageview-tracking/track_pageview.js'></script>"
        )
        logger.info("  - Rebuild Hugo site to deploy tracking files to /public/")
