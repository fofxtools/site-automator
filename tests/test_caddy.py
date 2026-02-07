import pytest
from unittest.mock import Mock, patch

from site_automator.caddy import CaddyProvisioner


class TestInit:
    """Test __init__ method."""

    @patch("site_automator.caddy.SSHConnection")
    def test_init_stores_host(self, mock_ssh_connection):
        """Test that host is stored correctly."""
        caddy = CaddyProvisioner(host="example.com")

        assert caddy.host == "example.com"
        assert caddy.user is None
        mock_ssh_connection.assert_called_once_with("example.com", None)

    @patch("site_automator.caddy.SSHConnection")
    def test_init_stores_explicit_user(self, mock_ssh_connection):
        """Test that explicit user is stored correctly."""
        caddy = CaddyProvisioner(host="example.com", user="deploy")

        assert caddy.host == "example.com"
        assert caddy.user == "deploy"
        mock_ssh_connection.assert_called_once_with("example.com", "deploy")


class TestClose:
    """Test close method."""

    @patch("site_automator.caddy.SSHConnection")
    def test_close_calls_ssh_close(self, mock_ssh_connection):
        """Test that close() calls ssh.close()."""
        mock_ssh = Mock()
        mock_ssh_connection.return_value = mock_ssh

        caddy = CaddyProvisioner(host="example.com")
        caddy.close()

        mock_ssh.close.assert_called_once()


class TestReloadCaddy:
    """Test reload_caddy method."""

    @patch("site_automator.caddy.SSHConnection")
    def test_validates_before_reload(self, mock_ssh_connection):
        """Test that validation happens before reload."""
        mock_ssh = Mock()
        mock_ssh_connection.return_value = mock_ssh

        caddy = CaddyProvisioner(host="example.com")
        caddy.reload_caddy()

        calls = [call[0][0] for call in mock_ssh.run_command.call_args_list]
        assert calls[0] == "caddy validate --config /etc/caddy/Caddyfile"
        assert calls[1] == "caddy reload --config /etc/caddy/Caddyfile"


class TestEnsureCaddyfileImport:
    """Test ensure_caddyfile_import method."""

    @patch("site_automator.caddy.SSHConnection")
    def test_creates_directories(self, mock_ssh_connection):
        """Test that directories are created."""
        mock_ssh = Mock()
        mock_ssh.run_command.return_value = ("", 1)  # grep returns 1 (not found)
        mock_ssh_connection.return_value = mock_ssh

        caddy = CaddyProvisioner(host="example.com")
        caddy.ensure_caddyfile_import()

        calls = [call[0][0] for call in mock_ssh.run_command.call_args_list]
        assert "mkdir -p /etc/caddy/sites-available" in calls
        assert "mkdir -p /etc/caddy/sites-enabled" in calls

    @patch("site_automator.caddy.SSHConnection")
    def test_adds_import_directive_when_missing(self, mock_ssh_connection):
        """Test that import directive is added when missing."""
        mock_ssh = Mock()
        mock_ssh.run_command.return_value = ("", 1)  # grep returns 1 (not found)
        mock_ssh_connection.return_value = mock_ssh

        caddy = CaddyProvisioner(host="example.com")
        caddy.ensure_caddyfile_import()

        calls = [call[0][0] for call in mock_ssh.run_command.call_args_list]
        assert any("echo 'import sites-enabled/*'" in call for call in calls)

    @patch("site_automator.caddy.SSHConnection")
    def test_skips_import_when_exists(self, mock_ssh_connection):
        """Test that import directive is not added when it exists."""
        mock_ssh = Mock()
        mock_ssh.run_command.return_value = ("", 0)  # grep returns 0 (found)
        mock_ssh_connection.return_value = mock_ssh

        caddy = CaddyProvisioner(host="example.com")
        caddy.ensure_caddyfile_import()

        calls = [call[0][0] for call in mock_ssh.run_command.call_args_list]
        assert not any("echo 'import sites-enabled/*'" in call for call in calls)

    @patch("site_automator.caddy.SSHConnection")
    def test_validates_config(self, mock_ssh_connection):
        """Test that config is validated."""
        mock_ssh = Mock()
        mock_ssh.run_command.return_value = ("", 0)
        mock_ssh_connection.return_value = mock_ssh

        caddy = CaddyProvisioner(host="example.com")
        caddy.ensure_caddyfile_import()

        calls = [call[0][0] for call in mock_ssh.run_command.call_args_list]
        assert "caddy validate --config /etc/caddy/Caddyfile" in calls


