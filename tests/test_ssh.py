"""Tests for SSH config resolution."""

from unittest.mock import patch

from site_automator.ssh import resolve_ssh_host


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
