import pytest
from unittest.mock import patch, Mock
from site_automator.tracking import PageviewTrackingSetup


@pytest.fixture
def tracking(wordops):
    """Create a PageviewTrackingSetup using a WordOpsProvisioner instance."""
    return PageviewTrackingSetup(wordops)


class TestUploadTrackingResources:
    """Test _upload_tracking_resources method."""

    def test_upload_tracking_plugin(self, tracking, mock_ssh_client):
        """Test plugin is always uploaded (overwrites if exists)."""
        # Mock SFTP
        mock_sftp = Mock()
        mock_ssh_client.open_sftp.return_value = mock_sftp

        # Mock exit code: 0 for mkdir
        mock_ssh_client._mock_channel.recv_exit_status.return_value = 0

        tracking._upload_tracking_resources()

        # Should create remote directory
        calls = [call[0][0] for call in mock_ssh_client.exec_command.call_args_list]
        assert any("mkdir -p" in cmd and "/shared" in cmd for cmd in calls)

        # Should always upload 1 file (overwrites if exists)
        assert mock_sftp.put.call_count == 1


class TestCreateEnvFile:
    """Test _create_env_file method."""

    def test_create_env_file_success(self, tracking, mock_ssh_client):
        """Test _create_env_file creates .env with correct content."""
        tracking._create_env_file("example.com")

        mock_ssh_client.exec_command.assert_called_once()
        call_cmd = mock_ssh_client.exec_command.call_args[0][0]

        assert "echo" in call_cmd
        assert "/var/www/example.com/.env" in call_cmd
        assert "TRACKING_ENABLED=true" in call_cmd


class TestInstallPlugins:
    """Test _install_plugins method."""

    def test_install_plugins_success(self, tracking, mock_ssh_client):
        """Test _install_plugins installs the plugin."""
        tracking._install_plugins("example.com")

        # Should install 1 plugin
        calls = [call[0][0] for call in mock_ssh_client.exec_command.call_args_list]
        plugin_calls = [cmd for cmd in calls if "wp plugin install" in cmd]

        assert len(plugin_calls) == 1
        assert any("pageview-tracking.zip" in cmd for cmd in plugin_calls)