class TestEnableDomain:
    """Test enable_domain method."""

    @patch("site_automator.caddy.SSHConnection")
    def test_rejects_invalid_domain_with_slash(self, mock_ssh_connection):
        """Test that domain with slash is rejected."""
        caddy = CaddyProvisioner(host="example.com")

        with pytest.raises(ValueError, match="Invalid domain"):
            caddy.enable_domain("example.com/path")

    @patch("site_automator.caddy.SSHConnection")
    def test_rejects_empty_domain(self, mock_ssh_connection):
        """Test that empty domain is rejected."""
        caddy = CaddyProvisioner(host="example.com")

        with pytest.raises(ValueError, match="Invalid domain"):
            caddy.enable_domain("")

    @patch("site_automator.caddy.SSHConnection")
    def test_rejects_whitespace_only_domain(self, mock_ssh_connection):
        """Test that whitespace-only domain is rejected."""
        caddy = CaddyProvisioner(host="example.com")

        with pytest.raises(ValueError, match="Invalid domain"):
            caddy.enable_domain("   ")

    @patch("site_automator.caddy.SSHConnection")
    def test_rejects_domain_with_null_byte(self, mock_ssh_connection):
        """Test that domain with null byte is rejected."""
        caddy = CaddyProvisioner(host="example.com")

        with pytest.raises(ValueError, match="Invalid domain"):
            caddy.enable_domain("example.com\x00")

    @patch("site_automator.caddy.SSHConnection")
    def test_rejects_domain_with_whitespace(self, mock_ssh_connection):
        """Test that domains with leading/trailing whitespace are rejected."""
        mock_ssh = Mock()
        mock_ssh.run_command.return_value = ("", 0)
        mock_ssh_connection.return_value = mock_ssh

        caddy = CaddyProvisioner(host="example.com")

        with pytest.raises(ValueError, match="Invalid domain"):
            caddy.enable_domain("  test.com  ")

    @patch("site_automator.caddy.SSHConnection")
    def test_creates_web_root_with_permissions(self, mock_ssh_connection):
        """Test that web root is created with correct permissions."""
        mock_ssh = Mock()
        mock_ssh.run_command.return_value = ("", 0)
        mock_ssh_connection.return_value = mock_ssh

        caddy = CaddyProvisioner(host="example.com")
        caddy.enable_domain("test.com")

        calls = [call[0][0] for call in mock_ssh.run_command.call_args_list]
        assert "mkdir -p /var/www/test.com/public" in calls
        assert "chown -R caddy:caddy /var/www/test.com" in calls
        assert "chmod -R 755 /var/www/test.com" in calls

    @patch("site_automator.caddy.SSHConnection")
    def test_writes_site_config(self, mock_ssh_connection):
        """Test that site config is written."""
        mock_ssh = Mock()
        mock_ssh.run_command.return_value = ("", 0)
        mock_ssh_connection.return_value = mock_ssh

        caddy = CaddyProvisioner(host="example.com")
        caddy.enable_domain("test.com")

        # Should upload config file using upload_file
        mock_ssh.upload_file.assert_called_once()

        # Verify remote path
        call_args = mock_ssh.upload_file.call_args[0]
        remote_path = call_args[1]
        assert "/etc/caddy/sites-available/test.com.caddy" in remote_path

    @patch("site_automator.caddy.SSHConnection")
    def test_creates_symlink(self, mock_ssh_connection):
        """Test that symlink is created."""
        mock_ssh = Mock()
        mock_ssh.run_command.return_value = ("", 0)
        mock_ssh_connection.return_value = mock_ssh

        caddy = CaddyProvisioner(host="example.com")
        caddy.enable_domain("test.com")

        calls = [call[0][0] for call in mock_ssh.run_command.call_args_list]
        symlink_call = [c for c in calls if "ln -sf" in c]
        assert len(symlink_call) == 1
        assert "/etc/caddy/sites-available/test.com.caddy" in symlink_call[0]
        assert "/etc/caddy/sites-enabled/test.com.caddy" in symlink_call[0]

    @patch("site_automator.caddy.SSHConnection")
    def test_validates_and_reloads(self, mock_ssh_connection):
        """Test that Caddy is validated and reloaded."""
        mock_ssh = Mock()
        mock_ssh.run_command.return_value = ("", 0)
        mock_ssh_connection.return_value = mock_ssh

        caddy = CaddyProvisioner(host="example.com")
        caddy.enable_domain("test.com")

        calls = [call[0][0] for call in mock_ssh.run_command.call_args_list]
        # Should validate and reload twice: once in ensure_caddyfile_import, once in enable_domain
        validate_calls = [c for c in calls if "caddy validate" in c]
        reload_calls = [c for c in calls if "caddy reload" in c]
        assert len(validate_calls) == 2
        assert len(reload_calls) == 1


