"""Shared pytest fixtures for WordOps Provisioner tests."""

import pytest
from unittest.mock import Mock, patch

from wordops_provisioner.provisioner import WordOpsProvisioner
from wordops_provisioner.deployer import WordPressDeployer


@pytest.fixture
def mock_ssh_client():
    """Mock paramiko SSHClient with default success behavior."""
    with patch("wordops_provisioner.provisioner.paramiko.SSHClient") as mock_class:
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
def provisioner(mock_ssh_client):
    """Create a WordOpsProvisioner with mocked SSH."""
    return WordOpsProvisioner(host="example.com", password="pass")


@pytest.fixture
def deployer(provisioner):
    """Create a WordPressDeployer wrapping the provisioner."""
    return WordPressDeployer(provisioner)
