"""Pageview Tracking Setup - Install and configure pageview tracking plugins."""

import logging
import secrets
import shlex
import string

from site_automator.wordops import WordOpsProvisioner

logger = logging.getLogger(__name__)


class PageviewTrackingSetup:
    """Setup pageview tracking plugins and database."""

    wordops: WordOpsProvisioner

    def __init__(self, wordops: WordOpsProvisioner) -> None:
        """Initialize PageviewTrackingSetup.

        Args:
            wordops: WordOpsProvisioner instance
        """
        self.wordops = wordops

    def _upload_tracking_resources(self, remote_folder: str = "/shared") -> None:
        """Upload tracking plugin and SQL files to remote server.

        Uploads the following files from local /resources/ folder if they
        don't already exist on the remote server:
        - pageview-tracking-core.zip
        - pageview-tracking-daily.zip
        - pageview-tracking.zip
        - tracking_pageviews_daily.sql
        - tracking_pageviews.sql

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
            "pageview-tracking-core.zip",
            "pageview-tracking-daily.zip",
            "pageview-tracking.zip",
            "tracking_pageviews_daily.sql",
            "tracking_pageviews.sql",
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

            # Check if file exists remotely
            logger.debug(f"Checking if {remote_path} exists on remote server")
            check_command = f"test -f {shlex.quote(remote_path)}"
            _, exit_code = self.wordops.run_command(check_command, check=False)

            if exit_code == 0:
                logger.debug(f"File already exists remotely: {remote_path}")
            else:
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

    def _create_db_user(self, username: str, password: str) -> None:
        """Create MySQL user with provided password and grant all privileges.

        Args:
            username: MySQL username to create
            password: MySQL password to set

        Raises:
            RuntimeError: If user creation fails
        """
        logger.info(f"Creating MySQL user: {username}")

        # Create user if not exists, then alter to set password
        create_user_sql = f"CREATE USER IF NOT EXISTS '{username}'@'localhost';"
        alter_user_sql = (
            f"ALTER USER '{username}'@'localhost' IDENTIFIED BY '{password}';"
        )
        grant_sql = f"GRANT ALL PRIVILEGES ON *.* TO '{username}'@'localhost';"
        flush_sql = "FLUSH PRIVILEGES;"

        logger.debug(f"Creating MySQL user if not exists: {username}")
        self.wordops.run_command(f"mysql -e {shlex.quote(create_user_sql)}", check=True)

        logger.debug(f"Setting password for MySQL user: {username}")
        self.wordops.run_command(f"mysql -e {shlex.quote(alter_user_sql)}", check=True)

        logger.debug(f"Granting all privileges to: {username}")
        self.wordops.run_command(f"mysql -e {shlex.quote(grant_sql)}", check=True)

        logger.debug("Flushing privileges")
        self.wordops.run_command(f"mysql -e {shlex.quote(flush_sql)}", check=True)

        logger.info(f"MySQL user created successfully: {username}")

    def _create_database(self, db_name: str) -> None:
        """Create MySQL database.

        Args:
            db_name: Database name to create

        Raises:
            RuntimeError: If database creation fails
        """
        logger.info(f"Creating database: {db_name}")

        # Escape for shell
        db_name_escaped = shlex.quote(db_name)

        # Create database
        create_db_sql = (
            f"CREATE DATABASE IF NOT EXISTS {db_name_escaped} "
            f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
        )

        logger.debug(f"Creating database: {db_name}")
        self.wordops.run_command(f"mysql -e {shlex.quote(create_db_sql)}", check=True)

        logger.info(f"Database created successfully: {db_name}")

    def _create_tables(self, db_name: str, username: str, password: str) -> None:
        """Create tracking tables from SQL files.

        Args:
            db_name: Database name
            username: MySQL username
            password: MySQL password

        Raises:
            RuntimeError: If table creation fails
        """
        logger.info(f"Creating tracking tables in database: {db_name}")

        # SQL files on server in /shared/
        sql_files = [
            "/shared/tracking_pageviews.sql",
            "/shared/tracking_pageviews_daily.sql",
        ]

        for sql_file in sql_files:
            logger.debug(f"Executing SQL file: {sql_file}")

            sql_file_escaped = shlex.quote(sql_file)
            db_name_escaped = shlex.quote(db_name)
            username_escaped = shlex.quote(username)
            password_escaped = shlex.quote(password)

            # Execute SQL file using mysql command
            command = (
                f"mysql -u {username_escaped} -p{password_escaped} "
                f"{db_name_escaped} < {sql_file_escaped}"
            )

            self.wordops.run_command(command, check=True)
            logger.debug(f"SQL file executed successfully: {sql_file}")

        logger.info(f"Tracking tables created successfully in database: {db_name}")

    def _create_env_file(
        self, domain: str, db_name: str, username: str, password: str
    ) -> None:
        """Create .env file in site parent directory.

        Args:
            domain: Domain name (e.g., "example.com")
            db_name: Database name
            username: MySQL username
            password: MySQL password

        Raises:
            RuntimeError: If .env file creation fails
        """
        logger.info(f"Creating .env file for {domain}")

        # .env file path
        env_file_path = f"/var/www/{domain}/.env"

        # .env file content
        env_content = f"""TRACKING_ENABLED=true
