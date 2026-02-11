import pytest
from unittest.mock import patch
from site_automator.tracking import PageviewTrackingSetup


@pytest.fixture
def tracking(wordops):
    """Create a PageviewTrackingSetup using the SSHConnection from a WordOpsProvisioner instance."""
    return PageviewTrackingSetup(wordops.ssh)


class TestUploadTrackingResources:
    """Test _upload_tracking_resources method."""

    def test_upload_tracking_plugin(self, tracking, mock_ssh_connection):
        """Test plugin is always uploaded (overwrites if exists)."""
        tracking._upload_tracking_resources()

        # Should upload 1 file using upload_file
        assert mock_ssh_connection.upload_file.call_count == 1

        # Verify upload_file was called with correct path
        call_args = mock_ssh_connection.upload_file.call_args[0]
        assert "/shared/" in call_args[1]  # remote path


class TestCreateEnvFile:
    """Test _create_env_file method."""

    def test_create_env_file_success(self, tracking, mock_ssh_connection):
        """Test _create_env_file creates .env with correct content."""
        tracking._create_env_file("example.com")

        mock_ssh_connection.run_command.assert_called_once()
        call_cmd = mock_ssh_connection.run_command.call_args[0][0]

        assert "echo" in call_cmd
        assert "/var/www/example.com/.env" in call_cmd
        assert "TRACKING_ENABLED=true" in call_cmd


class TestInstallPlugins:
    """Test _install_plugins method."""

    def test_install_plugins_success(self, tracking, mock_ssh_connection):
        """Test _install_plugins installs the plugin."""
        tracking._install_plugins("example.com")

        # Should install 1 plugin
        calls = [call[0][0] for call in mock_ssh_connection.run_command.call_args_list]
        plugin_calls = [cmd for cmd in calls if "wp plugin install" in cmd]

        assert len(plugin_calls) == 1
        assert any("pageview-tracking.zip" in cmd for cmd in plugin_calls)


class TestUpdateTrackConfig:
    """Test _update_track_config method."""

    @patch.dict(
        "os.environ",
        {
            "TRACKING_DATA_ROOT": "/var/lib/pageview-tracking",
            "TRACKING_EXCLUDE_IPS": "127.0.0.1,192.168.1.1",
            "TRACKING_EXCLUDE_IPS_CIDR": "10.0.0.0/8",
            "TRACKING_EXCLUDE_USER_AGENTS_EXACT": "BadBot",
            "TRACKING_EXCLUDE_USER_AGENTS_SUBSTRING": "bot",
        },
    )
    def test_update_track_config_success(self, tracking, mock_ssh_connection):
        """Test _update_track_config creates config file with env values."""
        # Capture file content when upload_file is called
        uploaded_content = None

        def capture_upload(local_path, remote_path):
            nonlocal uploaded_content
            with open(local_path, "r") as f:
                uploaded_content = f.read()

        mock_ssh_connection.upload_file.side_effect = capture_upload

        tracking._update_track_config("example.com")

        # Should upload file using upload_file
        mock_ssh_connection.upload_file.assert_called_once()

        # Verify remote path
        call_args = mock_ssh_connection.upload_file.call_args[0]
        remote_path = call_args[1]
        assert "track_config.php" in remote_path
        assert "example.com" in remote_path

        # Verify WordPress default path calculates correct relative path
        # WordPress: htdocs/wp-content/plugins/pageview-tracking/ -> 4 levels up
        assert uploaded_content is not None
        assert "'env_file' => '../../../../.env'" in uploaded_content

    @patch.dict(
        "os.environ",
        {
            "TRACKING_DATA_ROOT": "/var/lib/pageview-tracking",
        },
    )
    def test_update_track_config_custom_path(self, tracking, mock_ssh_connection):
        """Test _update_track_config with custom config path."""
        # Capture file content when upload_file is called
        uploaded_content = None

        def capture_upload(local_path, remote_path):
            nonlocal uploaded_content
            with open(local_path, "r") as f:
                uploaded_content = f.read()

        mock_ssh_connection.upload_file.side_effect = capture_upload

        custom_path = "/var/www/example.com/static/pageview-tracking/track_config.php"
        tracking._update_track_config("example.com", config_path=custom_path)

        # Should upload file using upload_file
        mock_ssh_connection.upload_file.assert_called_once()

        # Verify custom path was used
        call_args = mock_ssh_connection.upload_file.call_args[0]
        remote_path = call_args[1]
        assert remote_path == custom_path

        # Verify Hugo path calculates correct relative path
        # Hugo: static/pageview-tracking/ -> 2 levels up
        assert uploaded_content is not None
        assert "'env_file' => '../../.env'" in uploaded_content


class TestCreateDataDirectory:
    """Test _create_data_directory method."""

    def test_create_data_directory_success(self, tracking, mock_ssh_connection):
        """Test _create_data_directory creates directory with proper permissions."""
        tracking._create_data_directory()

        # Should execute 6 commands: 3x mkdir, chown, chmod, chmod g+s
        assert mock_ssh_connection.run_command.call_count == 6
        calls = [call[0][0] for call in mock_ssh_connection.run_command.call_args_list]

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

    def test_create_data_directory_idempotent(self, tracking, mock_ssh_connection):
        """Test _create_data_directory is idempotent (can run multiple times)."""
        # Run twice
        tracking._create_data_directory()
        tracking._create_data_directory()

        # Should execute 6 commands each time (12 total)
        assert mock_ssh_connection.run_command.call_count == 12


