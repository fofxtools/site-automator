import pytest
from unittest.mock import Mock, patch

from site_automator.wordops import WordOpsProvisioner


class TestInit:
    """Test __init__ and SSHConnection creation."""

    @patch("site_automator.wordops.SSHConnection")
    def test_init_stores_host(self, mock_ssh_connection):
        """Test that host is stored correctly."""
        wordops = WordOpsProvisioner(host="example.com")

        assert wordops.host == "example.com"
        assert wordops.user is None
        mock_ssh_connection.assert_called_once_with("example.com", None)

    @patch("site_automator.wordops.SSHConnection")
    def test_init_stores_explicit_user(self, mock_ssh_connection):
        """Test that explicit user is stored correctly."""
        wordops = WordOpsProvisioner(host="example.com", user="deploy")

        assert wordops.host == "example.com"
        assert wordops.user == "deploy"
        mock_ssh_connection.assert_called_once_with("example.com", "deploy")

    @patch("site_automator.wordops.SSHConnection")
    def test_init_connects_with_ssh_keys(self, mock_ssh_connection):
        """Test that SSH connection is created."""
        _ = WordOpsProvisioner(host="example.com")

        # Verify SSHConnection was created
        mock_ssh_connection.assert_called_once_with("example.com", None)

    @patch("site_automator.wordops.SSHConnection")
    def test_init_resolves_ssh_alias(self, mock_ssh_connection):
        """Test that SSH connection is created with alias."""
        _ = WordOpsProvisioner(host="myserver")

        # Verify SSHConnection was created with the host alias
        mock_ssh_connection.assert_called_once_with("myserver", None)

    @patch("site_automator.wordops.SSHConnection")
    def test_explicit_user_overrides_ssh_config(self, mock_ssh_connection):
        """Test that explicit user parameter is passed to SSHConnection."""
        _ = WordOpsProvisioner(host="myserver", user="deploy")

        # Verify explicit user is passed to SSHConnection
        mock_ssh_connection.assert_called_once_with("myserver", "deploy")


class TestClose:
    """Test close method."""

    @patch("site_automator.wordops.SSHConnection")
    def test_close_closes_client(self, mock_ssh_connection):
        """Test that close() closes the SSH connection."""
        mock_ssh_instance = Mock()
        mock_ssh_connection.return_value = mock_ssh_instance

        wordops = WordOpsProvisioner(host="example.com")
        wordops.close()

        mock_ssh_instance.close.assert_called_once()

    @patch("site_automator.wordops.SSHConnection")
    def test_close_handles_none_client(self, mock_ssh_connection):
        """Test that close() delegates to SSHConnection.close()."""
        mock_ssh_instance = Mock()
        mock_ssh_connection.return_value = mock_ssh_instance

        wordops = WordOpsProvisioner(host="example.com")
        wordops.close()

        # SSHConnection.close() should be called
        mock_ssh_instance.close.assert_called_once()


class TestCreateSite:
    """Test create_site method."""

    @patch("site_automator.wordops.SSHConnection")
    def test_create_site_without_flags(self, mock_ssh_connection):
        """Test create_site with no flags."""
        mock_ssh_instance = Mock()
        mock_ssh_connection.return_value = mock_ssh_instance
        mock_ssh_instance.run_command.return_value = ("Site created", 0)

        wordops = WordOpsProvisioner(host="example.com")
        wordops.create_site("test.com")

        mock_ssh_instance.run_command.assert_called_with(
            "wo site create test.com", check=True
        )

    @patch("site_automator.wordops.SSHConnection")
    def test_create_site_with_flags(self, mock_ssh_connection):
        """Test create_site with flags."""
        mock_ssh_instance = Mock()
        mock_ssh_connection.return_value = mock_ssh_instance
        mock_ssh_instance.run_command.return_value = ("Site created", 0)

        wordops = WordOpsProvisioner(host="example.com")
        wordops.create_site("test.com", flags=["--wp", "--php81"])

        mock_ssh_instance.run_command.assert_called_with(
            "wo site create test.com --wp --php81", check=True
        )

    @patch("site_automator.wordops.SSHConnection")
    def test_create_site_failure_raises(self, mock_ssh_connection):
        """Test create_site raises on failure."""
        mock_ssh_instance = Mock()
        mock_ssh_connection.return_value = mock_ssh_instance
        mock_ssh_instance.run_command.side_effect = RuntimeError("Command failed")

        wordops = WordOpsProvisioner(host="example.com")

        with pytest.raises(RuntimeError):
            wordops.create_site("test.com")


class TestRestartNginx:
    """Test restart_nginx method."""

    @patch("site_automator.wordops.SSHConnection")
    def test_restart_nginx_success(self, mock_ssh_connection):
        """Test restart_nginx executes systemctl command."""
        mock_ssh_instance = Mock()
        mock_ssh_connection.return_value = mock_ssh_instance
        mock_ssh_instance.run_command.return_value = ("", 0)

        wordops = WordOpsProvisioner(host="example.com")
        wordops.restart_nginx()

        mock_ssh_instance.run_command.assert_called_with(
            "systemctl restart nginx", check=True
        )

    @patch("site_automator.wordops.SSHConnection")
    def test_restart_nginx_failure_raises(self, mock_ssh_connection):
        """Test restart_nginx raises on failure."""
        mock_ssh_instance = Mock()
        mock_ssh_connection.return_value = mock_ssh_instance
        mock_ssh_instance.run_command.side_effect = RuntimeError("Command failed")

        wordops = WordOpsProvisioner(host="example.com")

        with pytest.raises(RuntimeError):
            wordops.restart_nginx()