TRACKING_DB_HOST=localhost
TRACKING_DB_NAME={db_name}
TRACKING_DB_USER={username}
TRACKING_DB_PASSWORD={password}
"""

        # Escape for shell
        env_file_path_escaped = shlex.quote(env_file_path)
        env_content_escaped = shlex.quote(env_content)

        # Create .env file
        logger.debug(f"Creating .env file at: {env_file_path}")
        command = f"echo {env_content_escaped} > {env_file_path_escaped}"
        self.wordops.run_command(command, check=True)

        logger.info(f".env file created successfully at: {env_file_path}")

    def _install_plugins(self, domain: str) -> None:
        """Install and activate tracking plugins.

        Installs:
        - /shared/pageview-tracking-core.zip
        - /shared/pageview-tracking.zip
        - /shared/pageview-tracking-daily.zip

        Args:
            domain: Domain name

        Raises:
            RuntimeError: If plugin installation fails
        """
        logger.info(f"Installing tracking plugins for {domain}")

        # Plugin paths
        plugins = [
            "/shared/pageview-tracking-core.zip",
            "/shared/pageview-tracking.zip",
            "/shared/pageview-tracking-daily.zip",
        ]

        # Install and activate each plugin
        for plugin in plugins:
            plugin_escaped = shlex.quote(plugin)
            logger.debug(f"Installing plugin: {plugin}")

            command = (
                f"cd /var/www/{domain}/htdocs && "
                f"wp plugin install {plugin_escaped} --activate --allow-root"
            )

            self.wordops.run_command(command, check=True)
            logger.debug(f"Plugin installed and activated: {plugin}")

        logger.info(f"All tracking plugins installed successfully for {domain}")

    def _update_track_config(self, domain: str) -> None:
        """Update track_config.php with settings from .env file.

        Reads configuration from .env file and updates the track_config.php
        file in the pageview-tracking-core plugin.

        Environment variables:
        - TRACKING_DB_CONFIG_FILE: Database config file path (string)
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
        db_config_file = os.getenv("TRACKING_DB_CONFIG_FILE", "auto")
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
 * Database configuration and exclude IP and user agent settings.
 */

return [
    /**
     * Database configuration file path.
     *
     * Options:
     * - 'auto' (default): Auto-detect WordPress wp-config.php, then fallback to .env
     * - Relative path to wp-config.php: '../../../wp-config.php' (WordPress plugin context)
     * - Relative path to .env file: '../../../.env'
     *
     * Paths are resolved relative to this config file's directory.
     */
    'db_config_file' => '{db_config_file}',

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
            f"pageview-tracking-core/track_config.php"
        )
        config_file_escaped = shlex.quote(config_file_path)
        php_config_escaped = shlex.quote(php_config)

        logger.debug(f"Writing track_config.php: {config_file_path}")
        command = f"echo {php_config_escaped} > {config_file_escaped}"
        self.wordops.run_command(command, check=True)

        logger.info(f"track_config.php updated successfully for {domain}")

    def setup_tracking(self, domain: str) -> None:
        """Setup complete pageview tracking system for a domain.

        This method:
        - Uploads tracking resources to /shared/ (plugins and SQL files)
        - Creates MySQL database user (from env or default 'db_admin')
        - Creates database (from env or default 'site_automator')
        - Creates tracking tables from SQL files
        - Creates .env file in site parent directory
        - Installs and activates tracking plugins
        - Updates track_config.php with settings from .env

        Environment variables (optional):
        - TRACKING_DB_NAME: Database name (default: 'site_automator')
        - TRACKING_DB_USER: MySQL username (default: 'db_admin')
        - TRACKING_DB_PASSWORD: MySQL password (default: random 32-char alphanumeric)

        Args:
            domain: Domain name of the site (e.g., "example.com")

        Raises:
            RuntimeError: If setup fails
        """
        import os

        logger.info(f"Setting up pageview tracking for {domain}")

        # Upload tracking resources
        self._upload_tracking_resources()

        # Read configuration from environment with defaults
        db_name = os.getenv("TRACKING_DB_NAME") or "site_automator"
        username = os.getenv("TRACKING_DB_USER") or "db_admin"
        password = os.getenv("TRACKING_DB_PASSWORD")

        # Generate password if not provided
        if not password:
            logger.debug("Generating random password for database user")
            alphabet = string.ascii_letters + string.digits
            password = "".join(secrets.choice(alphabet) for _ in range(32))

        # Create MySQL user
        self._create_db_user(username, password)

        # Create database
        self._create_database(db_name)

        # Create tables
        self._create_tables(db_name, username, password)

        # Create .env file
        self._create_env_file(domain, db_name, username, password)

        # Install and activate plugins
        self._install_plugins(domain)

        # Update track_config.php
        self._update_track_config(domain)

        logger.info(f"Pageview tracking setup completed successfully for {domain}")
