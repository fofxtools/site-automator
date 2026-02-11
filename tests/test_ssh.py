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
    def test_upload_file_success(self, mock_ssh_client, mock_resolve, tmp_path):
        """Test successful file upload."""
        mock_resolve.return_value = ("192.168.1.1", None, None)
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        # Mock SFTP
        mock_sftp = Mock()
        mock_client_instance.open_sftp.return_value = mock_sftp

        # Mock run_command for mkdir
        mock_stdout = Mock()
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stdout.read.return_value = b""
        mock_stderr = Mock()
        mock_stderr.read.return_value = b""
        mock_client_instance.exec_command.return_value = (
            None,
            mock_stdout,
            mock_stderr,
        )

        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        ssh = SSHConnection(host="example.com")
        ssh.upload_file(test_file, "/remote/path/test.txt")

        # Verify mkdir was called
        mock_client_instance.exec_command.assert_called_with("mkdir -p /remote/path")

        # Verify SFTP put was called
        mock_sftp.put.assert_called_once_with(str(test_file), "/remote/path/test.txt")
        mock_sftp.close.assert_called_once()

    @patch("site_automator.ssh.resolve_ssh_host")
    @patch("site_automator.ssh.paramiko.SSHClient")
    def test_upload_file_no_client_raises(
        self, mock_ssh_client, mock_resolve, tmp_path
    ):
        """Test upload_file raises when client is not connected."""
        mock_resolve.return_value = ("192.168.1.1", None, None)
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        ssh = SSHConnection(host="example.com")
        ssh._client = None

        with pytest.raises(RuntimeError, match="SSH client not connected"):
            ssh.upload_file(test_file, "/remote/path/test.txt")

    @patch("site_automator.ssh.resolve_ssh_host")
    @patch("site_automator.ssh.paramiko.SSHClient")
    def test_upload_file_not_found_raises(
        self, mock_ssh_client, mock_resolve, tmp_path
    ):
        """Test upload_file raises when local file doesn't exist."""
        mock_resolve.return_value = ("192.168.1.1", None, None)
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        non_existent_file = tmp_path / "does-not-exist.txt"

        ssh = SSHConnection(host="example.com")

        with pytest.raises(FileNotFoundError, match="Local file not found"):
            ssh.upload_file(non_existent_file, "/remote/path/test.txt")

    @patch("site_automator.ssh.subprocess.run")
    @patch("site_automator.ssh.resolve_ssh_host")
    @patch("site_automator.ssh.paramiko.SSHClient")
    def test_upload_directory_rsync_success(
        self, mock_ssh_client, mock_resolve, mock_subprocess, tmp_path
    ):
        """Test successful directory upload via rsync."""
        mock_resolve.return_value = ("192.168.1.1", None, None)
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        # Mock run_command for mkdir
        mock_stdout = Mock()
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stdout.read.return_value = b""
        mock_stderr = Mock()
        mock_stderr.read.return_value = b""
        mock_client_instance.exec_command.return_value = (
            None,
            mock_stdout,
            mock_stderr,
        )

        # Mock successful rsync
        mock_result = Mock()
        mock_result.stdout = "rsync output"
        mock_subprocess.return_value = mock_result

        # Create test directory
        test_dir = tmp_path / "test_upload"
        test_dir.mkdir()
        (test_dir / "file.txt").write_text("content")

        ssh = SSHConnection(host="example.com")
        ssh.upload_directory_rsync(test_dir, "/remote/path")

        # Verify mkdir was called
        assert any(
            "mkdir -p" in str(call)
            for call in mock_client_instance.exec_command.call_args_list
        )

        # Verify rsync was called
        mock_subprocess.assert_called_once()
        call_args = mock_subprocess.call_args
        rsync_cmd = call_args[0][0]

        assert rsync_cmd[0] == "rsync"
        assert "-avz" in rsync_cmd
        assert "--stats" in rsync_cmd
        assert rsync_cmd[-1] == "root@192.168.1.1:/remote/path"

    @patch("site_automator.ssh.resolve_ssh_host")
    @patch("site_automator.ssh.paramiko.SSHClient")
    def test_upload_directory_rsync_not_found_raises(
        self, mock_ssh_client, mock_resolve, tmp_path
    ):
        """Test upload_directory_rsync raises when directory doesn't exist."""
        mock_resolve.return_value = ("192.168.1.1", None, None)
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        non_existent_dir = tmp_path / "does-not-exist"

        ssh = SSHConnection(host="example.com")

        with pytest.raises(FileNotFoundError, match="Local directory not found"):
            ssh.upload_directory_rsync(non_existent_dir, "/remote/path")

    @patch("site_automator.ssh.resolve_ssh_host")
    @patch("site_automator.ssh.paramiko.SSHClient")
    def test_upload_directory_rsync_not_a_directory_raises(
        self, mock_ssh_client, mock_resolve, tmp_path
    ):
        """Test upload_directory_rsync raises when path is not a directory."""
        mock_resolve.return_value = ("192.168.1.1", None, None)
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        # Create a file, not a directory
        test_file = tmp_path / "file.txt"
        test_file.write_text("content")

        ssh = SSHConnection(host="example.com")

        with pytest.raises(ValueError, match="Path is not a directory"):
            ssh.upload_directory_rsync(test_file, "/remote/path")

    @patch("site_automator.ssh.subprocess.run")
    @patch("site_automator.ssh.resolve_ssh_host")
    @patch("site_automator.ssh.paramiko.SSHClient")
    def test_upload_directory_rsync_command_failure_raises(
        self, mock_ssh_client, mock_resolve, mock_subprocess, tmp_path
    ):
        """Test upload_directory_rsync raises when rsync command fails."""
        mock_resolve.return_value = ("192.168.1.1", None, None)
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        # Mock run_command for mkdir
        mock_stdout = Mock()
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stdout.read.return_value = b""
        mock_stderr = Mock()
        mock_stderr.read.return_value = b""
        mock_client_instance.exec_command.return_value = (
            None,
            mock_stdout,
            mock_stderr,
        )

        # Mock rsync failure
        from subprocess import CalledProcessError

        mock_subprocess.side_effect = CalledProcessError(
            returncode=1,
            cmd=["rsync"],
            stderr="rsync error",
        )

        # Create test directory
        test_dir = tmp_path / "test_upload"
        test_dir.mkdir()

        ssh = SSHConnection(host="example.com")

        with pytest.raises(RuntimeError, match="Rsync failed with exit code 1"):
            ssh.upload_directory_rsync(test_dir, "/remote/path")

    @patch("site_automator.ssh.subprocess.run")
    @patch("site_automator.ssh.resolve_ssh_host")
    @patch("site_automator.ssh.paramiko.SSHClient")
    def test_upload_directory_rsync_with_delete(
        self, mock_ssh_client, mock_resolve, mock_subprocess, tmp_path
    ):
        """Test upload_directory_rsync with delete flag."""
        mock_resolve.return_value = ("192.168.1.1", None, None)
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        # Mock run_command
        mock_stdout = Mock()
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stdout.read.return_value = b""
        mock_stderr = Mock()
        mock_stderr.read.return_value = b""
        mock_client_instance.exec_command.return_value = (
            None,
            mock_stdout,
            mock_stderr,
        )

        # Mock rsync
        mock_result = Mock()
        mock_result.stdout = "rsync output"
        mock_subprocess.return_value = mock_result

        # Create test directory
        test_dir = tmp_path / "test_upload"
        test_dir.mkdir()

        ssh = SSHConnection(host="example.com")
        ssh.upload_directory_rsync(test_dir, "/remote/path", delete=True)

        # Verify --delete flag is in command
        call_args = mock_subprocess.call_args
        rsync_cmd = call_args[0][0]
        assert "--delete" in rsync_cmd

    @patch("site_automator.ssh.subprocess.run")
    @patch("site_automator.ssh.resolve_ssh_host")
    @patch("site_automator.ssh.paramiko.SSHClient")
    def test_upload_directory_rsync_with_excludes(
        self, mock_ssh_client, mock_resolve, mock_subprocess, tmp_path
    ):
        """Test upload_directory_rsync with exclude patterns."""
        mock_resolve.return_value = ("192.168.1.1", None, None)
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        # Mock run_command
        mock_stdout = Mock()
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stdout.read.return_value = b""
        mock_stderr = Mock()
        mock_stderr.read.return_value = b""
        mock_client_instance.exec_command.return_value = (
            None,
            mock_stdout,
            mock_stderr,
        )

        # Mock rsync
        mock_result = Mock()
        mock_result.stdout = "rsync output"
        mock_subprocess.return_value = mock_result

        # Create test directory
        test_dir = tmp_path / "test_upload"
        test_dir.mkdir()

        ssh = SSHConnection(host="example.com")
        ssh.upload_directory_rsync(test_dir, "/remote/path", exclude=[".git/", "*.tmp"])

        # Verify exclude patterns are in command
        call_args = mock_subprocess.call_args
        rsync_cmd = call_args[0][0]
        cmd_str = " ".join(rsync_cmd)
        assert "--exclude .git/" in cmd_str
        assert "--exclude *.tmp" in cmd_str

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

    @patch("site_automator.ssh.resolve_ssh_host")
    @patch("site_automator.ssh.paramiko.SSHClient")
    def test_ensure_swap_already_exists(self, mock_ssh_client, mock_resolve):
        """Test ensure_swap skips when swap already exists."""
        mock_resolve.return_value = ("192.168.1.1", None, None)
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        # Mock exec_command to return swap exists
        mock_stdout = Mock()
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stdout.read.return_value = b"swap output"
        mock_stderr = Mock()
        mock_stderr.read.return_value = b""
        mock_client_instance.exec_command.return_value = (
            None,
            mock_stdout,
            mock_stderr,
        )

        ssh = SSHConnection(host="example.com")
        ssh.ensure_swap()

        # Should only call the check command
        assert mock_client_instance.exec_command.call_count == 1
        mock_client_instance.exec_command.assert_called_with("swapon --show")

    @patch("site_automator.ssh.resolve_ssh_host")
    @patch("site_automator.ssh.paramiko.SSHClient")
    def test_ensure_swap_creates_swap(self, mock_ssh_client, mock_resolve):
        """Test ensure_swap creates swap when not present."""
        mock_resolve.return_value = ("192.168.1.1", None, None)
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        call_count = [0]

        # Setup mock to return different values for different commands
        def exec_command_side_effect(command):
            call_count[0] += 1
            mock_stdout = Mock()
            mock_stderr = Mock()
            mock_stderr.read.return_value = b""

            if "swapon --show" in command:
                # No swap exists (empty output)
                mock_stdout.channel.recv_exit_status.return_value = 0
                mock_stdout.read.return_value = b""
            else:
                # All other commands succeed
                mock_stdout.channel.recv_exit_status.return_value = 0
                mock_stdout.read.return_value = b"success"

            return (None, mock_stdout, mock_stderr)

        mock_client_instance.exec_command.side_effect = exec_command_side_effect

        ssh = SSHConnection(host="example.com")
        ssh.ensure_swap(size_gb=4)

        # Should call multiple commands to create swap
        # 1. swapon --show (check)
        # 2. fallocate
        # 3. chmod
        # 4. mkswap
        # 5. swapon
        # 6. grep/echo fstab
        assert mock_client_instance.exec_command.call_count == 6

    @patch("site_automator.ssh.resolve_ssh_host")
    @patch("site_automator.ssh.paramiko.SSHClient")
    def test_ensure_git_safe_directory_configures_wildcard(
        self, mock_ssh_client, mock_resolve
    ):
        """Test that git safe.directory is configured with wildcard."""
        mock_resolve.return_value = ("192.168.1.1", None, None)
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        # Mock successful git config command
        mock_stdout = Mock()
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stdout.read.return_value = b""
        mock_stderr = Mock()
        mock_stderr.read.return_value = b""
        mock_client_instance.exec_command.return_value = (
            None,
            mock_stdout,
            mock_stderr,
        )

        ssh = SSHConnection(host="example.com")
        ssh.ensure_git_safe_directory()

        # Verify git config command was called with wildcard
        git_config_call = None
        for call in mock_client_instance.exec_command.call_args_list:
            if "git config --system --add safe.directory" in str(call):
                git_config_call = call
                break

        assert git_config_call is not None
        command = git_config_call[0][0]
        assert "git config --system --add safe.directory '*'" in command

    @patch("site_automator.ssh.resolve_ssh_host")
    @patch("site_automator.ssh.paramiko.SSHClient")
    def test_ensure_git_safe_directory_raises_on_failure(
        self, mock_ssh_client, mock_resolve
    ):
        """Test that failure to configure git raises RuntimeError."""
        mock_resolve.return_value = ("192.168.1.1", None, None)
        mock_client_instance = Mock()
        mock_ssh_client.return_value = mock_client_instance

        # Mock failed git config command
        mock_stdout = Mock()
        mock_stdout.channel.recv_exit_status.return_value = 1
        mock_stdout.read.return_value = b""
        mock_stderr = Mock()
        mock_stderr.read.return_value = b"git config failed"
        mock_client_instance.exec_command.return_value = (
            None,
            mock_stdout,
            mock_stderr,
        )

        ssh = SSHConnection(host="example.com")

        with pytest.raises(RuntimeError, match="Command failed with exit code 1"):
            ssh.ensure_git_safe_directory()
