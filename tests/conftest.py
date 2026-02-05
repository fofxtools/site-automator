"""Shared pytest fixtures for Site Automator tests."""

import pytest
from unittest.mock import Mock, patch

from site_automator.wordops import WordOpsProvisioner
from site_automator.wordpress import WordPressDeployer
from site_automator.tracking import PageviewTrackingSetup


@pytest.fixture
def mock_ssh_connection():
    """Mock SSHConnection with default success behavior."""
    with patch("site_automator.wordops.SSHConnection") as mock_class:
        mock_instance = Mock()
        mock_class.return_value = mock_instance

        # Setup default successful command execution
        mock_instance.run_command.return_value = ("Success", 0)

        yield mock_instance


@pytest.fixture
def wordops(mock_ssh_connection):
    """Create a WordOpsProvisioner with mocked SSH."""
    return WordOpsProvisioner(host="example.com")


@pytest.fixture
def wordpress(wordops):
    """Create a WordPressDeployer using a WordOpsProvisioner instance."""
    return WordPressDeployer(wordops)


@pytest.fixture
def tracking(wordops):
    """Create a PageviewTrackingSetup using a WordOpsProvisioner instance."""
    return PageviewTrackingSetup(wordops)
