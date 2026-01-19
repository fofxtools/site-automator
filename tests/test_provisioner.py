"""Unit tests for WordOpsProvisioner - Critical path only."""

import pytest
from unittest.mock import Mock, patch

from wordops_provisioner import WordOpsProvisioner


class TestInit:
    """Test __init__ and _connect methods."""

    @patch("wordops_provisioner.provisioner.paramiko.SSHClient")
    def test_init_stores_credentials(self, mock_ssh_client):
        """Test that credentials are stored correctly."""
        provisioner = WordOpsProvisioner(
            host="example.com", user="testuser", password="testpass"
        )

        assert provisioner.host == "example.com"
        assert provisioner.user == "testuser"
        assert provisioner.password == "testpass"

    @patch("wordops_provisioner.provisioner.paramiko.SSHClient")
    def test_init_connects_to_ssh(self, mock_ssh_client):
        """Test that SSH connection is established on init."""
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        _ = WordOpsProvisioner(host="example.com", user="root", password="pass")

        # Verify SSH client was created and configured
        mock_ssh_client.assert_called_once()
        mock_client_instance.set_missing_host_key_policy.assert_called_once()
        mock_client_instance.connect.assert_called_once_with(
            hostname="example.com", username="root", password="pass"
        )


class TestClose:
    """Test close method."""

    @patch("wordops_provisioner.provisioner.paramiko.SSHClient")
    def test_close_closes_client(self, mock_ssh_client):
        """Test that close() closes the SSH client."""
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        provisioner = WordOpsProvisioner(host="example.com", password="pass")
        provisioner.close()

        mock_client_instance.close.assert_called_once()
        assert provisioner._client is None

    @patch("wordops_provisioner.provisioner.paramiko.SSHClient")
    def test_close_handles_none_client(self, mock_ssh_client):
        """Test that close() handles None client gracefully."""
        provisioner = WordOpsProvisioner(host="example.com", password="pass")
        provisioner._client = None
        provisioner.close()  # Should not raise


class TestRunCommand:
    """Test run_command method."""

    @patch("wordops_provisioner.provisioner.paramiko.SSHClient")
    def test_run_command_success(self, mock_ssh_client):
        """Test successful command execution."""
        # Setup mock SSH client
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        # Setup mock command execution
        mock_stdout = Mock()
        mock_stderr = Mock()
        mock_channel = Mock()
        mock_stdout.channel = mock_channel
        mock_channel.recv_exit_status.return_value = 0
        mock_stdout.read.return_value = b"command output"
        mock_stderr.read.return_value = b""

        mock_client_instance.exec_command.return_value = (
            None,
            mock_stdout,
            mock_stderr,
        )

        provisioner = WordOpsProvisioner(host="example.com", password="pass")
        output, exit_code = provisioner.run_command("echo test")

        assert output == "command output"
        assert exit_code == 0
        mock_client_instance.exec_command.assert_called_with("echo test")

    @patch("wordops_provisioner.provisioner.paramiko.SSHClient")
    def test_run_command_failure_with_check(self, mock_ssh_client):
        """Test command failure raises exception when check=True."""
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        mock_stdout = Mock()
        mock_stderr = Mock()
        mock_channel = Mock()
        mock_stdout.channel = mock_channel
        mock_channel.recv_exit_status.return_value = 1
        mock_stdout.read.return_value = b"output"
        mock_stderr.read.return_value = b"error message"

        mock_client_instance.exec_command.return_value = (
            None,
            mock_stdout,
            mock_stderr,
        )

        provisioner = WordOpsProvisioner(host="example.com", password="pass")

        with pytest.raises(RuntimeError):
            provisioner.run_command("false", check=True)

    @patch("wordops_provisioner.provisioner.paramiko.SSHClient")
    def test_run_command_failure_without_check(self, mock_ssh_client):
        """Test command failure returns exit code when check=False."""
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        mock_stdout = Mock()
        mock_stderr = Mock()
        mock_channel = Mock()
        mock_stdout.channel = mock_channel
        mock_channel.recv_exit_status.return_value = 1
        mock_stdout.read.return_value = b"output"
        mock_stderr.read.return_value = b"error"

        mock_client_instance.exec_command.return_value = (
            None,
            mock_stdout,
            mock_stderr,
        )

        provisioner = WordOpsProvisioner(host="example.com", password="pass")
        output, exit_code = provisioner.run_command("false", check=False)

        assert exit_code == 1
        assert "error" in output

    @patch("wordops_provisioner.provisioner.paramiko.SSHClient")
    def test_run_command_no_client_raises(self, mock_ssh_client):
        """Test run_command raises when client is None."""
        provisioner = WordOpsProvisioner(host="example.com", password="pass")
        provisioner._client = None

        with pytest.raises(RuntimeError):
            provisioner.run_command("echo test")


