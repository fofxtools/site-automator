"""Unit tests for PageviewTrackingSetup - Critical path only."""

import pytest
from unittest.mock import patch
from wordops_provisioner.tracking import PageviewTrackingSetup


@pytest.fixture
def tracking(provisioner):
    """Create a PageviewTrackingSetup wrapping the provisioner."""
    return PageviewTrackingSetup(provisioner)


class TestCreateDbUser:
    """Test _create_db_user method."""

    def test_create_db_user_success(self, tracking, mock_ssh_client):
        """Test _create_db_user creates user and returns password."""
        password = tracking._create_db_user("db_admin")

        # Password should be 32 characters, alphanumeric only
        assert len(password) == 32
        assert password.isalnum()

        # Should execute 4 commands: CREATE USER, ALTER USER, GRANT, FLUSH
        assert mock_ssh_client.exec_command.call_count == 4
        calls = [call[0][0] for call in mock_ssh_client.exec_command.call_args_list]

        assert any("CREATE USER IF NOT EXISTS" in cmd for cmd in calls)
        assert any("ALTER USER" in cmd for cmd in calls)
        assert any("GRANT ALL PRIVILEGES" in cmd for cmd in calls)
        assert any("FLUSH PRIVILEGES" in cmd for cmd in calls)


class TestCreateDatabase:
    """Test _create_database method."""

    def test_create_database_success(self, tracking, mock_ssh_client):
        """Test _create_database creates database."""
        tracking._create_database("tracking")

        mock_ssh_client.exec_command.assert_called_once()
        call_cmd = mock_ssh_client.exec_command.call_args[0][0]

        assert "CREATE DATABASE IF NOT EXISTS" in call_cmd
        assert "tracking" in call_cmd


class TestCreateTables:
    """Test _create_tables method."""

    def test_create_tables_success(self, tracking, mock_ssh_client):
        """Test _create_tables executes SQL files."""
        tracking._create_tables("tracking", "db_admin", "password123")

        # Should execute 2 SQL files
        calls = [call[0][0] for call in mock_ssh_client.exec_command.call_args_list]
        mysql_calls = [cmd for cmd in calls if "mysql" in cmd and "/shared/" in cmd]

        assert len(mysql_calls) == 2
        assert any("tracking_pageviews.sql" in cmd for cmd in mysql_calls)
        assert any("tracking_pageviews_daily.sql" in cmd for cmd in mysql_calls)


class TestCreateEnvFile:
    """Test _create_env_file method."""

    def test_create_env_file_success(self, tracking, mock_ssh_client):
        """Test _create_env_file creates .env with correct content."""
        tracking._create_env_file("example.com", "tracking", "db_admin", "pass123")

        mock_ssh_client.exec_command.assert_called_once()
        call_cmd = mock_ssh_client.exec_command.call_args[0][0]

        assert "echo" in call_cmd
        assert "/var/www/example.com/.env" in call_cmd
        assert "TRACKING_ENABLED=true" in call_cmd
        assert "TRACKING_DB_NAME=tracking" in call_cmd
        assert "TRACKING_DB_USER=db_admin" in call_cmd
        assert "TRACKING_DB_PASSWORD=pass123" in call_cmd


class TestInstallPlugins:
    """Test _install_plugins method."""

    def test_install_plugins_success(self, tracking, mock_ssh_client):
        """Test _install_plugins installs all three plugins."""
        tracking._install_plugins("example.com")

        # Should install 3 plugins
        calls = [call[0][0] for call in mock_ssh_client.exec_command.call_args_list]
        plugin_calls = [cmd for cmd in calls if "wp plugin install" in cmd]

        assert len(plugin_calls) == 3
        assert any("pageview-tracking-core.zip" in cmd for cmd in plugin_calls)
        assert any("pageview-tracking.zip" in cmd for cmd in plugin_calls)
        assert any("pageview-tracking-daily.zip" in cmd for cmd in plugin_calls)


class TestUpdateTrackConfig:
    """Test _update_track_config method."""

    @patch.dict(
        "os.environ",
        {
            "TRACKING_DB_CONFIG_FILE": "../../../.env",
            "TRACKING_EXCLUDE_IPS": "127.0.0.1,192.168.1.1",
            "TRACKING_EXCLUDE_IPS_CIDR": "10.0.0.0/8",
            "TRACKING_EXCLUDE_USER_AGENTS_EXACT": "BadBot",
            "TRACKING_EXCLUDE_USER_AGENTS_SUBSTRING": "bot",
        },
    )
    def test_update_track_config_success(self, tracking, mock_ssh_client):
        """Test _update_track_config creates config file with env values."""
        tracking._update_track_config("example.com")

        mock_ssh_client.exec_command.assert_called_once()
        call_cmd = mock_ssh_client.exec_command.call_args[0][0]

        assert "echo" in call_cmd
        assert "track_config.php" in call_cmd
        assert "../../../.env" in call_cmd
        assert "127.0.0.1" in call_cmd
        assert "192.168.1.1" in call_cmd
        assert "10.0.0.0/8" in call_cmd
        assert "BadBot" in call_cmd
        assert "bot" in call_cmd


class TestSetupTracking:
    """Test setup_tracking method."""

    @patch.dict(
        "os.environ",
        {
            "TRACKING_DB_CONFIG_FILE": "auto",
            "TRACKING_EXCLUDE_IPS": "",
            "TRACKING_EXCLUDE_IPS_CIDR": "",
            "TRACKING_EXCLUDE_USER_AGENTS_EXACT": "",
            "TRACKING_EXCLUDE_USER_AGENTS_SUBSTRING": "",
        },
    )
    def test_setup_tracking_success(self, tracking, mock_ssh_client):
        """Test setup_tracking executes all steps."""
        tracking.setup_tracking("example.com")

        # Should execute multiple commands for all steps
        assert mock_ssh_client.exec_command.call_count > 5

        calls = [call[0][0] for call in mock_ssh_client.exec_command.call_args_list]

        # Verify key steps were executed
        assert any("CREATE USER" in cmd for cmd in calls)
        assert any("CREATE DATABASE" in cmd for cmd in calls)
        assert any("mysql" in cmd and "/shared/" in cmd for cmd in calls)
        assert any(".env" in cmd for cmd in calls)
        assert any("wp plugin install" in cmd for cmd in calls)
        assert any("track_config.php" in cmd for cmd in calls)
