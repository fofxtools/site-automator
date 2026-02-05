"""Tests for SSH config resolution."""

import pytest
from unittest.mock import Mock, patch

from site_automator.ssh import resolve_ssh_host, SSHConnection


class TestResolveSSHHost:
    """Test resolve_ssh_host function."""

    def test_no_ssh_config_returns_host_as_is(self):
        """When no SSH config exists, return host unchanged."""
        with patch("os.path.exists", return_value=False):
            hostname, user, keyfile = resolve_ssh_host("example.com")

        assert hostname == "example.com"
        assert user is None
        assert keyfile is None

    def test_resolves_alias_to_hostname(self, tmp_path):
        """Resolve SSH alias to actual hostname."""
        config_content = """
Host myserver
    HostName 192.168.1.100
    User admin
    IdentityFile ~/.ssh/mykey
"""
        config_path = tmp_path / "config"
        config_path.write_text(config_content)

        with patch("os.path.expanduser", return_value=str(config_path)):
            hostname, user, keyfile = resolve_ssh_host("myserver")

        assert hostname == "192.168.1.100"
        assert user == "admin"
        # Paramiko expands ~ in IdentityFile paths
        assert keyfile is not None
        assert keyfile.endswith("/.ssh/mykey")

    def test_ip_address_without_config_entry(self, tmp_path):
        """IP address without matching config entry returns as-is."""
        config_content = """
Host myserver
    HostName 192.168.1.100
"""
        config_path = tmp_path / "config"
        config_path.write_text(config_content)

        with patch("os.path.expanduser", return_value=str(config_path)):
            hostname, user, keyfile = resolve_ssh_host("10.0.0.1")

        assert hostname == "10.0.0.1"
        assert user is None
        assert keyfile is None

    def test_alias_without_user_or_keyfile(self, tmp_path):
        """Alias with only hostname specified."""
        config_content = """
Host shortname
    HostName server.example.com
"""
        config_path = tmp_path / "config"
        config_path.write_text(config_content)

        with patch("os.path.expanduser", return_value=str(config_path)):
            hostname, user, keyfile = resolve_ssh_host("shortname")

        assert hostname == "server.example.com"
        assert user is None
        assert keyfile is None

    def test_wildcard_config_match(self, tmp_path):
        """Test wildcard pattern matching in SSH config."""
        config_content = """
Host *.example.com
    User deploy
    IdentityFile ~/.ssh/deploy_key

Host web1.example.com
    HostName 10.0.0.5
"""
        config_path = tmp_path / "config"
        config_path.write_text(config_content)

        with patch("os.path.expanduser", return_value=str(config_path)):
            hostname, user, keyfile = resolve_ssh_host("web1.example.com")

        assert hostname == "10.0.0.5"
        assert user == "deploy"
        # Paramiko expands ~ in IdentityFile paths
        assert keyfile is not None
        assert keyfile.endswith("/.ssh/deploy_key")


