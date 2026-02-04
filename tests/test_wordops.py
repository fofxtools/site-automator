import pytest
from unittest.mock import Mock, patch

from site_automator.wordops import WordOpsProvisioner


class TestInit:
    """Test __init__ and _connect methods."""

    @patch("site_automator.wordops.resolve_ssh_host")
    @patch("site_automator.wordops.paramiko.SSHClient")
    def test_init_stores_host(self, mock_ssh_client, mock_resolve):
        """Test that host is stored correctly."""
        mock_resolve.return_value = ("192.168.1.1", None, None)

        wordops = WordOpsProvisioner(host="example.com")

        assert wordops.host == "example.com"
        assert wordops.user is None

    @patch("site_automator.wordops.resolve_ssh_host")
    @patch("site_automator.wordops.paramiko.SSHClient")
    def test_init_stores_explicit_user(self, mock_ssh_client, mock_resolve):
        """Test that explicit user is stored correctly."""
        mock_resolve.return_value = ("192.168.1.1", None, None)

        wordops = WordOpsProvisioner(host="example.com", user="deploy")

        assert wordops.host == "example.com"
        assert wordops.user == "deploy"

    @patch("site_automator.wordops.resolve_ssh_host")
    @patch("site_automator.wordops.paramiko.SSHClient")
    def test_init_connects_with_ssh_keys(self, mock_ssh_client, mock_resolve):
        """Test that SSH connection uses keys and agent."""
        mock_resolve.return_value = ("192.168.1.1", None, None)
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        _ = WordOpsProvisioner(host="example.com")

        # Verify SSH client was created and configured
        mock_ssh_client.assert_called_once()
        mock_client_instance.set_missing_host_key_policy.assert_called_once()
        mock_client_instance.connect.assert_called_once_with(
            hostname="192.168.1.1",
            username="root",
            key_filename=None,
            allow_agent=True,
            look_for_keys=True,
        )

    @patch("site_automator.wordops.resolve_ssh_host")
    @patch("site_automator.wordops.paramiko.SSHClient")
    def test_init_resolves_ssh_alias(self, mock_ssh_client, mock_resolve):
        """Test that SSH alias is resolved to hostname."""
        mock_resolve.return_value = ("10.0.0.5", "admin", "/home/user/.ssh/mykey")
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        _ = WordOpsProvisioner(host="myserver")

        # Verify resolve_ssh_host was called
        mock_resolve.assert_called_once_with("myserver")

        # Verify connection uses resolved values
        mock_client_instance.connect.assert_called_once_with(
            hostname="10.0.0.5",
            username="admin",
            key_filename="/home/user/.ssh/mykey",
            allow_agent=True,
            look_for_keys=True,
        )

    @patch("site_automator.wordops.resolve_ssh_host")
    @patch("site_automator.wordops.paramiko.SSHClient")
    def test_explicit_user_overrides_ssh_config(self, mock_ssh_client, mock_resolve):
        """Test that explicit user parameter overrides SSH config user."""
        mock_resolve.return_value = ("10.0.0.5", "admin", None)
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        _ = WordOpsProvisioner(host="myserver", user="deploy")

        # Verify explicit user is used, not SSH config user
        mock_client_instance.connect.assert_called_once_with(
            hostname="10.0.0.5",
            username="deploy",
            key_filename=None,
            allow_agent=True,
            look_for_keys=True,
        )


class TestClose:
    """Test close method."""

    @patch("site_automator.wordops.resolve_ssh_host")
    @patch("site_automator.wordops.paramiko.SSHClient")
    def test_close_closes_client(self, mock_ssh_client, mock_resolve):
        """Test that close() closes the SSH client."""
        mock_resolve.return_value = ("192.168.1.1", None, None)
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        wordops = WordOpsProvisioner(host="example.com")
        wordops.close()

        mock_client_instance.close.assert_called_once()
        assert wordops._client is None

    @patch("site_automator.wordops.resolve_ssh_host")
    @patch("site_automator.wordops.paramiko.SSHClient")
    def test_close_handles_none_client(self, mock_ssh_client, mock_resolve):
        """Test that close() handles None client gracefully."""
        mock_resolve.return_value = ("192.168.1.1", None, None)

        wordops = WordOpsProvisioner(host="example.com")
        wordops._client = None
        wordops.close()  # Should not raise