class TestDisableDomain:
    """Test disable_domain method."""

    @patch("site_automator.caddy.SSHConnection")
    def test_rejects_invalid_domain_with_slash(self, mock_ssh_connection):
        """Test that domain with slash is rejected."""
        caddy = CaddyProvisioner(host="example.com")

        with pytest.raises(ValueError, match="Invalid domain"):
            caddy.disable_domain("example.com/path")

    @patch("site_automator.caddy.SSHConnection")
    def test_rejects_empty_domain(self, mock_ssh_connection):
        """Test that empty domain is rejected."""
        caddy = CaddyProvisioner(host="example.com")

        with pytest.raises(ValueError, match="Invalid domain"):
            caddy.disable_domain("")

    @patch("site_automator.caddy.SSHConnection")
    def test_rejects_whitespace_only_domain(self, mock_ssh_connection):
        """Test that whitespace-only domain is rejected."""
        caddy = CaddyProvisioner(host="example.com")

        with pytest.raises(ValueError, match="Invalid domain"):
            caddy.disable_domain("   ")

    @patch("site_automator.caddy.SSHConnection")
    def test_removes_symlink(self, mock_ssh_connection):
        """Test that symlink is removed."""
        mock_ssh = Mock()
        mock_ssh.run_command.return_value = ("", 0)
        mock_ssh_connection.return_value = mock_ssh

        caddy = CaddyProvisioner(host="example.com")
        caddy.disable_domain("test.com")

        calls = [call[0][0] for call in mock_ssh.run_command.call_args_list]
        assert "rm -f /etc/caddy/sites-enabled/test.com.caddy" in calls

    @patch("site_automator.caddy.SSHConnection")
    def test_validates_and_reloads(self, mock_ssh_connection):
        """Test that Caddy is validated and reloaded."""
        mock_ssh = Mock()
        mock_ssh.run_command.return_value = ("", 0)
        mock_ssh_connection.return_value = mock_ssh

        caddy = CaddyProvisioner(host="example.com")
        caddy.disable_domain("test.com")

        calls = [call[0][0] for call in mock_ssh.run_command.call_args_list]
        assert "caddy validate --config /etc/caddy/Caddyfile" in calls
        assert "caddy reload --config /etc/caddy/Caddyfile" in calls
