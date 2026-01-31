import pytest


class TestWp:
    """Test wp method."""

    def test_wp_success(self, wordpress, mock_ssh_client):
        """Test wp() executes WP-CLI command successfully."""
        mock_ssh_client._mock_stdout.read.return_value = b"6.9"

        output, exit_code = wordpress.wp("example.com", "core version")

        assert output == "6.9"
        assert exit_code == 0
        mock_ssh_client.exec_command.assert_called_with(
            "cd /var/www/example.com/htdocs && wp core version --allow-root"
        )

    def test_wp_failure_raises(self, wordpress, mock_ssh_client):
        """Test wp() raises exception on failure when check=True."""
        mock_ssh_client._mock_channel.recv_exit_status.return_value = 1
        mock_ssh_client._mock_stdout.read.return_value = b""
        mock_ssh_client._mock_stderr.read.return_value = (
            b"Error: This does not seem to be a WordPress installation."
        )

        with pytest.raises(RuntimeError):
            wordpress.wp("example.com", "core version")

    def test_wp_failure_without_check(self, wordpress, mock_ssh_client):
        """Test wp() returns exit code without raising when check=False."""
        mock_ssh_client._mock_channel.recv_exit_status.return_value = 1
        mock_ssh_client._mock_stdout.read.return_value = b""
        mock_ssh_client._mock_stderr.read.return_value = b"Error"

        output, exit_code = wordpress.wp("example.com", "core version", check=False)

        assert exit_code == 1
        assert "Error" in output


class TestSiteExists:
    """Test site_exists method."""

    def test_site_exists_returns_true(self, wordpress, mock_ssh_client):
        """Test site_exists returns True when WordPress is installed."""
        mock_ssh_client._mock_stdout.read.return_value = b""

        result = wordpress.site_exists("example.com")

        assert result is True
        mock_ssh_client.exec_command.assert_called_with(
            "cd /var/www/example.com/htdocs && wp core is-installed --allow-root"
        )

    def test_site_exists_returns_false(self, wordpress, mock_ssh_client):
        """Test site_exists returns False when WordPress is not installed."""
        mock_ssh_client._mock_channel.recv_exit_status.return_value = 1
        mock_ssh_client._mock_stdout.read.return_value = b""

        result = wordpress.site_exists("nonexistent.com")

        assert result is False


class TestConfigureSite:
    """Test configure_site method."""

    def test_configure_site_success(self, wordpress, mock_ssh_client):
        """Test configure_site updates all settings."""
        wordpress.configure_site(
            "test.com",
            "My Site",
            "My Description",
            timezone="America/New_York",
            public=False,
            permalink_structure="/%year%/%postname%/",
        )

        # Verify all wp commands were called
        calls = mock_ssh_client.exec_command.call_args_list
        call_commands = [call[0][0] for call in calls]

        # Check that all expected commands were executed
        assert any("option update blogname" in cmd for cmd in call_commands)
        assert any("option update blogdescription" in cmd for cmd in call_commands)
        assert any("option update timezone_string" in cmd for cmd in call_commands)
        assert any("option update blog_public 0" in cmd for cmd in call_commands)
        assert any("rewrite structure" in cmd for cmd in call_commands)

    def test_configure_site_with_defaults(self, wordpress, mock_ssh_client):
        """Test configure_site with default parameters."""
        wordpress.configure_site("test.com", "My Site", "My Description")

        # Verify default values were used
        calls = mock_ssh_client.exec_command.call_args_list
        call_commands = [call[0][0] for call in calls]

        assert any(
            "option update timezone_string" in cmd and "UTC" in cmd
            for cmd in call_commands
        )
        assert any("blog_public 1" in cmd for cmd in call_commands)
        assert any(
            "rewrite structure" in cmd and "/%postname%/" in cmd
            for cmd in call_commands
        )

    def test_configure_site_failure_raises(self, wordpress, mock_ssh_client):
        """Test configure_site raises on failure."""
        mock_ssh_client._mock_channel.recv_exit_status.return_value = 1
        mock_ssh_client._mock_stderr.read.return_value = b"error"

        with pytest.raises(RuntimeError):
            wordpress.configure_site("test.com", "My Site", "Description")