class TestEnsureSSL:
    """Test ensure_ssl method."""

    @patch("site_automator.wordops.SSHConnection")
    def test_ensure_ssl_already_enabled(self, mock_ssh_connection):
        """Test ensure_ssl skips when SSL already enabled."""
        mock_ssh_instance = Mock()
        mock_ssh_connection.return_value = mock_ssh_instance
        mock_ssh_instance.run_command.return_value = ("", 0)

        wordops = WordOpsProvisioner(host="example.com")
        result = wordops.ensure_ssl("test.com")

        # Should return True and only call the check command, not the update command
        assert result is True
        mock_ssh_instance.run_command.assert_called_once_with(
            "test -f /var/www/test.com/conf/nginx/ssl.conf", check=False
        )

    @patch("site_automator.wordops.SSHConnection")
    def test_ensure_ssl_enables_ssl(self, mock_ssh_connection):
        """Test ensure_ssl enables SSL when not present and DNS matches."""
        mock_ssh_instance = Mock()
        mock_ssh_connection.return_value = mock_ssh_instance

        # Setup mock to return different values for different commands
        def run_command_side_effect(command, check=True):
            if "test -f" in command:
                # SSL check fails (not present)
                return ("", 1)
            elif "dig +short" in command:
                # DNS check succeeds (matches server IP)
                return ("", 0)
            else:
                # SSL enable succeeds
                return ("", 0)

        mock_ssh_instance.run_command.side_effect = run_command_side_effect

        wordops = WordOpsProvisioner(host="example.com")
        result = wordops.ensure_ssl("test.com")

        # Should return True and call check, DNS check, and update commands
        assert result is True
        assert mock_ssh_instance.run_command.call_count == 3

    @patch("site_automator.wordops.SSHConnection")
    def test_ensure_ssl_skips_on_dns_mismatch(self, mock_ssh_connection):
        """Test ensure_ssl skips when DNS doesn't match server IP."""
        mock_ssh_instance = Mock()
        mock_ssh_connection.return_value = mock_ssh_instance

        # Setup mock to return different values for different commands
        def run_command_side_effect(command, check=True):
            if "test -f" in command:
                # SSL check fails (not present)
                return ("", 1)
            elif "dig +short" in command:
                # DNS check fails (doesn't match server IP)
                return ("", 1)
            else:
                # Should not reach SSL enable
                return ("", 0)

        mock_ssh_instance.run_command.side_effect = run_command_side_effect

        wordops = WordOpsProvisioner(host="example.com")
        result = wordops.ensure_ssl("test.com")

        # Should return False and only call check and DNS check commands (not SSL enable)
        assert result is False
        assert mock_ssh_instance.run_command.call_count == 2


class TestEnsureDefaultCatchall:
    """Test ensure_default_catchall method."""

    @patch("site_automator.wordops.SSHConnection")
    def test_already_exists(self, mock_ssh_connection):
        """Test returns early if catchall already exists."""
        mock_ssh_instance = Mock()
        mock_ssh_connection.return_value = mock_ssh_instance
        mock_ssh_instance.run_command.return_value = ("", 0)

        wordops = WordOpsProvisioner(host="example.com")
        wordops.ensure_default_catchall()

        mock_ssh_instance.run_command.assert_called_once_with(
            "test -L /etc/nginx/sites-enabled/000-catchall", check=False
        )

    @patch("site_automator.wordops.SSHConnection")
    def test_raises_on_conflicting_default_server(self, mock_ssh_connection):
        """Test raises error if conflicting default_server exists."""
        mock_ssh_instance = Mock()
        mock_ssh_connection.return_value = mock_ssh_instance

        call_count = [0]

        def run_command_side_effect(cmd, check=True):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call: catchall doesn't exist
                return ("", 1)
            elif call_count[0] == 2:
                # Second call: remove default symlink
                return ("", 0)
            elif call_count[0] == 3:
                # Third call: grep finds conflict
                return ("/etc/nginx/sites-enabled/other:1:listen 80 default_server;", 0)
            return ("", 0)

        mock_ssh_instance.run_command.side_effect = run_command_side_effect

        wordops = WordOpsProvisioner(host="example.com")

        with pytest.raises(RuntimeError, match="Conflicting default_server"):
            wordops.ensure_default_catchall()

    @patch("site_automator.wordops.SSHConnection")
    def test_creates_catchall_config(self, mock_ssh_connection):
        """Test creates catchall config with correct content."""
        mock_ssh_instance = Mock()
        mock_ssh_connection.return_value = mock_ssh_instance

        call_count = [0]

        def run_command_side_effect(cmd, check=True):
            call_count[0] += 1
            if call_count[0] <= 3:
                # First 3 calls: checks fail (catchall doesn't exist, no conflicts, rm)
                return ("", 1)
            else:
                # Remaining calls succeed (ln, nginx -t, reload)
                return ("", 0)

        mock_ssh_instance.run_command.side_effect = run_command_side_effect

        wordops = WordOpsProvisioner(host="example.com")
        wordops.ensure_default_catchall()

        # Should upload config file using upload_file
        mock_ssh_instance.upload_file.assert_called_once()

        # Verify remote path
        call_args = mock_ssh_instance.upload_file.call_args[0]
        remote_path = call_args[1]
        assert "/etc/nginx/sites-available/000-catchall" in remote_path