class TestWp:
    """Test wp method."""

    @patch("wordops_provisioner.provisioner.paramiko.SSHClient")
    def test_wp_success(self, mock_ssh_client):
        """Test wp() executes WP-CLI command successfully."""
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        # Setup mock command execution
        mock_stdout = Mock()
        mock_stderr = Mock()
        mock_channel = Mock()
        mock_stdout.channel = mock_channel
        mock_channel.recv_exit_status.return_value = 0
        mock_stdout.read.return_value = b"6.9"
        mock_stderr.read.return_value = b""

        mock_client_instance.exec_command.return_value = (
            None,
            mock_stdout,
            mock_stderr,
        )

        provisioner = WordOpsProvisioner(host="example.com", password="pass")
        output, exit_code = provisioner.wp("example.com", "core version")

        assert output == "6.9"
        assert exit_code == 0
        mock_client_instance.exec_command.assert_called_with(
            "cd /var/www/example.com/htdocs && wp core version --allow-root"
        )

    @patch("wordops_provisioner.provisioner.paramiko.SSHClient")
    def test_wp_failure_raises(self, mock_ssh_client):
        """Test wp() raises exception on failure when check=True."""
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        mock_stdout = Mock()
        mock_stderr = Mock()
        mock_channel = Mock()
        mock_stdout.channel = mock_channel
        mock_channel.recv_exit_status.return_value = 1
        mock_stdout.read.return_value = b""
        mock_stderr.read.return_value = (
            b"Error: This does not seem to be a WordPress installation."
        )

        mock_client_instance.exec_command.return_value = (
            None,
            mock_stdout,
            mock_stderr,
        )

        provisioner = WordOpsProvisioner(host="example.com", password="pass")

        with pytest.raises(RuntimeError):
            provisioner.wp("example.com", "core version")

    @patch("wordops_provisioner.provisioner.paramiko.SSHClient")
    def test_wp_failure_without_check(self, mock_ssh_client):
        """Test wp() returns exit code without raising when check=False."""
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        mock_stdout = Mock()
        mock_stderr = Mock()
        mock_channel = Mock()
        mock_stdout.channel = mock_channel
        mock_channel.recv_exit_status.return_value = 1
        mock_stdout.read.return_value = b""
        mock_stderr.read.return_value = b"Error"

        mock_client_instance.exec_command.return_value = (
            None,
            mock_stdout,
            mock_stderr,
        )

        provisioner = WordOpsProvisioner(host="example.com", password="pass")
        output, exit_code = provisioner.wp("example.com", "core version", check=False)

        assert exit_code == 1
        assert "Error" in output