class TestRunCommand:
    """Test run_command method."""

    @patch("site_automator.wordops.resolve_ssh_host")
    @patch("site_automator.wordops.paramiko.SSHClient")
    def test_run_command_success(self, mock_ssh_client, mock_resolve):
        """Test successful command execution."""
        mock_resolve.return_value = ("192.168.1.1", None, None)
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

        wordops = WordOpsProvisioner(host="example.com")
        output, exit_code = wordops.run_command("echo test")

        assert output == "command output"
        assert exit_code == 0
        mock_client_instance.exec_command.assert_called_with("echo test")

    @patch("site_automator.wordops.resolve_ssh_host")
    @patch("site_automator.wordops.paramiko.SSHClient")
    def test_run_command_failure_with_check(self, mock_ssh_client, mock_resolve):
        """Test command failure raises exception when check=True."""
        mock_resolve.return_value = ("192.168.1.1", None, None)
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

        wordops = WordOpsProvisioner(host="example.com")

        with pytest.raises(RuntimeError):
            wordops.run_command("false", check=True)

    @patch("site_automator.wordops.resolve_ssh_host")
    @patch("site_automator.wordops.paramiko.SSHClient")
    def test_run_command_failure_without_check(self, mock_ssh_client, mock_resolve):
        """Test command failure returns exit code when check=False."""
        mock_resolve.return_value = ("192.168.1.1", None, None)
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

        wordops = WordOpsProvisioner(host="example.com")
        output, exit_code = wordops.run_command("false", check=False)

        assert exit_code == 1
        assert "error" in output

    @patch("site_automator.wordops.resolve_ssh_host")
    @patch("site_automator.wordops.paramiko.SSHClient")
    def test_run_command_no_client_raises(self, mock_ssh_client, mock_resolve):
        """Test run_command raises when client is None."""
        mock_resolve.return_value = ("192.168.1.1", None, None)

        wordops = WordOpsProvisioner(host="example.com")
        wordops._client = None

        with pytest.raises(RuntimeError):
            wordops.run_command("echo test")


class TestCreateSite:
    """Test create_site method."""

    @patch("site_automator.wordops.resolve_ssh_host")
    @patch("site_automator.wordops.paramiko.SSHClient")
    def test_create_site_without_flags(self, mock_ssh_client, mock_resolve):
        """Test create_site with no flags."""
        mock_resolve.return_value = ("192.168.1.1", None, None)
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

        wordops = WordOpsProvisioner(host="example.com")
        wordops.create_site("test.com")

        mock_client_instance.exec_command.assert_called_with("wo site create test.com")

    @patch("site_automator.wordops.resolve_ssh_host")
    @patch("site_automator.wordops.paramiko.SSHClient")
    def test_create_site_with_flags(self, mock_ssh_client, mock_resolve):
        """Test create_site with flags."""
        mock_resolve.return_value = ("192.168.1.1", None, None)
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

        wordops = WordOpsProvisioner(host="example.com")
        wordops.create_site("test.com", flags=["--wp", "--php81"])

        mock_client_instance.exec_command.assert_called_with(
            "wo site create test.com --wp --php81"
        )

    @patch("site_automator.wordops.resolve_ssh_host")
    @patch("site_automator.wordops.paramiko.SSHClient")
    def test_create_site_failure_raises(self, mock_ssh_client, mock_resolve):
        """Test create_site raises on failure."""
        mock_resolve.return_value = ("192.168.1.1", None, None)
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

        wordops = WordOpsProvisioner(host="example.com")

        with pytest.raises(RuntimeError):
            wordops.create_site("test.com")


class TestRestartNginx:
    """Test restart_nginx method."""

    @patch("site_automator.wordops.resolve_ssh_host")
    @patch("site_automator.wordops.paramiko.SSHClient")
    def test_restart_nginx_success(self, mock_ssh_client, mock_resolve):
        """Test restart_nginx executes systemctl command."""
        mock_resolve.return_value = ("192.168.1.1", None, None)
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

        wordops = WordOpsProvisioner(host="example.com")
        wordops.restart_nginx()

        mock_client_instance.exec_command.assert_called_with("systemctl restart nginx")

    @patch("site_automator.wordops.resolve_ssh_host")
    @patch("site_automator.wordops.paramiko.SSHClient")
    def test_restart_nginx_failure_raises(self, mock_ssh_client, mock_resolve):
        """Test restart_nginx raises on failure."""
        mock_resolve.return_value = ("192.168.1.1", None, None)
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

        wordops = WordOpsProvisioner(host="example.com")

        with pytest.raises(RuntimeError):
            wordops.restart_nginx()