class TestSyncAdminPasswordToDb:
    """Test sync_admin_password_to_db method."""

    def test_sync_admin_password_to_db_success(self, wordpress, mock_ssh_client):
        """Test sync_admin_password_to_db updates admin password to DB_PASSWORD."""
        # First call returns DB_PASSWORD, second call updates user
        mock_ssh_client._mock_stdout.read.side_effect = [
            b"MyDbPassword123",  # eval 'echo DB_PASSWORD;'
            b"Success: Updated user 1.",  # user update
        ]

        wordpress.sync_admin_password_to_db("test.com")

        # Verify commands were called
        calls = mock_ssh_client.exec_command.call_args_list
        call_commands = [call[0][0] for call in calls]

        assert len(call_commands) == 2
        assert "eval 'echo DB_PASSWORD;'" in call_commands[0]
        assert "user update 1" in call_commands[1]
        assert "--user_pass=MyDbPassword123" in call_commands[1]
        assert "--skip-email" in call_commands[1]


class TestCreateRobotsTxt:
    """Test create_robots_txt method."""

    def test_create_robots_txt(self, wordpress, mock_ssh_client):
        """Test create_robots_txt writes correct content."""
        wordpress.create_robots_txt("test.com")

        call_args = mock_ssh_client.exec_command.call_args[0][0]
        assert "/var/www/test.com/htdocs/robots.txt" in call_args
        assert "User-agent: *" in call_args
        assert "Disallow: /wp-admin/" in call_args
        assert "Allow: /wp-admin/admin-ajax.php" in call_args
        assert "Sitemap: https://test.com/wp-sitemap.xml" in call_args


class TestDeleteDemoContent:
    """Test delete_demo_content method."""

    def test_delete_demo_content_success(self, wordpress, mock_ssh_client):
        """Test delete_demo_content deletes all demo content."""
        wordpress.delete_demo_content("test.com")

        # Verify all delete commands were called
        calls = mock_ssh_client.exec_command.call_args_list
        call_commands = [call[0][0] for call in calls]

        # Check that all expected delete commands were executed
        assert any("post delete 1 --force" in cmd for cmd in call_commands)
        assert any("post delete 2 --force" in cmd for cmd in call_commands)
        assert any("post delete 3 --force" in cmd for cmd in call_commands)
        assert any("comment delete 1 --force" in cmd for cmd in call_commands)

    def test_delete_demo_content_idempotent(self, wordpress, mock_ssh_client):
        """Test delete_demo_content is idempotent (handles already deleted content)."""
        # Return exit code 1 (content not found) for all delete commands
        mock_ssh_client._mock_channel.recv_exit_status.return_value = 1
        mock_ssh_client._mock_stdout.read.return_value = b"Warning: Failed deleting"

        # Should not raise even if content doesn't exist
        wordpress.delete_demo_content("test.com")