class TestSiteExists:
    """Test site_exists method."""

    @patch("wordops_provisioner.provisioner.paramiko.SSHClient")
    def test_site_exists_returns_true(self, mock_ssh_client):
        """Test site_exists returns True when WordPress is installed."""
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        # Mock successful wp core is-installed command (exit code 0)
        mock_stdout = Mock()
        mock_stderr = Mock()
        mock_channel = Mock()
        mock_stdout.channel = mock_channel
        mock_channel.recv_exit_status.return_value = 0
        mock_stdout.read.return_value = b""
        mock_stderr.read.return_value = b""

        mock_client_instance.exec_command.return_value = (
            None,
            mock_stdout,
            mock_stderr,
        )

        provisioner = WordOpsProvisioner(host="example.com", password="pass")
        result = provisioner.site_exists("example.com")

        assert result is True
        mock_client_instance.exec_command.assert_called_with(
            "cd /var/www/example.com/htdocs && wp core is-installed --allow-root"
        )

    @patch("wordops_provisioner.provisioner.paramiko.SSHClient")
    def test_site_exists_returns_false(self, mock_ssh_client):
        """Test site_exists returns False when WordPress is not installed."""
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        # Mock failed wp core is-installed command (exit code 1)
        mock_stdout = Mock()
        mock_stderr = Mock()
        mock_channel = Mock()
        mock_stdout.channel = mock_channel
        mock_channel.recv_exit_status.return_value = 1
        mock_stdout.read.return_value = b""
        mock_stderr.read.return_value = b""

        mock_client_instance.exec_command.return_value = (
            None,
            mock_stdout,
            mock_stderr,
        )

        provisioner = WordOpsProvisioner(host="example.com", password="pass")
        result = provisioner.site_exists("nonexistent.com")

        assert result is False


class TestCreateSite:
    """Test create_site method."""

    @patch("wordops_provisioner.provisioner.paramiko.SSHClient")
    def test_create_site_without_flags(self, mock_ssh_client):
        """Test create_site with no flags."""
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        mock_stdout = Mock()
        mock_stderr = Mock()
        mock_channel = Mock()
        mock_stdout.channel = mock_channel
        mock_channel.recv_exit_status.return_value = 0
        mock_stdout.read.return_value = b"Site created"
        mock_stderr.read.return_value = b""

        mock_client_instance.exec_command.return_value = (
            None,
            mock_stdout,
            mock_stderr,
        )

        provisioner = WordOpsProvisioner(host="example.com", password="pass")
        provisioner.create_site("test.com")

        mock_client_instance.exec_command.assert_called_with("wo site create test.com")

    @patch("wordops_provisioner.provisioner.paramiko.SSHClient")
    def test_create_site_with_flags(self, mock_ssh_client):
        """Test create_site with flags."""
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        mock_stdout = Mock()
        mock_stderr = Mock()
        mock_channel = Mock()
        mock_stdout.channel = mock_channel
        mock_channel.recv_exit_status.return_value = 0
        mock_stdout.read.return_value = b"Site created"
        mock_stderr.read.return_value = b""

        mock_client_instance.exec_command.return_value = (
            None,
            mock_stdout,
            mock_stderr,
        )

        provisioner = WordOpsProvisioner(host="example.com", password="pass")
        provisioner.create_site("test.com", flags=["--wp", "--php81"])

        mock_client_instance.exec_command.assert_called_with(
            "wo site create test.com --wp --php81"
        )

    @patch("wordops_provisioner.provisioner.paramiko.SSHClient")
    def test_create_site_failure_raises(self, mock_ssh_client):
        """Test create_site raises on failure."""
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        mock_stdout = Mock()
        mock_stderr = Mock()
        mock_channel = Mock()
        mock_stdout.channel = mock_channel
        mock_channel.recv_exit_status.return_value = 1
        mock_stdout.read.return_value = b"output"
        mock_stderr.read.return_value = b"error"

        mock_client_instance.exec_command.return_value = (
            None,
            mock_stdout,
            mock_stderr,
        )

        provisioner = WordOpsProvisioner(host="example.com", password="pass")

        with pytest.raises(RuntimeError):
            provisioner.create_site("test.com")