class TestEnsureSSL:
    """Test ensure_ssl method."""

    @patch("site_automator.wordops.resolve_ssh_host")
    @patch("site_automator.wordops.paramiko.SSHClient")
    def test_ensure_ssl_already_enabled(self, mock_ssh_client, mock_resolve):
        """Test ensure_ssl skips when SSL already enabled."""
        mock_resolve.return_value = ("192.168.1.1", None, None)
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

        wordops = WordOpsProvisioner(host="example.com")
        wordops.ensure_ssl("test.com")

        # Should only call the check command, not the update command
        mock_client_instance.exec_command.assert_called_once_with(
            "test -f /var/www/test.com/conf/nginx/ssl.conf"
        )

    @patch("site_automator.wordops.resolve_ssh_host")
    @patch("site_automator.wordops.paramiko.SSHClient")
    def test_ensure_ssl_enables_ssl(self, mock_ssh_client, mock_resolve):
        """Test ensure_ssl enables SSL when not present."""
        mock_resolve.return_value = ("192.168.1.1", None, None)
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

        wordops = WordOpsProvisioner(host="example.com")
        wordops.ensure_ssl("test.com")

        # Should call both check and update commands
        assert mock_client_instance.exec_command.call_count == 2


class TestEnsureDefaultCatchall:
    """Test ensure_default_catchall method."""

    @patch("site_automator.wordops.resolve_ssh_host")
    @patch("site_automator.wordops.paramiko.SSHClient")
    def test_already_exists(self, mock_ssh_client, mock_resolve):
        """Test returns early if catchall already exists."""
        mock_resolve.return_value = ("192.168.1.1", None, None)
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

        wordops = WordOpsProvisioner(host="example.com")
        wordops.ensure_default_catchall()

        mock_client_instance.exec_command.assert_called_once_with(
            "test -L /etc/nginx/sites-enabled/000-catchall"
        )

    @patch("site_automator.wordops.resolve_ssh_host")
    @patch("site_automator.wordops.paramiko.SSHClient")
    def test_raises_on_conflicting_default_server(self, mock_ssh_client, mock_resolve):
        """Test raises error if conflicting default_server exists."""
        mock_resolve.return_value = ("192.168.1.1", None, None)
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        call_count = [0]

        def exec_command_side_effect(cmd):
            mock_stdout = Mock()
            mock_stderr = Mock()
            mock_channel = Mock()
            mock_stdout.channel = mock_channel
            mock_stderr.read.return_value = b""

            call_count[0] += 1
            if call_count[0] == 1:
                # First call: catchall doesn't exist
                mock_channel.recv_exit_status.return_value = 1
                mock_stdout.read.return_value = b""
            elif call_count[0] == 2:
                # Second call: grep finds conflict
                mock_channel.recv_exit_status.return_value = 0
                mock_stdout.read.return_value = (
                    b"/etc/nginx/sites-enabled/other:1:listen 80 default_server;"
                )

            return (None, mock_stdout, mock_stderr)

        mock_client_instance.exec_command.side_effect = exec_command_side_effect

        wordops = WordOpsProvisioner(host="example.com")

        with pytest.raises(RuntimeError, match="Conflicting default_server"):
            wordops.ensure_default_catchall()

    @patch("site_automator.wordops.resolve_ssh_host")
    @patch("site_automator.wordops.paramiko.SSHClient")
    def test_creates_catchall_config(self, mock_ssh_client, mock_resolve):
        """Test creates catchall config with correct content."""
        mock_resolve.return_value = ("192.168.1.1", None, None)
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        call_count = [0]

        def exec_command_side_effect(cmd):
            mock_stdout = Mock()
            mock_stderr = Mock()
            mock_channel = Mock()
            mock_stdout.channel = mock_channel
            mock_stderr.read.return_value = b""
            mock_stdout.read.return_value = b""

            call_count[0] += 1
            if call_count[0] <= 3:
                # First 3 calls: checks fail (catchall doesn't exist, no conflicts, rm)
                mock_channel.recv_exit_status.return_value = 1
            else:
                # Remaining calls succeed (cat, ln, nginx -t, reload)
                mock_channel.recv_exit_status.return_value = 0

            return (None, mock_stdout, mock_stderr)

        mock_client_instance.exec_command.side_effect = exec_command_side_effect

        wordops = WordOpsProvisioner(host="example.com")
        wordops.ensure_default_catchall()

        # Check config was written
        calls = [
            call[0][0] for call in mock_client_instance.exec_command.call_args_list
        ]
        config_call = [c for c in calls if "cat >" in c][0]

        assert "listen 80 default_server" in config_call
        assert "listen [::]:80 default_server" in config_call
        assert "listen 443 ssl default_server" in config_call
        assert "listen [::]:443 ssl default_server" in config_call
        assert "ssl_reject_handshake on" in config_call
        assert "return 444" in config_call