class TestCreatePost:
    """Test create_post method."""

    def test_create_post_success(self, wordpress, mock_ssh_client):
        """Test create_post returns post ID."""
        mock_ssh_client._mock_stdout.read.return_value = b"123"

        post_id = wordpress.create_post("test.com", "Test Title", "Test Content")

        assert post_id == 123

    def test_create_post_with_all_parameters(self, wordpress, mock_ssh_client):
        """Test create_post with all optional parameters."""
        mock_ssh_client._mock_stdout.read.return_value = b"456"

        post_id = wordpress.create_post(
            "test.com",
            "Test Post",
            "Content",
            status="draft",
            post_type="page",
            author="admin",
            date="2024-01-01 12:00:00",
            slug="test-slug",
            additional_flags=["--meta_input='key=value'"],
        )

        assert post_id == 456
        # Verify command includes all parameters
        call_args = mock_ssh_client.exec_command.call_args[0][0]
        assert "--post_type=page" in call_args
        assert "--post_author=admin" in call_args
        assert "--post_date='2024-01-01 12:00:00'" in call_args
        assert "--post_name=test-slug" in call_args
        assert "--meta_input='key=value'" in call_args

    def test_create_post_with_post_type(self, wordpress, mock_ssh_client):
        """Test create_post with post_type parameter."""
        mock_ssh_client._mock_stdout.read.return_value = b"789"

        post_id = wordpress.create_post(
            "test.com", "Page Title", "Content", post_type="page"
        )

        assert post_id == 789
        call_args = mock_ssh_client.exec_command.call_args[0][0]
        assert "--post_type=page" in call_args

    def test_create_post_with_additional_flags(self, wordpress, mock_ssh_client):
        """Test create_post with additional_flags parameter."""
        mock_ssh_client._mock_stdout.read.return_value = b"999"

        post_id = wordpress.create_post(
            "test.com",
            "Title",
            "Content",
            additional_flags=["--comment_status=closed", "--ping_status=closed"],
        )

        assert post_id == 999
        call_args = mock_ssh_client.exec_command.call_args[0][0]
        assert "--comment_status=closed" in call_args
        assert "--ping_status=closed" in call_args

    def test_create_post_failure_raises(self, wordpress, mock_ssh_client):
        """Test create_post raises on failure."""
        mock_ssh_client._mock_channel.recv_exit_status.return_value = 1
        mock_ssh_client._mock_stderr.read.return_value = b"error"

        with pytest.raises(RuntimeError):
            wordpress.create_post("test.com", "Title", "Content")


class TestEnsureAttachment:
    """Test ensure_attachment method."""

    def test_ensure_attachment_creates_new(self, wordpress, mock_ssh_client):
        """Test ensure_attachment imports new attachment when none exists."""
        # First call: search returns empty (no existing attachment)
        # Second call: import returns attachment ID
        # Third call: add meta
        call_count = [0]

        def mock_recv_exit_status():
            call_count[0] += 1
            return 0

        mock_ssh_client._mock_channel.recv_exit_status = mock_recv_exit_status

        def mock_read():
            if call_count[0] == 1:
                return b""  # Search returns empty
            elif call_count[0] == 2:
                return b"123"  # Import returns ID
            else:
                return b"output"

        mock_ssh_client._mock_stdout.read = mock_read

        attachment_id = wordpress.ensure_attachment(
            "test.com", "/path/to/image.jpg", title="Test Image"
        )

        assert attachment_id == 123
        assert mock_ssh_client.exec_command.call_count == 3

    def test_ensure_attachment_returns_existing(self, wordpress, mock_ssh_client):
        """Test ensure_attachment returns existing attachment ID."""
        mock_ssh_client._mock_stdout.read.return_value = (
            b"456"  # Existing attachment ID
        )

        attachment_id = wordpress.ensure_attachment("test.com", "/path/to/image.jpg")

        assert attachment_id == 456
        # Should only call search, not import
        assert mock_ssh_client.exec_command.call_count == 1

    def test_ensure_attachment_failure_raises(self, wordpress, mock_ssh_client):
        """Test ensure_attachment raises on import failure."""
        from unittest.mock import Mock

        call_count = [0]

        def mock_exec_command(cmd):
            call_count[0] += 1

            mock_stdout = Mock()
            mock_stderr = Mock()
            mock_channel = Mock()
            mock_stdout.channel = mock_channel

            if call_count[0] == 1:
                # Search succeeds, returns empty
                mock_channel.recv_exit_status.return_value = 0
                mock_stdout.read.return_value = b""
                mock_stderr.read.return_value = b""
            else:
                # Import fails
                mock_channel.recv_exit_status.return_value = 1
                mock_stdout.read.return_value = b"output"
                mock_stderr.read.return_value = b"error"

            return (None, mock_stdout, mock_stderr)

        mock_ssh_client.exec_command.side_effect = mock_exec_command

        with pytest.raises(RuntimeError):
            wordpress.ensure_attachment("test.com", "/path/to/image.jpg")