class TestSSHConnection:
    """Test SSHConnection class."""

    @patch("site_automator.ssh.resolve_ssh_host")
    @patch("site_automator.ssh.paramiko.SSHClient")
    def test_init_stores_host(self, mock_ssh_client, mock_resolve):
        """Test that host is stored correctly."""
        mock_resolve.return_value = ("192.168.1.1", None, None)
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        ssh = SSHConnection(host="example.com")

        assert ssh.host == "example.com"
        assert ssh.user is None

    @patch("site_automator.ssh.resolve_ssh_host")
    @patch("site_automator.ssh.paramiko.SSHClient")
    def test_init_stores_explicit_user(self, mock_ssh_client, mock_resolve):
        """Test that explicit user is stored correctly."""
        mock_resolve.return_value = ("192.168.1.1", None, None)
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        ssh = SSHConnection(host="example.com", user="deploy")

        assert ssh.host == "example.com"
        assert ssh.user == "deploy"

    @patch("site_automator.ssh.resolve_ssh_host")
    @patch("site_automator.ssh.paramiko.SSHClient")
    def test_init_connects_automatically(self, mock_ssh_client, mock_resolve):
        """Test that __init__ calls connect() automatically."""
        mock_resolve.return_value = ("192.168.1.1", None, None)
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        _ = SSHConnection(host="example.com")

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

    @patch("site_automator.ssh.resolve_ssh_host")
    @patch("site_automator.ssh.paramiko.SSHClient")
    def test_connect_resolves_ssh_alias(self, mock_ssh_client, mock_resolve):
        """Test that SSH alias is resolved to hostname."""
        mock_resolve.return_value = ("10.0.0.5", "admin", "/home/user/.ssh/mykey")
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        _ = SSHConnection(host="myserver")

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

    @patch("site_automator.ssh.resolve_ssh_host")
    @patch("site_automator.ssh.paramiko.SSHClient")
    def test_explicit_user_overrides_ssh_config(self, mock_ssh_client, mock_resolve):
        """Test that explicit user parameter overrides SSH config user."""
        mock_resolve.return_value = ("10.0.0.5", "admin", None)
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        _ = SSHConnection(host="myserver", user="deploy")

        # Verify explicit user is used, not SSH config user
        mock_client_instance.connect.assert_called_once_with(
            hostname="10.0.0.5",
            username="deploy",
            key_filename=None,
            allow_agent=True,
            look_for_keys=True,
        )

    @patch("site_automator.ssh.resolve_ssh_host")
    @patch("site_automator.ssh.paramiko.SSHClient")
    def test_run_command_success(self, mock_ssh_client, mock_resolve):
        """Test successful command execution."""
        mock_resolve.return_value = ("192.168.1.1", None, None)
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        # Mock command execution
        mock_stdout = Mock()
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stdout.read.return_value = b"command output"
        mock_stderr = Mock()
        mock_stderr.read.return_value = b""
        mock_client_instance.exec_command.return_value = (
            None,
            mock_stdout,
            mock_stderr,
        )

        ssh = SSHConnection(host="example.com")
        output, exit_code = ssh.run_command("echo test")

        assert output == "command output"
        assert exit_code == 0
        mock_client_instance.exec_command.assert_called_with("echo test")

    @patch("site_automator.ssh.resolve_ssh_host")
    @patch("site_automator.ssh.paramiko.SSHClient")
    def test_run_command_failure_with_check(self, mock_ssh_client, mock_resolve):
        """Test command failure with check=True raises exception."""
        mock_resolve.return_value = ("192.168.1.1", None, None)
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        # Mock failed command
        mock_stdout = Mock()
        mock_stdout.channel.recv_exit_status.return_value = 1
        mock_stdout.read.return_value = b"output"
        mock_stderr = Mock()
        mock_stderr.read.return_value = b"error message"
        mock_client_instance.exec_command.return_value = (
            None,
            mock_stdout,
            mock_stderr,
        )

        ssh = SSHConnection(host="example.com")

        with pytest.raises(RuntimeError, match="Command failed with exit code 1"):
            ssh.run_command("false", check=True)

    @patch("site_automator.ssh.resolve_ssh_host")
    @patch("site_automator.ssh.paramiko.SSHClient")
    def test_run_command_failure_without_check(self, mock_ssh_client, mock_resolve):
        """Test command failure with check=False returns exit code."""
        mock_resolve.return_value = ("192.168.1.1", None, None)
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        # Mock failed command
        mock_stdout = Mock()
        mock_stdout.channel.recv_exit_status.return_value = 1
        mock_stdout.read.return_value = b"output"
        mock_stderr = Mock()
        mock_stderr.read.return_value = b"error message"
        mock_client_instance.exec_command.return_value = (
            None,
            mock_stdout,
            mock_stderr,
        )

        ssh = SSHConnection(host="example.com")
        output, exit_code = ssh.run_command("false", check=False)

        assert exit_code == 1
        assert "output" in output
        assert "error message" in output

    @patch("site_automator.ssh.resolve_ssh_host")
    @patch("site_automator.ssh.paramiko.SSHClient")
    def test_run_command_no_client_raises(self, mock_ssh_client, mock_resolve):
        """Test run_command raises when client is not connected."""
        mock_resolve.return_value = ("192.168.1.1", None, None)
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        ssh = SSHConnection(host="example.com")
        ssh._client = None

        with pytest.raises(RuntimeError, match="SSH client not connected"):
            ssh.run_command("echo test")

    @patch("site_automator.ssh.resolve_ssh_host")
    @patch("site_automator.ssh.paramiko.SSHClient")
    def test_close_closes_client(self, mock_ssh_client, mock_resolve):
        """Test that close() closes the SSH client."""
        mock_resolve.return_value = ("192.168.1.1", None, None)
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        ssh = SSHConnection(host="example.com")
        ssh.close()

        mock_client_instance.close.assert_called_once()
        assert ssh._client is None

    @patch("site_automator.ssh.resolve_ssh_host")
    @patch("site_automator.ssh.paramiko.SSHClient")
    def test_close_handles_none_client(self, mock_ssh_client, mock_resolve):
        """Test that close() handles None client gracefully."""
        mock_resolve.return_value = ("192.168.1.1", None, None)
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        ssh = SSHConnection(host="example.com")
        ssh._client = None
        ssh.close()  # Should not raise
