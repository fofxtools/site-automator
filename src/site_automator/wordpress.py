"""WordPress Deployer - Deploy WordPress sites using WP-CLI."""

import logging

from site_automator.wordops import WordOpsProvisioner

logger = logging.getLogger(__name__)


class WordPressDeployer:
    """Deploy WordPress sites using WP-CLI."""

    wordops: WordOpsProvisioner

    def __init__(self, wordops: WordOpsProvisioner) -> None:
        """Initialize WordPressDeployer.

        Args:
            wordops: WordOpsProvisioner instance
        """
        self.wordops = wordops

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
        return self.wordops.run_command(command, check=check)

    def site_exists(self, domain: str) -> bool:
        """Check if WordPress is installed for the domain.

        Args:
            domain: Domain name to check

        Returns:
            True if WordPress is installed, False otherwise
        """
        _, exit_code = self.wp(domain, "core is-installed", check=False)
        return exit_code == 0

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

    def sync_admin_password_to_db(self, domain: str) -> None:
        """Update WordPress admin password to match DB_PASSWORD from wp-config.php.

        Sets the password for user ID 1 (admin) to the same value as DB_PASSWORD.

        Args:
            domain: Domain name of the site

        Raises:
            RuntimeError: If password update fails
        """
        import shlex

        logger.info(f"Syncing admin password to DB_PASSWORD for {domain}")

        # Get DB_PASSWORD from wp-config.php
        output, _ = self.wp(domain, "eval 'echo DB_PASSWORD;'", check=True)
        db_password = output.strip()

        # Update admin password (skip-email to avoid prompts)
        self.wp(
            domain,
            f"user update 1 --user_pass={shlex.quote(db_password)} --skip-email",
            check=True,
        )

        logger.info(f"Admin password synced successfully for {domain}")

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

    def install_plugins(
        self,
        domain: str,
        plugins: list[str],
        activate: bool = True,
    ) -> None:
        """Install WordPress plugins from slugs or local paths.

        Args:
            domain: Domain name of the site
            plugins: List of plugin slugs (e.g., "akismet") or file paths
                    (e.g., "/shared/plugin.zip"). WP-CLI accepts both.
            activate: Whether to activate plugins after installation (default: True)

        Raises:
            RuntimeError: If plugin installation fails

        Note:
            WP-CLI automatically detects whether each argument is a slug or path.
        """
        import shlex

        if not plugins:
            logger.warning("No plugins specified for installation")
            return

        logger.info(f"Installing {len(plugins)} plugin(s) on {domain}")

        # Escape each plugin slug/path for shell safety
        escaped_plugins = [shlex.quote(plugin) for plugin in plugins]
        plugins_str = " ".join(escaped_plugins)

        # Build command
        cmd_parts = ["plugin install", plugins_str]
        if activate:
            cmd_parts.append("--activate")

        wp_command = " ".join(cmd_parts)

        logger.debug(f"Plugin install command: {wp_command}")
        output, _ = self.wp(domain, wp_command, check=True)
        logger.info(f"Plugins installed successfully: {', '.join(plugins)}")
        logger.debug(f"Escaped plugin args: {escaped_plugins}")
        logger.debug(f"Plugin install output:\n{output}")

    def activate_plugins(
        self,
        domain: str,
        plugins: list[str],
    ) -> None:
        """Activate WordPress plugins.

        Args:
            domain: Domain name of the site
            plugins: List of plugin slugs to activate (e.g., ["akismet", "jetpack"])
                    Note: Use plugin slugs, not file paths.

        Raises:
            RuntimeError: If plugin activation fails

        Note:
            This method expects plugin slugs (e.g., "akismet"), not file paths.
            If you installed from a path, use the resulting plugin slug for activation.
        """
        import shlex

        if not plugins:
            logger.warning("No plugins specified for activation")
            return

        logger.info(f"Activating {len(plugins)} plugin(s) on {domain}")

        # Escape each plugin slug for shell safety
        escaped_plugins = [shlex.quote(plugin) for plugin in plugins]
        plugins_str = " ".join(escaped_plugins)

        wp_command = f"plugin activate {plugins_str}"

        logger.debug(f"Plugin activate command: {wp_command}")
        output, _ = self.wp(domain, wp_command, check=True)
        logger.info(f"Plugins activated successfully: {', '.join(plugins)}")
        logger.debug(f"Escaped plugin args: {escaped_plugins}")
        logger.debug(f"Plugin activate output:\n{output}")

    def deactivate_plugins(
        self,
        domain: str,
        plugins: list[str],
    ) -> None:
        """Deactivate WordPress plugins.

        Args:
            domain: Domain name of the site
            plugins: List of plugin slugs to deactivate (e.g., ["akismet", "jetpack"])

        Raises:
            RuntimeError: If plugin deactivation fails
        """
        import shlex

        if not plugins:
            logger.warning("No plugins specified for deactivation")
            return

        logger.info(f"Deactivating {len(plugins)} plugin(s) on {domain}")

        # Escape each plugin slug for shell safety
        escaped_plugins = [shlex.quote(plugin) for plugin in plugins]
        plugins_str = " ".join(escaped_plugins)

        wp_command = f"plugin deactivate {plugins_str}"

        logger.debug(f"Plugin deactivate command: {wp_command}")
        output, _ = self.wp(domain, wp_command, check=True)
        logger.info(f"Plugins deactivated successfully: {', '.join(plugins)}")
        logger.debug(f"Escaped plugin args: {escaped_plugins}")
        logger.debug(f"Plugin deactivate output:\n{output}")

    def deactivate_all_plugins(
        self,
        domain: str,
        exclude: list[str] | None = None,
    ) -> None:
        """Deactivate all WordPress plugins, optionally excluding some.

        Args:
            domain: Domain name of the site
            exclude: Optional list of plugin slugs to exclude from deactivation

        Raises:
            RuntimeError: If plugin deactivation fails
        """
        import shlex

        logger.info(f"Deactivating all plugins on {domain}")

        cmd_parts = ["plugin deactivate --all"]
        escaped_exclude: list[str] = []

        if exclude:
            logger.info(f"Excluding {len(exclude)} plugin(s) from deactivation")
            escaped_exclude = [shlex.quote(plugin) for plugin in exclude]
            exclude_str = ",".join(escaped_exclude)
            cmd_parts.append(f"--exclude={exclude_str}")
            logger.debug(f"Excluded plugins: {exclude}")

        wp_command = " ".join(cmd_parts)

        logger.debug(f"Plugin deactivate command: {wp_command}")
        output, _ = self.wp(domain, wp_command, check=True)
        logger.info("All plugins deactivated successfully")
        if escaped_exclude:
            logger.debug(f"Escaped exclude args: {escaped_exclude}")
        logger.debug(f"Plugin deactivate output:\n{output}")

    def install_theme(
        self,
        domain: str,
        theme: str,
        activate: bool = True,
    ) -> None:
        """Install WordPress theme from slug or local path.

        Args:
            domain: Domain name of the site
            theme: Theme slug (e.g., "twentytwentyfour") or file path
                   (e.g., "/shared/astra.zip"). WP-CLI accepts both.
            activate: Whether to activate theme after installation (default: True)

        Raises:
            RuntimeError: If theme installation fails

        Note:
            WP-CLI automatically detects whether the argument is a slug or path.
        """
        import shlex

        logger.info(f"Installing theme on {domain}: {theme}")

        # Escape theme slug/path for shell safety
        escaped_theme = shlex.quote(theme)

        # Build command
        cmd_parts = ["theme install", escaped_theme]
        if activate:
            cmd_parts.append("--activate")

        wp_command = " ".join(cmd_parts)

        logger.debug(f"Theme install command: {wp_command}")
        output, _ = self.wp(domain, wp_command, check=True)
        logger.info(f"Theme installed successfully: {theme}")
        logger.debug(f"Escaped theme arg: {escaped_theme}")
        logger.debug(f"Theme install output:\n{output}")

    def activate_theme(
        self,
        domain: str,
        theme: str,
    ) -> None:
        """Activate WordPress theme.

        Args:
            domain: Domain name of the site
            theme: Theme slug to activate (e.g., "twentytwentyfour")
                   Note: Use theme slug, not file path.

        Raises:
            RuntimeError: If theme activation fails

        Note:
            This method expects a theme slug, not a file path.
        """
        import shlex

        logger.info(f"Activating theme on {domain}: {theme}")

        # Escape theme slug for shell safety
        escaped_theme = shlex.quote(theme)

        wp_command = f"theme activate {escaped_theme}"

        logger.debug(f"Theme activate command: {wp_command}")
        output, _ = self.wp(domain, wp_command, check=True)
        logger.info(f"Theme activated successfully: {theme}")
        logger.debug(f"Escaped theme arg: {escaped_theme}")
        logger.debug(f"Theme activate output:\n{output}")

    def delete_themes(
        self,
        domain: str,
        themes: list[str],
    ) -> None:
        """Delete WordPress themes.

        Args:
            domain: Domain name of the site
            themes: List of theme slugs to delete (e.g., ["twentytwentythree", "twentytwentyfour"])

        Raises:
            RuntimeError: If theme deletion fails (e.g., trying to delete active theme)

        Note:
            Active themes cannot be deleted and will cause WP-CLI to fail.
            This method fails fast in that case.
        """
        import shlex

        if not themes:
            logger.warning("No themes specified for deletion")
            return

        logger.info(f"Deleting {len(themes)} theme(s) on {domain}")

        # Escape each theme slug for shell safety
        escaped_themes = [shlex.quote(theme) for theme in themes]
        themes_str = " ".join(escaped_themes)

        wp_command = f"theme delete {themes_str}"

        logger.debug(f"Theme delete command: {wp_command}")
        output, _ = self.wp(domain, wp_command, check=True)
        logger.info(f"Themes deleted successfully: {', '.join(themes)}")
        logger.debug(f"Escaped theme args: {escaped_themes}")
        logger.debug(f"Theme delete output:\n{output}")

    def disable_comments(self, domain: str) -> None:
        """Disable comments site-wide on WordPress.

        This method:
        1. Disables comments on new posts/pages (default_comment_status)
        2. Disables pingbacks/trackbacks on new posts (default_ping_status)
        3. Closes comments on all existing posts and pages
        4. Requires users to be logged in to comment (comment_registration)

        Args:
            domain: Domain name of the site

        Raises:
            RuntimeError: If disabling comments fails

        Note:
            This is a destructive operation. Existing comments are not deleted,
            but commenting is disabled on all posts and pages.
            The comment_registration setting acts as a safety net to prevent
            anonymous comments even if themes override other settings.
        """
        logger.info(f"Disabling comments on {domain}")

        # Disable comments on new posts
        logger.debug("Setting default_comment_status to 'closed'")
        self.wp(domain, "option update default_comment_status closed", check=True)

        # Disable pingbacks/trackbacks on new posts
        logger.debug("Setting default_ping_status to 'closed'")
        self.wp(domain, "option update default_ping_status closed", check=True)

        # Close comments on all existing posts and pages
        logger.debug("Closing comments on all existing posts and pages")
        self.wp(
            domain,
            "post list --format=ids | xargs -r -d ' ' -I % wp post update % --comment_status=closed",
            check=True,
        )

        # Require users to be logged in to comment (safety net)
        logger.debug("Setting comment_registration to '1' (require login)")
        self.wp(domain, "option update comment_registration 1", check=True)

        logger.info(f"Comments disabled successfully on {domain}")

    def disable_comments_with_plugin(
        self, domain: str, plugin_path: str | None = None
    ) -> None:
        """Disable comments using the Disable Comments plugin.

        This method installs and configures the Disable Comments plugin to
        disable comments everywhere on the site.

        Args:
            domain: Domain name of the site
            plugin_path: Optional path to plugin zip file (e.g., "/shared/disable-comments.2.6.1.zip").
                        If not provided, installs from WordPress.org using slug "disable-comments".

        Raises:
            RuntimeError: If plugin installation or configuration fails
        """
        logger.info(f"Disabling comments with plugin on {domain}")

        # Install plugin
        plugin = plugin_path if plugin_path else "disable-comments"
        self.install_plugins(domain, [plugin], activate=True)

        # Disable comments everywhere
        logger.debug("Configuring plugin to disable comments everywhere")
        self.wp(domain, "disable-comments settings --types=all", check=True)

        logger.info(f"Comments disabled with plugin successfully on {domain}")