class TestSetFeaturedImage:
    """Test set_featured_image method."""

    def test_set_featured_image_success(self, wordpress, mock_ssh_client):
        """Test set_featured_image sets _thumbnail_id meta."""
        wordpress.set_featured_image("test.com", post_id=123, attachment_id=456)

        # Verify wp post meta update was called
        call_args = mock_ssh_client.exec_command.call_args[0][0]
        assert "post meta update 123 _thumbnail_id 456" in call_args

    def test_set_featured_image_failure_raises(self, wordpress, mock_ssh_client):
        """Test set_featured_image raises on failure."""
        mock_ssh_client._mock_channel.recv_exit_status.return_value = 1
        mock_ssh_client._mock_stderr.read.return_value = b"error"

        with pytest.raises(RuntimeError):
            wordpress.set_featured_image("test.com", post_id=123, attachment_id=456)


class TestInstallPlugins:
    """Test install_plugins method."""

    def test_install_single_plugin_slug(self, wordpress, mock_ssh_client):
        """Test installing a single plugin from slug."""
        wordpress.install_plugins("test.com", ["akismet"], activate=True)

        call_args = mock_ssh_client.exec_command.call_args[0][0]
        assert "plugin install" in call_args
        assert "akismet" in call_args
        assert "--activate" in call_args

    def test_install_multiple_plugins(self, wordpress, mock_ssh_client):
        """Test installing multiple plugins at once."""
        wordpress.install_plugins("test.com", ["akismet", "jetpack"], activate=True)

        call_args = mock_ssh_client.exec_command.call_args[0][0]
        assert "plugin install" in call_args
        assert "akismet" in call_args
        assert "jetpack" in call_args

    def test_install_plugin_from_path(self, wordpress, mock_ssh_client):
        """Test installing a plugin from file path."""
        wordpress.install_plugins("test.com", ["/shared/plugin.zip"], activate=True)

        call_args = mock_ssh_client.exec_command.call_args[0][0]
        assert "plugin install" in call_args
        assert "/shared/plugin.zip" in call_args

    def test_install_without_activation(self, wordpress, mock_ssh_client):
        """Test installing plugins without activation."""
        wordpress.install_plugins("test.com", ["akismet"], activate=False)

        call_args = mock_ssh_client.exec_command.call_args[0][0]
        assert "plugin install" in call_args
        assert "--activate" not in call_args

    def test_install_empty_list_returns_early(self, wordpress, mock_ssh_client):
        """Test that empty plugin list returns without calling wp."""
        wordpress.install_plugins("test.com", [])

        # Should not call exec_command for wp (only for SSH connection)
        assert mock_ssh_client.exec_command.call_count == 0


class TestActivatePlugins:
    """Test activate_plugins method."""

    def test_activate_single_plugin(self, wordpress, mock_ssh_client):
        """Test activating a single plugin."""
        wordpress.activate_plugins("test.com", ["akismet"])

        call_args = mock_ssh_client.exec_command.call_args[0][0]
        assert "plugin activate" in call_args
        assert "akismet" in call_args

    def test_activate_multiple_plugins(self, wordpress, mock_ssh_client):
        """Test activating multiple plugins."""
        wordpress.activate_plugins("test.com", ["akismet", "jetpack"])

        call_args = mock_ssh_client.exec_command.call_args[0][0]
        assert "plugin activate" in call_args
        assert "akismet" in call_args
        assert "jetpack" in call_args

    def test_activate_empty_list_returns_early(self, wordpress, mock_ssh_client):
        """Test that empty plugin list returns without calling wp."""
        wordpress.activate_plugins("test.com", [])

        assert mock_ssh_client.exec_command.call_count == 0


class TestDeactivatePlugins:
    """Test deactivate_plugins method."""

    def test_deactivate_single_plugin(self, wordpress, mock_ssh_client):
        """Test deactivating a single plugin."""
        wordpress.deactivate_plugins("test.com", ["akismet"])

        call_args = mock_ssh_client.exec_command.call_args[0][0]
        assert "plugin deactivate" in call_args
        assert "akismet" in call_args

    def test_deactivate_multiple_plugins(self, wordpress, mock_ssh_client):
        """Test deactivating multiple plugins."""
        wordpress.deactivate_plugins("test.com", ["akismet", "jetpack"])

        call_args = mock_ssh_client.exec_command.call_args[0][0]
        assert "plugin deactivate" in call_args
        assert "akismet" in call_args
        assert "jetpack" in call_args

    def test_deactivate_empty_list_returns_early(self, wordpress, mock_ssh_client):
        """Test that empty plugin list returns without calling wp."""
        wordpress.deactivate_plugins("test.com", [])

        assert mock_ssh_client.exec_command.call_count == 0