class TestEnsureSwap:
    """Test ensure_swap method."""

    @patch("site_automator.wordops.resolve_ssh_host")
    @patch("site_automator.wordops.paramiko.SSHClient")
    def test_ensure_swap_already_exists(self, mock_ssh_client, mock_resolve):
        """Test ensure_swap skips when swap already exists."""
        mock_resolve.return_value = ("192.168.1.1", None, None)
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

        wordops = WordOpsProvisioner(host="example.com")
        wordops.ensure_swap()

        # Should only call the check command
        mock_client_instance.exec_command.assert_called_once_with("swapon --show")

    @patch("site_automator.wordops.resolve_ssh_host")
    @patch("site_automator.wordops.paramiko.SSHClient")
    def test_ensure_swap_creates_swap(self, mock_ssh_client, mock_resolve):
        """Test ensure_swap creates swap when not present."""
        mock_resolve.return_value = ("192.168.1.1", None, None)
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

        wordops = WordOpsProvisioner(host="example.com")
        wordops.ensure_swap(size_gb=4)

        # Should call multiple commands to create swap
        assert mock_client_instance.exec_command.call_count == 6


class TestEnsureGitSafeDirectory:
    """Test ensure_git_safe_directory method."""

    @patch("site_automator.wordops.resolve_ssh_host")
    @patch("site_automator.wordops.paramiko.SSHClient")
    def test_configures_git_safe_directory_with_wildcard(
        self, mock_ssh_client, mock_resolve
    ):
        """Test that git safe.directory is configured with wildcard."""
        mock_resolve.return_value = ("192.168.1.1", None, None)
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        # Mock exec_command to return success
        mock_channel = Mock()
        mock_stdout = Mock()
        mock_stderr = Mock()
        mock_stdout.channel = mock_channel
        mock_channel.recv_exit_status.return_value = 0
        mock_stdout.read.return_value = b"success"
        mock_stderr.read.return_value = b""
        mock_client_instance.exec_command.return_value = (
            None,
            mock_stdout,
            mock_stderr,
        )

        wordops = WordOpsProvisioner(host="example.com")
        wordops.ensure_git_safe_directory()

        # Verify git config command was called with wildcard
        calls = mock_client_instance.exec_command.call_args_list
        git_config_call = [
            call
            for call in calls
            if "git config --system --add safe.directory" in str(call)
        ]
        assert len(git_config_call) == 1
        assert "'*'" in str(git_config_call[0]) or '"*"' in str(git_config_call[0])

    @patch("site_automator.wordops.resolve_ssh_host")
    @patch("site_automator.wordops.paramiko.SSHClient")
    def test_raises_on_git_config_failure(self, mock_ssh_client, mock_resolve):
        """Test that failure to configure git raises RuntimeError."""
        mock_resolve.return_value = ("192.168.1.1", None, None)
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        # Mock exec_command to return failure for git config
        def exec_command_side_effect(command):
            mock_channel = Mock()
            mock_stdout = Mock()
            mock_stderr = Mock()
            mock_stdout.channel = mock_channel
            mock_stderr.read.return_value = b""

            if "git config" in command:
                mock_channel.recv_exit_status.return_value = 1
                mock_stdout.read.return_value = b""
                mock_stderr.read.return_value = b"error: could not lock config file"
            else:
                mock_channel.recv_exit_status.return_value = 0
                mock_stdout.read.return_value = b"success"

            return None, mock_stdout, mock_stderr

        mock_client_instance.exec_command.side_effect = exec_command_side_effect

        wordops = WordOpsProvisioner(host="example.com")

        with pytest.raises(RuntimeError, match="Command failed with exit code 1"):
            wordops.ensure_git_safe_directory()
