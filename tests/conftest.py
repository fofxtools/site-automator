"""Shared pytest fixtures for Site Automator tests."""

import pytest
from unittest.mock import Mock, patch

from site_automator.wordops import WordOpsProvisioner
from site_automator.wordpress import WordPressDeployer
from site_automator.tracking import PageviewTrackingSetup


@pytest.fixture
def mock_ssh_client():
    """Mock paramiko SSHClient with default success behavior."""
    with patch("site_automator.wordops.paramiko.SSHClient") as mock_class:
        mock_instance = Mock()
        mock_class.return_value = mock_instance

        # Setup default successful command execution
        mock_stdout = Mock()
        mock_stderr = Mock()
        mock_channel = Mock()
        mock_stdout.channel = mock_channel
        mock_channel.recv_exit_status.return_value = 0
        mock_stdout.read.return_value = b"Success"
        mock_stderr.read.return_value = b""

        mock_instance.exec_command.return_value = (None, mock_stdout, mock_stderr)

        # Expose useful attributes for tests to customize
        mock_instance._mock_stdout = mock_stdout
        mock_instance._mock_stderr = mock_stderr
        mock_instance._mock_channel = mock_channel

        yield mock_instance


@pytest.fixture
def wordops(mock_ssh_client):
    """Create a WordOpsProvisioner with mocked SSH."""
    with patch("site_automator.wordops.resolve_ssh_host") as mock_resolve:
        mock_resolve.return_value = ("example.com", None, None)
        return WordOpsProvisioner(host="example.com")


@pytest.fixture
def wordpress(wordops):
    """Create a WordPressDeployer using a WordOpsProvisioner instance."""
    return WordPressDeployer(wordops)


@pytest.fixture
def tracking(wordops):
    """Create a PageviewTrackingSetup using a WordOpsProvisioner instance."""
    return PageviewTrackingSetup(wordops)