class TestDeactivateAllPlugins:
    """Test deactivate_all_plugins method."""

    def test_deactivate_all_without_exclude(self, wordpress, mock_ssh_client):
        """Test deactivating all plugins without exclusions."""
        wordpress.deactivate_all_plugins("test.com")

        call_args = mock_ssh_client.exec_command.call_args[0][0]
        assert "plugin deactivate --all" in call_args
        assert "--exclude" not in call_args

    def test_deactivate_all_with_exclude(self, wordpress, mock_ssh_client):
        """Test deactivating all plugins with exclusions."""
        wordpress.deactivate_all_plugins("test.com", exclude=["akismet", "jetpack"])

        call_args = mock_ssh_client.exec_command.call_args[0][0]
        assert "plugin deactivate --all" in call_args
        assert "--exclude=" in call_args
        assert "akismet" in call_args
        assert "jetpack" in call_args

    def test_deactivate_all_with_empty_exclude(self, wordpress, mock_ssh_client):
        """Test deactivating all plugins with empty exclude list."""
        wordpress.deactivate_all_plugins("test.com", exclude=[])

        call_args = mock_ssh_client.exec_command.call_args[0][0]
        assert "plugin deactivate --all" in call_args
        # Empty exclude list should not add --exclude flag
        assert "--exclude" not in call_args


class TestInstallTheme:
    """Test install_theme method."""

    def test_install_theme_from_slug(self, wordpress, mock_ssh_client):
        """Test installing a theme from slug."""
        wordpress.install_theme("test.com", "twentytwentyfour", activate=True)

        call_args = mock_ssh_client.exec_command.call_args[0][0]
        assert "theme install" in call_args
        assert "twentytwentyfour" in call_args
        assert "--activate" in call_args

    def test_install_theme_from_path(self, wordpress, mock_ssh_client):
        """Test installing a theme from file path."""
        wordpress.install_theme("test.com", "/shared/astra.zip", activate=True)

        call_args = mock_ssh_client.exec_command.call_args[0][0]
        assert "theme install" in call_args
        assert "/shared/astra.zip" in call_args
        assert "--activate" in call_args

    def test_install_theme_without_activation(self, wordpress, mock_ssh_client):
        """Test installing theme without activation."""
        wordpress.install_theme("test.com", "astra", activate=False)

        call_args = mock_ssh_client.exec_command.call_args[0][0]
        assert "theme install" in call_args
        assert "--activate" not in call_args


class TestActivateTheme:
    """Test activate_theme method."""

    def test_activate_theme(self, wordpress, mock_ssh_client):
        """Test activating a theme."""
        wordpress.activate_theme("test.com", "astra")

        call_args = mock_ssh_client.exec_command.call_args[0][0]
        assert "theme activate" in call_args
        assert "astra" in call_args


class TestDeleteThemes:
    """Test delete_themes method."""

    def test_delete_single_theme(self, wordpress, mock_ssh_client):
        """Test deleting a single theme."""
        wordpress.delete_themes("test.com", ["twentytwentythree"])

        call_args = mock_ssh_client.exec_command.call_args[0][0]
        assert "theme delete" in call_args
        assert "twentytwentythree" in call_args

    def test_delete_multiple_themes(self, wordpress, mock_ssh_client):
        """Test deleting multiple themes."""
        wordpress.delete_themes("test.com", ["twentytwentythree", "twentytwentyfour"])

        call_args = mock_ssh_client.exec_command.call_args[0][0]
        assert "theme delete" in call_args
        assert "twentytwentythree" in call_args
        assert "twentytwentyfour" in call_args

    def test_delete_empty_list_returns_early(self, wordpress, mock_ssh_client):
        """Test that empty theme list returns without calling wp."""
        wordpress.delete_themes("test.com", [])

        assert mock_ssh_client.exec_command.call_count == 0