class TestUpdateTrackConfig:
    """Test _update_track_config method."""

    @patch.dict(
        "os.environ",
        {
            "TRACKING_ENV_FILE": "../../../../.env",
            "TRACKING_DATA_ROOT": "/var/lib/pageview-tracking",
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
        assert "../../../../.env" in call_cmd
        assert "/var/lib/pageview-tracking" in call_cmd
        assert "127.0.0.1" in call_cmd
        assert "192.168.1.1" in call_cmd
        assert "10.0.0.0/8" in call_cmd
        assert "BadBot" in call_cmd
        assert "bot" in call_cmd


class TestCreateDataDirectory:
    """Test _create_data_directory method."""

    def test_create_data_directory_success(self, tracking, mock_ssh_client):
        """Test _create_data_directory creates directory with proper permissions."""
        # Mock exit codes: 0 for all commands (mkdir -p is idempotent)
        exit_codes = [
            0,  # mkdir raw
            0,  # mkdir agg/daily
            0,  # mkdir scripts
            0,  # chown
            0,  # chmod
            0,  # chmod g+s
        ]
        mock_ssh_client._mock_channel.recv_exit_status.side_effect = exit_codes

        tracking._create_data_directory()

        # Should execute 6 commands: 3x mkdir, chown, chmod, chmod g+s
        assert mock_ssh_client.exec_command.call_count == 6
        calls = [call[0][0] for call in mock_ssh_client.exec_command.call_args_list]

        assert any(
            "sudo mkdir -p /var/lib/pageview-tracking/raw" in cmd for cmd in calls
        )
        assert any(
            "sudo mkdir -p /var/lib/pageview-tracking/agg/daily" in cmd for cmd in calls
        )
        assert any(
            "sudo mkdir -p /var/lib/pageview-tracking/scripts" in cmd for cmd in calls
        )
        assert any("sudo chown" in cmd and "www-data:www-data" in cmd for cmd in calls)
        assert any("sudo chmod -R 775" in cmd for cmd in calls)
        assert any("sudo chmod g+s" in cmd for cmd in calls)

    def test_create_data_directory_idempotent(self, tracking, mock_ssh_client):
        """Test _create_data_directory is idempotent (can run multiple times)."""
        # Mock exit code: 0 for all commands (mkdir -p succeeds even if exists)
        mock_ssh_client._mock_channel.recv_exit_status.return_value = 0

        # Run twice
        tracking._create_data_directory()
        tracking._create_data_directory()

        # Should execute 6 commands each time (12 total)
        assert mock_ssh_client.exec_command.call_count == 12


class TestUploadProcessingScripts:
    """Test _upload_processing_scripts method."""

    def test_upload_processing_scripts(self, tracking, mock_ssh_client):
        """Test _upload_processing_scripts uploads scripts and makes them executable."""
        mock_sftp = Mock()
        mock_ssh_client.open_sftp.return_value = mock_sftp

        tracking._upload_processing_scripts()

        # Should upload 2 scripts
        assert mock_sftp.put.call_count == 2

        # Should make each script executable
        calls = [call[0][0] for call in mock_ssh_client.exec_command.call_args_list]
        assert any(
            "chmod +x" in cmd and "process_daily_logs.py" in cmd for cmd in calls
        )
        assert any(
            "chmod +x" in cmd and "generate_dummy_logs.py" in cmd for cmd in calls
        )


class TestSetupCronJob:
    """Test _setup_cron_job method."""

    def test_setup_cron_job(self, tracking, mock_ssh_client):
        """Test _setup_cron_job adds cron entry idempotently."""
        tracking._setup_cron_job()

        call_args = mock_ssh_client.exec_command.call_args[0][0]
        assert "process_daily_logs.py" in call_args
        assert "crontab" in call_args


class TestSetupTracking:
    """Test setup_tracking method."""

    @patch("site_automator.tracking.PageviewTrackingSetup._setup_cron_job")
    @patch("site_automator.tracking.PageviewTrackingSetup._upload_processing_scripts")
    @patch("site_automator.tracking.PageviewTrackingSetup._upload_tracking_resources")
    @patch.dict(
        "os.environ",
        {
            "TRACKING_ENV_FILE": "../../../../.env",
            "TRACKING_DATA_ROOT": "/var/lib/pageview-tracking",
            "TRACKING_EXCLUDE_IPS": "",
            "TRACKING_EXCLUDE_IPS_CIDR": "",
            "TRACKING_EXCLUDE_USER_AGENTS_EXACT": "",
            "TRACKING_EXCLUDE_USER_AGENTS_SUBSTRING": "",
        },
        clear=True,
    )
    def test_setup_tracking_with_defaults(
        self, mock_upload, mock_upload_scripts, mock_cron, tracking, mock_ssh_client
    ):
        """Test setup_tracking executes all steps."""
        # Mock exit codes for all commands to succeed
        # .env creation, plugin install, track_config, 3x mkdir, chown, chmod, chmod g+s
        exit_codes = [0, 0, 0, 0, 0, 0, 0, 0, 0]
        mock_ssh_client._mock_channel.recv_exit_status.side_effect = exit_codes

        tracking.setup_tracking("example.com")

        # Should call all mocked methods
        mock_upload.assert_called_once()
        mock_upload_scripts.assert_called_once()
        mock_cron.assert_called_once()

        calls = [call[0][0] for call in mock_ssh_client.exec_command.call_args_list]

        # Verify key steps were executed
        assert any(".env" in cmd for cmd in calls)
        assert any("wp plugin install" in cmd for cmd in calls)
        assert any("track_config.php" in cmd for cmd in calls)
        assert any("sudo mkdir -p /var/lib/pageview-tracking" in cmd for cmd in calls)
