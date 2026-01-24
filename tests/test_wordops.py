import pytest
from unittest.mock import Mock, patch

from site_automator.wordops import WordOpsProvisioner


class TestInit:
    """Test __init__ and _connect methods."""

    @patch("site_automator.wordops.paramiko.SSHClient")
    def test_init_stores_credentials(self, mock_ssh_client):
        """Test that credentials are stored correctly."""
        wordops = WordOpsProvisioner(
            host="example.com", user="testuser", password="testpass"
        )

        assert wordops.host == "example.com"
        assert wordops.user == "testuser"
        assert wordops.password == "testpass"

    @patch("site_automator.wordops.paramiko.SSHClient")
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


class TestFromEnv:
    """Test from_env classmethod."""

    @patch("site_automator.wordops.paramiko.SSHClient")
    @patch("site_automator.wordops.os.getenv")
    @patch("site_automator.wordops.load_dotenv")
    def test_from_env_with_all_vars(
        self, mock_load_dotenv, mock_getenv, mock_ssh_client
    ):
        """Test from_env with all environment variables set."""
        mock_getenv.side_effect = lambda key, default=None: {
            "SERVER_HOST": "192.168.1.1",
            "SSH_USER": "root",
            "SSH_PASSWORD": "secret",
        }.get(key, default)

        wordops = WordOpsProvisioner.from_env()

        mock_load_dotenv.assert_called_once()
        assert wordops.host == "192.168.1.1"
        assert wordops.user == "root"
        assert wordops.password == "secret"

    @patch("site_automator.wordops.os.getenv")
    @patch("site_automator.wordops.load_dotenv")
    def test_from_env_missing_host_raises(self, mock_load_dotenv, mock_getenv):
        """Test from_env raises when SERVER_HOST is missing."""
        mock_getenv.side_effect = lambda key, default=None: {
            "SSH_PASSWORD": "secret"
        }.get(key, default)

        with pytest.raises(ValueError):
            WordOpsProvisioner.from_env()


class TestClose:
    """Test close method."""

    @patch("site_automator.wordops.paramiko.SSHClient")
    def test_close_closes_client(self, mock_ssh_client):
        """Test that close() closes the SSH client."""
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        wordops = WordOpsProvisioner(host="example.com", password="pass")
        wordops.close()

        mock_client_instance.close.assert_called_once()
        assert wordops._client is None

    @patch("site_automator.wordops.paramiko.SSHClient")
    def test_close_handles_none_client(self, mock_ssh_client):
        """Test that close() handles None client gracefully."""
        wordops = WordOpsProvisioner(host="example.com", password="pass")
        wordops._client = None
        wordops.close()  # Should not raise


class TestRunCommand:
    """Test run_command method."""

    @patch("site_automator.wordops.paramiko.SSHClient")
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

        wordops = WordOpsProvisioner(host="example.com", password="pass")
        output, exit_code = wordops.run_command("echo test")

        assert output == "command output"
        assert exit_code == 0
        mock_client_instance.exec_command.assert_called_with("echo test")

    @patch("site_automator.wordops.paramiko.SSHClient")
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

        wordops = WordOpsProvisioner(host="example.com", password="pass")

        with pytest.raises(RuntimeError):
            wordops.run_command("false", check=True)

    @patch("site_automator.wordops.paramiko.SSHClient")
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

        wordops = WordOpsProvisioner(host="example.com", password="pass")
        output, exit_code = wordops.run_command("false", check=False)

        assert exit_code == 1
        assert "error" in output

    @patch("site_automator.wordops.paramiko.SSHClient")
    def test_run_command_no_client_raises(self, mock_ssh_client):
        """Test run_command raises when client is None."""
        wordops = WordOpsProvisioner(host="example.com", password="pass")
        wordops._client = None

        with pytest.raises(RuntimeError):
            wordops.run_command("echo test")


class TestCreateSite:
    """Test create_site method."""

    @patch("site_automator.wordops.paramiko.SSHClient")
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

        wordops = WordOpsProvisioner(host="example.com", password="pass")
        wordops.create_site("test.com")

        mock_client_instance.exec_command.assert_called_with("wo site create test.com")

    @patch("site_automator.wordops.paramiko.SSHClient")
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

        wordops = WordOpsProvisioner(host="example.com", password="pass")
        wordops.create_site("test.com", flags=["--wp", "--php81"])

        mock_client_instance.exec_command.assert_called_with(
            "wo site create test.com --wp --php81"
        )

    @patch("site_automator.wordops.paramiko.SSHClient")
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

        wordops = WordOpsProvisioner(host="example.com", password="pass")

        with pytest.raises(RuntimeError):
            wordops.create_site("test.com")


class TestRestartNginx:
    """Test restart_nginx method."""

    @patch("site_automator.wordops.paramiko.SSHClient")
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

        wordops = WordOpsProvisioner(host="example.com", password="pass")
        wordops.restart_nginx()

        mock_client_instance.exec_command.assert_called_with("systemctl restart nginx")

    @patch("site_automator.wordops.paramiko.SSHClient")
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

        wordops = WordOpsProvisioner(host="example.com", password="pass")

        with pytest.raises(RuntimeError):
            wordops.restart_nginx()


class TestEnsureSSL:
    """Test ensure_ssl method."""

    @patch("site_automator.wordops.paramiko.SSHClient")
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

        wordops = WordOpsProvisioner(host="example.com", password="pass")
        wordops.ensure_ssl("test.com")

        # Should only call the check command, not the update command
        mock_client_instance.exec_command.assert_called_once_with(
            "test -f /var/www/test.com/conf/nginx/ssl.conf"
        )

    @patch("site_automator.wordops.paramiko.SSHClient")
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

        wordops = WordOpsProvisioner(host="example.com", password="pass")
        wordops.ensure_ssl("test.com")

        # Should call both check and update commands
        assert mock_client_instance.exec_command.call_count == 2


class TestEnsureSwap:
    """Test ensure_swap method."""

    @patch("site_automator.wordops.paramiko.SSHClient")
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

        wordops = WordOpsProvisioner(host="example.com", password="pass")
        wordops.ensure_swap()

        # Should only call the check command
        mock_client_instance.exec_command.assert_called_once_with("swapon --show")

    @patch("site_automator.wordops.paramiko.SSHClient")
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

        wordops = WordOpsProvisioner(host="example.com", password="pass")
        wordops.ensure_swap(size_gb=4)

        # Should call multiple commands to create swap
        assert mock_client_instance.exec_command.call_count == 6