class TestConfigureSite:
    """Test configure_site method."""

    @patch("wordops_provisioner.provisioner.paramiko.SSHClient")
    def test_configure_site_success(self, mock_ssh_client):
        """Test configure_site updates all settings."""
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        mock_stdout = Mock()
        mock_stderr = Mock()
        mock_channel = Mock()
        mock_stdout.channel = mock_channel
        mock_channel.recv_exit_status.return_value = 0
        mock_stdout.read.return_value = b"Success"
        mock_stderr.read.return_value = b""

        mock_client_instance.exec_command.return_value = (
            None,
            mock_stdout,
            mock_stderr,
        )

        provisioner = WordOpsProvisioner(host="example.com", password="pass")
        provisioner.configure_site(
            "test.com",
            "My Site",
            "My Description",
            timezone="America/New_York",
            public=False,
            permalink_structure="/%year%/%postname%/",
        )

        # Verify all wp commands were called
        calls = mock_client_instance.exec_command.call_args_list
        call_commands = [call[0][0] for call in calls]

        # Check that all expected commands were executed
        assert any("option update blogname" in cmd for cmd in call_commands)
        assert any("option update blogdescription" in cmd for cmd in call_commands)
        assert any("option update timezone_string" in cmd for cmd in call_commands)
        assert any("option update blog_public 0" in cmd for cmd in call_commands)
        assert any("rewrite structure" in cmd for cmd in call_commands)

    @patch("wordops_provisioner.provisioner.paramiko.SSHClient")
    def test_configure_site_with_defaults(self, mock_ssh_client):
        """Test configure_site with default parameters."""
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        mock_stdout = Mock()
        mock_stderr = Mock()
        mock_channel = Mock()
        mock_stdout.channel = mock_channel
        mock_channel.recv_exit_status.return_value = 0
        mock_stdout.read.return_value = b"Success"
        mock_stderr.read.return_value = b""

        mock_client_instance.exec_command.return_value = (
            None,
            mock_stdout,
            mock_stderr,
        )

        provisioner = WordOpsProvisioner(host="example.com", password="pass")
        provisioner.configure_site("test.com", "My Site", "My Description")

        # Verify default values were used
        calls = mock_client_instance.exec_command.call_args_list
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

    @patch("wordops_provisioner.provisioner.paramiko.SSHClient")
    def test_configure_site_failure_raises(self, mock_ssh_client):
        """Test configure_site raises on failure."""
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        mock_stdout = Mock()
        mock_stderr = Mock()
        mock_channel = Mock()
        mock_stdout.channel = mock_channel
        mock_channel.recv_exit_status.return_value = 1
        mock_stdout.read.return_value = b"output"
        mock_stderr.read.return_value = b"error"

        mock_client_instance.exec_command.return_value = (
            None,
            mock_stdout,
            mock_stderr,
        )

        provisioner = WordOpsProvisioner(host="example.com", password="pass")

        with pytest.raises(RuntimeError):
            provisioner.configure_site("test.com", "My Site", "Description")


class TestDeleteDemoContent:
    """Test delete_demo_content method."""

    @patch("wordops_provisioner.provisioner.paramiko.SSHClient")
    def test_delete_demo_content_success(self, mock_ssh_client):
        """Test delete_demo_content deletes all demo content."""
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        mock_stdout = Mock()
        mock_stderr = Mock()
        mock_channel = Mock()
        mock_stdout.channel = mock_channel
        mock_channel.recv_exit_status.return_value = 0
        mock_stdout.read.return_value = b"Success"
        mock_stderr.read.return_value = b""

        mock_client_instance.exec_command.return_value = (
            None,
            mock_stdout,
            mock_stderr,
        )

        provisioner = WordOpsProvisioner(host="example.com", password="pass")
        provisioner.delete_demo_content("test.com")

        # Verify all delete commands were called
        calls = mock_client_instance.exec_command.call_args_list
        call_commands = [call[0][0] for call in calls]

        # Check that all expected delete commands were executed
        assert any("post delete 1 --force" in cmd for cmd in call_commands)
        assert any("post delete 2 --force" in cmd for cmd in call_commands)
        assert any("post delete 3 --force" in cmd for cmd in call_commands)
        assert any("comment delete 1 --force" in cmd for cmd in call_commands)

    @patch("wordops_provisioner.provisioner.paramiko.SSHClient")
    def test_delete_demo_content_idempotent(self, mock_ssh_client):
        """Test delete_demo_content is idempotent (handles already deleted content)."""
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        mock_stdout = Mock()
        mock_stderr = Mock()
        mock_channel = Mock()
        mock_stdout.channel = mock_channel
        # Return exit code 1 (content not found) for all delete commands
        mock_channel.recv_exit_status.return_value = 1
        mock_stdout.read.return_value = b"Warning: Failed deleting"
        mock_stderr.read.return_value = b""

        mock_client_instance.exec_command.return_value = (
            None,
            mock_stdout,
            mock_stderr,
        )

        provisioner = WordOpsProvisioner(host="example.com", password="pass")

        # Should not raise even if content doesn't exist
        provisioner.delete_demo_content("test.com")