class TestDisableComments:
    """Test disable_comments method."""

    def test_disable_comments(self, wordpress, mock_ssh_client):
        """Test disabling comments site-wide."""
        wordpress.disable_comments("test.com")

        # Verify all four commands were called
        calls = mock_ssh_client.exec_command.call_args_list
        call_commands = [call[0][0] for call in calls]

        # Check default_comment_status was set to closed
        assert any(
            "option update default_comment_status closed" in cmd
            for cmd in call_commands
        )

        # Check default_ping_status was set to closed
        assert any(
            "option update default_ping_status closed" in cmd for cmd in call_commands
        )

        # Check that existing posts were updated
        assert any("post list --format=ids" in cmd for cmd in call_commands)

        # Check comment_registration was set to 1 (require login)
        assert any(
            "option update comment_registration 1" in cmd for cmd in call_commands
        )


class TestDisableCommentsWithPlugin:
    """Test disable_comments_with_plugin method."""

    def test_disable_comments_with_plugin_from_slug(self, wordpress, mock_ssh_client):
        """Test disabling comments with plugin from WordPress.org slug."""
        wordpress.disable_comments_with_plugin("test.com")

        # Verify commands were called
        calls = mock_ssh_client.exec_command.call_args_list
        call_commands = [call[0][0] for call in calls]

        # Check plugin was installed
        assert any(
            "plugin install" in cmd and "disable-comments" in cmd
            for cmd in call_commands
        )

        # Check plugin was configured
        assert any(
            "disable-comments settings --types=all" in cmd for cmd in call_commands
        )

    def test_disable_comments_with_plugin_from_path(self, wordpress, mock_ssh_client):
        """Test disabling comments with plugin from file path."""
        wordpress.disable_comments_with_plugin(
            "test.com", plugin_path="/shared/disable-comments.2.6.1.zip"
        )

        # Verify commands were called
        calls = mock_ssh_client.exec_command.call_args_list
        call_commands = [call[0][0] for call in calls]

        # Check plugin was installed from path
        assert any(
            "plugin install" in cmd and "/shared/disable-comments.2.6.1.zip" in cmd
            for cmd in call_commands
        )

        # Check plugin was configured
        assert any(
            "disable-comments settings --types=all" in cmd for cmd in call_commands
        )


class TestDeleteWidgets:
    """Test delete_widgets method."""

    def test_delete_single_widget(self, wordpress, mock_ssh_client):
        """Test deleting a single widget."""
        wordpress.delete_widgets("test.com", ["block-3"])

        call_args = mock_ssh_client.exec_command.call_args[0][0]
        assert "widget delete" in call_args
        assert "block-3" in call_args

    def test_delete_multiple_widgets(self, wordpress, mock_ssh_client):
        """Test deleting multiple widgets."""
        wordpress.delete_widgets("test.com", ["block-3", "block-4"])

        call_args = mock_ssh_client.exec_command.call_args[0][0]
        assert "widget delete" in call_args
        assert "block-3" in call_args
        assert "block-4" in call_args

    def test_delete_empty_list_returns_early(self, wordpress, mock_ssh_client):
        """Test that empty widget list returns without calling wp."""
        wordpress.delete_widgets("test.com", [])

        assert mock_ssh_client.exec_command.call_count == 0


class TestWipeSite:
    """Test wipe_site method."""

    def test_wipe_site_without_confirm_raises(self, wordpress, mock_ssh_client):
        """Test wipe_site raises ValueError when confirm is not True."""
        with pytest.raises(ValueError, match="confirm=True"):
            wordpress.wipe_site("test.com")

        assert mock_ssh_client.exec_command.call_count == 0

    def test_wipe_site_with_confirm(self, wordpress, mock_ssh_client):
        """Test wipe_site executes db reset and rm."""
        wordpress.wipe_site("test.com", confirm=True)

        calls = mock_ssh_client.exec_command.call_args_list
        call_commands = [call[0][0] for call in calls]

        assert len(call_commands) == 2
        assert "db reset --yes" in call_commands[0]
        assert "rm -rf /var/www/test.com/htdocs/*" in call_commands[1]
