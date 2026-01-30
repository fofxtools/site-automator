"""Pageview Tracking Setup - Install and configure pageview tracking."""

import logging
import shlex
from pathlib import Path

from site_automator.wordops import WordOpsProvisioner

logger = logging.getLogger(__name__)


class PageviewTrackingSetup:
    """Setup pageview tracking plugin with flat file storage."""

    wordops: WordOpsProvisioner

    def __init__(self, wordops: WordOpsProvisioner) -> None:
        """Initialize PageviewTrackingSetup.

        Args:
            wordops: WordOpsProvisioner instance
        """
        self.wordops = wordops

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
        self.wordops.run_command(f"mkdir -p {shlex.quote(remote_folder)}", check=True)

        for filename in files:
            local_path = resources_dir / filename
            remote_path = f"{remote_folder}/{filename}"

            # Check if file exists locally
            if not local_path.exists():
                raise FileNotFoundError(f"Local file not found: {local_path}")

            # Always upload (overwrite if exists)
            logger.info(f"Uploading {filename} to {remote_path}")

            # Upload file using SFTP
            if not self.wordops._client:
                raise RuntimeError("SSH client not connected")

            sftp = self.wordops._client.open_sftp()
            try:
                sftp.put(str(local_path), remote_path)
                logger.debug(f"Upload completed: {remote_path}")
            finally:
                sftp.close()

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
        self.wordops.run_command(command, check=True)

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

        self.wordops.run_command(command, check=True)
        logger.debug(f"Plugin installed and activated: {plugin}")

        logger.info(f"Tracking plugin installed successfully for {domain}")

    def _update_track_config(self, domain: str) -> None:
        """Update track_config.php with settings from .env file.

        Reads configuration from .env file and updates the track_config.php
        file in the pageview-tracking plugin.

        Environment variables:
        - TRACKING_ENV_FILE: Path to .env file (default: '../../../../.env')
        - TRACKING_DATA_ROOT: Data root directory (default: '/var/lib/pageview-tracking')
        - TRACKING_EXCLUDE_IPS: Comma-delimited IP addresses (becomes array)
        - TRACKING_EXCLUDE_IPS_CIDR: Comma-delimited CIDR ranges (becomes array)
        - TRACKING_EXCLUDE_USER_AGENTS_EXACT: Comma-delimited exact matches (becomes array)
        - TRACKING_EXCLUDE_USER_AGENTS_SUBSTRING: Comma-delimited substrings (becomes array)

        Args:
            domain: Domain name

        Raises:
            RuntimeError: If config update fails
        """
        import os

        logger.info(f"Updating track_config.php for {domain}")

        # Read local .env file to get configuration
        logger.debug("Reading local .env file for tracking configuration")

        # Get config values from local environment (with defaults)
        env_file = os.getenv("TRACKING_ENV_FILE", "../../../../.env")
        data_root = os.getenv("TRACKING_DATA_ROOT", "/var/lib/pageview-tracking")
        exclude_ips = os.getenv("TRACKING_EXCLUDE_IPS", "")
        exclude_ips_cidr = os.getenv("TRACKING_EXCLUDE_IPS_CIDR", "")
        exclude_user_agents_exact = os.getenv("TRACKING_EXCLUDE_USER_AGENTS_EXACT", "")
        exclude_user_agents_substring = os.getenv(
            "TRACKING_EXCLUDE_USER_AGENTS_SUBSTRING", ""
        )

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
     * Example: ['127.0.0.1', '192.168.1.100', '2001:db8::1']
     */
    'exclude_ips' => {to_php_array(exclude_ips)},

    /**
     * CIDR ranges to exclude (IPv4 or IPv6).
     *
     * Example: ['192.168.1.0/24', '2001:db8::/32']
     */
    'exclude_ips_cidr' => {to_php_array(exclude_ips_cidr)},

    /**
     * User agent strings to exclude (exact match, case-insensitive).
     *
     * Example: ['BadBot/1.0', 'Scraper/2.0']
     */
    'exclude_user_agents_exact' => {to_php_array(exclude_user_agents_exact)},

    /**
     * User agent substrings to exclude (substring match, case-insensitive).
     *
     * Example: ['badbot', 'scraper']
     */
    'exclude_user_agents_substring' => {to_php_array(exclude_user_agents_substring)},
];
"""

        # Write to track_config.php
        config_file_path = (
            f"/var/www/{domain}/htdocs/wp-content/plugins/"
            f"pageview-tracking/track_config.php"
        )
        config_file_escaped = shlex.quote(config_file_path)
        php_config_escaped = shlex.quote(php_config)

        logger.debug(f"Writing track_config.php: {config_file_path}")
        command = f"echo {php_config_escaped} > {config_file_escaped}"
        self.wordops.run_command(command, check=True)

        logger.info(f"track_config.php updated successfully for {domain}")

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
            self.wordops.run_command(command, check=True)

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

            if not local_path.exists():
                raise FileNotFoundError(f"Local script not found: {local_path}")

            logger.info(f"Uploading {script} to {remote_path}")

            # Upload via SFTP
            if not self.wordops._client:
                raise RuntimeError("SSH client not connected")

            sftp = self.wordops._client.open_sftp()
            try:
                sftp.put(str(local_path), remote_path)
                logger.debug(f"Upload completed: {remote_path}")
            finally:
                sftp.close()

            # Make executable
            command = f"chmod +x {shlex.quote(remote_path)}"
            self.wordops.run_command(command, check=True)

        logger.info("Python processing scripts uploaded successfully")

    def _setup_cron_job(self) -> None:
        """Setup daily cron job to process pageview logs.

        Adds cron job to run process_daily_logs.py daily at 1 AM.
        This method is idempotent - won't add duplicate entries.

        Raises:
            RuntimeError: If cron setup fails
        """
        logger.info("Setting up cron job for log processing")

        cron_line = "0 1 * * * /usr/bin/python3 /var/lib/pageview-tracking/scripts/process_daily_logs.py"

        # Add to crontab if not already present
        command = (
            f"(crontab -l 2>/dev/null | grep -q 'process_daily_logs.py') || "
            f"(crontab -l 2>/dev/null; echo {shlex.quote(cron_line)}) | crontab -"
        )

        self.wordops.run_command(command, check=True)
        logger.info("Cron job setup completed")

    def setup_tracking(self, domain: str) -> None:
        """Setup complete pageview tracking system for a domain.

        This method:
        - Uploads tracking plugin to /shared/
        - Creates .env file in site parent directory
        - Installs and activates tracking plugin
        - Updates track_config.php with settings from .env
        - Creates flat file storage directory (/var/lib/pageview-tracking)
        - Uploads Python processing scripts
        - Sets up cron job for daily log processing

        Environment variables (optional):
        - TRACKING_ENV_FILE: Path to .env file (default: '../../../../.env')
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

        # Setup cron job for daily log processing
        self._setup_cron_job()

        logger.info(f"Pageview tracking setup completed successfully for {domain}")