class TestCreatePost:
    """Test create_post method."""

    @patch("wordops_provisioner.provisioner.paramiko.SSHClient")
    def test_create_post_success(self, mock_ssh_client):
        """Test create_post returns post ID."""
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        mock_stdout = Mock()
        mock_stderr = Mock()
        mock_channel = Mock()
        mock_stdout.channel = mock_channel
        mock_channel.recv_exit_status.return_value = 0
        mock_stdout.read.return_value = b"123"
        mock_stderr.read.return_value = b""

        mock_client_instance.exec_command.return_value = (
            None,
            mock_stdout,
            mock_stderr,
        )

        provisioner = WordOpsProvisioner(host="example.com", password="pass")
        post_id = provisioner.create_post("test.com", "Test Title", "Test Content")

        assert post_id == 123

    @patch("wordops_provisioner.provisioner.paramiko.SSHClient")
    def test_create_post_with_all_parameters(self, mock_ssh_client):
        """Test create_post with all optional parameters."""
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        mock_stdout = Mock()
        mock_stderr = Mock()
        mock_channel = Mock()
        mock_stdout.channel = mock_channel
        mock_channel.recv_exit_status.return_value = 0
        mock_stdout.read.return_value = b"456"
        mock_stderr.read.return_value = b""

        mock_client_instance.exec_command.return_value = (
            None,
            mock_stdout,
            mock_stderr,
        )

        provisioner = WordOpsProvisioner(host="example.com", password="pass")
        post_id = provisioner.create_post(
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
        call_args = mock_client_instance.exec_command.call_args[0][0]
        assert "--post_type=page" in call_args
        assert "--post_author=admin" in call_args
        assert "--post_date='2024-01-01 12:00:00'" in call_args
        assert "--post_name=test-slug" in call_args
        assert "--meta_input='key=value'" in call_args

    @patch("wordops_provisioner.provisioner.paramiko.SSHClient")
    def test_create_post_with_post_type(self, mock_ssh_client):
        """Test create_post with post_type parameter."""
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        mock_stdout = Mock()
        mock_stderr = Mock()
        mock_channel = Mock()
        mock_stdout.channel = mock_channel
        mock_channel.recv_exit_status.return_value = 0
        mock_stdout.read.return_value = b"789"
        mock_stderr.read.return_value = b""

        mock_client_instance.exec_command.return_value = (
            None,
            mock_stdout,
            mock_stderr,
        )

        provisioner = WordOpsProvisioner(host="example.com", password="pass")
        post_id = provisioner.create_post(
            "test.com", "Page Title", "Content", post_type="page"
        )

        assert post_id == 789
        call_args = mock_client_instance.exec_command.call_args[0][0]
        assert "--post_type=page" in call_args

    @patch("wordops_provisioner.provisioner.paramiko.SSHClient")
    def test_create_post_with_additional_flags(self, mock_ssh_client):
        """Test create_post with additional_flags parameter."""
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        mock_stdout = Mock()
        mock_stderr = Mock()
        mock_channel = Mock()
        mock_stdout.channel = mock_channel
        mock_channel.recv_exit_status.return_value = 0
        mock_stdout.read.return_value = b"999"
        mock_stderr.read.return_value = b""

        mock_client_instance.exec_command.return_value = (
            None,
            mock_stdout,
            mock_stderr,
        )

        provisioner = WordOpsProvisioner(host="example.com", password="pass")
        post_id = provisioner.create_post(
            "test.com",
            "Title",
            "Content",
            additional_flags=["--comment_status=closed", "--ping_status=closed"],
        )

        assert post_id == 999
        call_args = mock_client_instance.exec_command.call_args[0][0]
        assert "--comment_status=closed" in call_args
        assert "--ping_status=closed" in call_args

    @patch("wordops_provisioner.provisioner.paramiko.SSHClient")
    def test_create_post_failure_raises(self, mock_ssh_client):
        """Test create_post raises on failure."""
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        mock_stdout = Mock()
        mock_stderr = Mock()
        mock_channel = Mock()
        mock_stdout.channel = mock_channel
        mock_channel.recv_exit_status.return_value = 1
        mock_stdout.read.return_value = b"output"
        mock_stderr.read.return_value = b"error"

        mock_client_instance.exec_command.return_value = (
            None,
            mock_stdout,
            mock_stderr,
        )

        provisioner = WordOpsProvisioner(host="example.com", password="pass")

        with pytest.raises(RuntimeError):
            provisioner.create_post("test.com", "Title", "Content")


class TestEnsureAttachment:
    """Test ensure_attachment method."""

    @patch("wordops_provisioner.provisioner.paramiko.SSHClient")
    def test_ensure_attachment_creates_new(self, mock_ssh_client):
        """Test ensure_attachment imports new attachment when none exists."""
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        mock_stdout = Mock()
        mock_stderr = Mock()
        mock_channel = Mock()
        mock_stdout.channel = mock_channel
        mock_stdout.read.return_value = b"output"
        mock_stderr.read.return_value = b""

        # First call: search returns empty (no existing attachment)
        # Second call: import returns attachment ID
        # Third call: add meta
        call_count = [0]

        def mock_recv_exit_status():
            call_count[0] += 1
            return 0

        mock_channel.recv_exit_status = mock_recv_exit_status

        def mock_read():
            if call_count[0] == 1:
                return b""  # Search returns empty
            elif call_count[0] == 2:
                return b"123"  # Import returns ID
            else:
                return b"output"

        mock_stdout.read = mock_read

        mock_client_instance.exec_command.return_value = (
            None,
            mock_stdout,
            mock_stderr,
        )

        provisioner = WordOpsProvisioner(host="example.com", password="pass")

        attachment_id = provisioner.ensure_attachment(
            "test.com", "/path/to/image.jpg", title="Test Image"
        )

        assert attachment_id == 123
        assert mock_client_instance.exec_command.call_count == 3

    @patch("wordops_provisioner.provisioner.paramiko.SSHClient")
    def test_ensure_attachment_returns_existing(self, mock_ssh_client):
        """Test ensure_attachment returns existing attachment ID."""
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        mock_stdout = Mock()
        mock_stderr = Mock()
        mock_channel = Mock()
        mock_stdout.channel = mock_channel
        mock_channel.recv_exit_status.return_value = 0
        mock_stdout.read.return_value = b"456"  # Existing attachment ID
        mock_stderr.read.return_value = b""

        mock_client_instance.exec_command.return_value = (
            None,
            mock_stdout,
            mock_stderr,
        )

        provisioner = WordOpsProvisioner(host="example.com", password="pass")

        attachment_id = provisioner.ensure_attachment("test.com", "/path/to/image.jpg")

        assert attachment_id == 456
        # Should only call search, not import
        assert mock_client_instance.exec_command.call_count == 1

    @patch("wordops_provisioner.provisioner.paramiko.SSHClient")
    def test_ensure_attachment_failure_raises(self, mock_ssh_client):
        """Test ensure_attachment raises on import failure."""
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

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

        mock_client_instance.exec_command.side_effect = mock_exec_command

        provisioner = WordOpsProvisioner(host="example.com", password="pass")

        with pytest.raises(RuntimeError):
            provisioner.ensure_attachment("test.com", "/path/to/image.jpg")


class TestSetFeaturedImage:
    """Test set_featured_image method."""

    @patch("wordops_provisioner.provisioner.paramiko.SSHClient")
    def test_set_featured_image_success(self, mock_ssh_client):
        """Test set_featured_image sets _thumbnail_id meta."""
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        mock_stdout = Mock()
        mock_stderr = Mock()
        mock_channel = Mock()
        mock_stdout.channel = mock_channel
        mock_channel.recv_exit_status.return_value = 0
        mock_stdout.read.return_value = b"output"
        mock_stderr.read.return_value = b""

        mock_client_instance.exec_command.return_value = (
            None,
            mock_stdout,
            mock_stderr,
        )

        provisioner = WordOpsProvisioner(host="example.com", password="pass")

        provisioner.set_featured_image("test.com", post_id=123, attachment_id=456)

        # Verify wp post meta update was called
        call_args = mock_client_instance.exec_command.call_args[0][0]
        assert "post meta update 123 _thumbnail_id 456" in call_args

    @patch("wordops_provisioner.provisioner.paramiko.SSHClient")
    def test_set_featured_image_failure_raises(self, mock_ssh_client):
        """Test set_featured_image raises on failure."""
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        mock_stdout = Mock()
        mock_stderr = Mock()
        mock_channel = Mock()
        mock_stdout.channel = mock_channel
        mock_channel.recv_exit_status.return_value = 1
        mock_stdout.read.return_value = b"output"
        mock_stderr.read.return_value = b"error"

        mock_client_instance.exec_command.return_value = (
            None,
            mock_stdout,
            mock_stderr,
        )

        provisioner = WordOpsProvisioner(host="example.com", password="pass")

        with pytest.raises(RuntimeError):
            provisioner.set_featured_image("test.com", post_id=123, attachment_id=456)


class TestRestartNginx:
    """Test restart_nginx method."""

    @patch("wordops_provisioner.provisioner.paramiko.SSHClient")
    def test_restart_nginx_success(self, mock_ssh_client):
        """Test restart_nginx executes systemctl command."""
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        mock_stdout = Mock()
        mock_stderr = Mock()
        mock_channel = Mock()
        mock_stdout.channel = mock_channel
        mock_channel.recv_exit_status.return_value = 0
        mock_stdout.read.return_value = b""
        mock_stderr.read.return_value = b""

        mock_client_instance.exec_command.return_value = (
            None,
            mock_stdout,
            mock_stderr,
        )

        provisioner = WordOpsProvisioner(host="example.com", password="pass")
        provisioner.restart_nginx()

        mock_client_instance.exec_command.assert_called_with("systemctl restart nginx")

    @patch("wordops_provisioner.provisioner.paramiko.SSHClient")
    def test_restart_nginx_failure_raises(self, mock_ssh_client):
        """Test restart_nginx raises on failure."""
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        mock_stdout = Mock()
        mock_stderr = Mock()
        mock_channel = Mock()
        mock_stdout.channel = mock_channel
        mock_channel.recv_exit_status.return_value = 1
        mock_stdout.read.return_value = b"output"
        mock_stderr.read.return_value = b"error"

        mock_client_instance.exec_command.return_value = (
            None,
            mock_stdout,
            mock_stderr,
        )

        provisioner = WordOpsProvisioner(host="example.com", password="pass")

        with pytest.raises(RuntimeError):
            provisioner.restart_nginx()


class TestEnsureSSL:
    """Test ensure_ssl method."""

    @patch("wordops_provisioner.provisioner.paramiko.SSHClient")
    def test_ensure_ssl_already_enabled(self, mock_ssh_client):
        """Test ensure_ssl skips when SSL already enabled."""
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        # First call: check SSL exists (exit code 0)
        mock_stdout = Mock()
        mock_stderr = Mock()
        mock_channel = Mock()
        mock_stdout.channel = mock_channel
        mock_channel.recv_exit_status.return_value = 0
        mock_stdout.read.return_value = b""
        mock_stderr.read.return_value = b""

        mock_client_instance.exec_command.return_value = (
            None,
            mock_stdout,
            mock_stderr,
        )

        provisioner = WordOpsProvisioner(host="example.com", password="pass")
        provisioner.ensure_ssl("test.com")

        # Should only call the check command, not the update command
        mock_client_instance.exec_command.assert_called_once_with(
            "test -f /var/www/test.com/conf/nginx/ssl.conf"
        )

    @patch("wordops_provisioner.provisioner.paramiko.SSHClient")
    def test_ensure_ssl_enables_ssl(self, mock_ssh_client):
        """Test ensure_ssl enables SSL when not present."""
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        # Setup mock to return different values for different commands
        def exec_command_side_effect(command):
            mock_stdout = Mock()
            mock_stderr = Mock()
            mock_channel = Mock()
            mock_stdout.channel = mock_channel
            mock_stdout.read.return_value = b""
            mock_stderr.read.return_value = b""

            if "test -f" in command:
                # SSL check fails (not present)
                mock_channel.recv_exit_status.return_value = 1
            else:
                # SSL enable succeeds
                mock_channel.recv_exit_status.return_value = 0

            return None, mock_stdout, mock_stderr

        mock_client_instance.exec_command.side_effect = exec_command_side_effect

        provisioner = WordOpsProvisioner(host="example.com", password="pass")
        provisioner.ensure_ssl("test.com")

        # Should call both check and update commands
        assert mock_client_instance.exec_command.call_count == 2


class TestEnsureSwap:
    """Test ensure_swap method."""

    @patch("wordops_provisioner.provisioner.paramiko.SSHClient")
    def test_ensure_swap_already_exists(self, mock_ssh_client):
        """Test ensure_swap skips when swap already exists."""
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        mock_stdout = Mock()
        mock_stderr = Mock()
        mock_channel = Mock()
        mock_stdout.channel = mock_channel
        mock_channel.recv_exit_status.return_value = 0
        mock_stdout.read.return_value = b"swap output"
        mock_stderr.read.return_value = b""

        mock_client_instance.exec_command.return_value = (
            None,
            mock_stdout,
            mock_stderr,
        )

        provisioner = WordOpsProvisioner(host="example.com", password="pass")
        provisioner.ensure_swap()

        # Should only call the check command
        mock_client_instance.exec_command.assert_called_once_with("swapon --show")

    @patch("wordops_provisioner.provisioner.paramiko.SSHClient")
    def test_ensure_swap_creates_swap(self, mock_ssh_client):
        """Test ensure_swap creates swap when not present."""
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        # Setup mock to return different values for different commands
        def exec_command_side_effect(command):
            mock_stdout = Mock()
            mock_stderr = Mock()
            mock_channel = Mock()
            mock_stdout.channel = mock_channel
            mock_channel.recv_exit_status.return_value = 0
            mock_stderr.read.return_value = b""

            if "swapon --show" in command:
                # No swap exists
                mock_stdout.read.return_value = b""
            else:
                # All other commands succeed
                mock_stdout.read.return_value = b"success"

            return None, mock_stdout, mock_stderr

        mock_client_instance.exec_command.side_effect = exec_command_side_effect

        provisioner = WordOpsProvisioner(host="example.com", password="pass")
        provisioner.ensure_swap(size_gb=4)

        # Should call multiple commands to create swap
        assert mock_client_instance.exec_command.call_count == 6


class TestFromEnv:
    """Test from_env classmethod."""

    @patch("wordops_provisioner.provisioner.paramiko.SSHClient")
    @patch("wordops_provisioner.provisioner.os.getenv")
    @patch("wordops_provisioner.provisioner.load_dotenv")
    def test_from_env_with_all_vars(
        self, mock_load_dotenv, mock_getenv, mock_ssh_client
    ):
        """Test from_env with all environment variables set."""
        mock_getenv.side_effect = lambda key, default=None: {
            "SERVER_HOST": "192.168.1.1",
            "SSH_USER": "admin",
            "SSH_PASSWORD": "secret",
        }.get(key, default)

        provisioner = WordOpsProvisioner.from_env()

        mock_load_dotenv.assert_called_once()
        assert provisioner.host == "192.168.1.1"
        assert provisioner.user == "admin"
        assert provisioner.password == "secret"

    @patch("wordops_provisioner.provisioner.os.getenv")
    @patch("wordops_provisioner.provisioner.load_dotenv")
    def test_from_env_missing_host_raises(self, mock_load_dotenv, mock_getenv):
        """Test from_env raises when SERVER_HOST is missing."""
        mock_getenv.side_effect = lambda key, default=None: {
            "SSH_PASSWORD": "secret"
        }.get(key, default)

        with pytest.raises(ValueError):
            WordOpsProvisioner.from_env()