class TestUploadProcessingScripts:
    """Test _upload_processing_scripts method."""

    def test_upload_processing_scripts(self, tracking, mock_ssh_connection):
        """Test _upload_processing_scripts uploads scripts and makes them executable."""
        tracking._upload_processing_scripts()

        # Should upload 2 scripts using upload_file
        assert mock_ssh_connection.upload_file.call_count == 2

        # Should make each script executable
        calls = [call[0][0] for call in mock_ssh_connection.run_command.call_args_list]
        assert any(
            "chmod +x" in cmd and "process_daily_logs.py" in cmd for cmd in calls
        )
        assert any(
            "chmod +x" in cmd and "generate_dummy_logs.py" in cmd for cmd in calls
        )


class TestSetupCronJob:
    """Test _setup_cron_job method."""

    def test_setup_cron_job(self, tracking, mock_ssh_connection):
        """Test _setup_cron_job adds cron entry idempotently."""
        tracking._setup_cron_job()

        call_args = mock_ssh_connection.run_command.call_args[0][0]
        assert "process_daily_logs.py" in call_args
        assert "crontab" in call_args


class TestSetupTrackingWordPress:
    """Test setup_tracking_wordpress method."""

    @patch("site_automator.tracking.PageviewTrackingSetup._setup_cron_job")
    @patch("site_automator.tracking.PageviewTrackingSetup._upload_processing_scripts")
    @patch("site_automator.tracking.PageviewTrackingSetup._upload_tracking_resources")
    @patch.dict(
        "os.environ",
        {
            "TRACKING_DATA_ROOT": "/var/lib/pageview-tracking",
            "TRACKING_EXCLUDE_IPS": "",
            "TRACKING_EXCLUDE_IPS_CIDR": "",
            "TRACKING_EXCLUDE_USER_AGENTS_EXACT": "",
            "TRACKING_EXCLUDE_USER_AGENTS_SUBSTRING": "",
        },
        clear=True,
    )
    def test_setup_tracking_wordpress_with_defaults(
        self, mock_upload, mock_upload_scripts, mock_cron, tracking, mock_ssh_connection
    ):
        """Test setup_tracking_wordpress executes all steps."""
        tracking.setup_tracking_wordpress("example.com")

        # Should call all mocked methods
        mock_upload.assert_called_once()
        mock_upload_scripts.assert_called_once()
        mock_cron.assert_called_once()

        calls = [call[0][0] for call in mock_ssh_connection.run_command.call_args_list]

        # Verify key steps were executed
        assert any(".env" in cmd for cmd in calls)
        assert any("wp plugin install" in cmd for cmd in calls)
        # Note: track_config.php is uploaded via upload_file, not run_command
        assert any("sudo mkdir -p /var/lib/pageview-tracking" in cmd for cmd in calls)


class TestSetupTrackingHugo:
    """Test setup_tracking_hugo method."""

    @patch("site_automator.tracking.PageviewTrackingSetup._setup_cron_job")
    @patch("site_automator.tracking.PageviewTrackingSetup._upload_processing_scripts")
    @patch("site_automator.tracking.PageviewTrackingSetup._create_data_directory")
    @patch("site_automator.tracking.PageviewTrackingSetup._update_track_config")
    @patch("site_automator.tracking.PageviewTrackingSetup._create_env_file")
    def test_setup_tracking_hugo_critical_path(
        self,
        mock_create_env,
        mock_update_config,
        mock_create_data,
        mock_upload_scripts,
        mock_cron,
        tracking,
        mock_ssh_connection,
    ):
        """Test setup_tracking_hugo executes all steps with correct paths."""
        tracking.setup_tracking_hugo("example.com")

        # Verify tracking directory creation
        calls = [call[0][0] for call in mock_ssh_connection.run_command.call_args_list]
        assert any(
            "mkdir -p /var/www/example.com/static/pageview-tracking" in cmd
            for cmd in calls
        )

        # Verify rsync upload was called
        mock_ssh_connection.upload_directory_rsync.assert_called_once()
        rsync_args = mock_ssh_connection.upload_directory_rsync.call_args
        assert "pageview-tracking" in str(rsync_args[0][0])  # Local path
        assert (
            "/var/www/example.com/static/pageview-tracking" == rsync_args[0][1]
        )  # Remote path
        assert rsync_args[1]["exclude"] == ["pageview-tracking.php"]

        # Verify all backend setup methods were called
        mock_create_env.assert_called_once_with("example.com")
        mock_update_config.assert_called_once_with(
            "example.com",
            "/var/www/example.com/static/pageview-tracking/track_config.php",
        )
        mock_create_data.assert_called_once()
        mock_upload_scripts.assert_called_once()
        mock_cron.assert_called_once()
