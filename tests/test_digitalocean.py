"""Unit tests for DigitalOceanDNSManager - Critical path only."""

import pytest
from unittest.mock import Mock, patch

from wordops_provisioner import DigitalOceanDNSManager


class TestInit:
    """Test __init__ method."""

    def test_init_stores_token(self):
        """Test that token is stored correctly."""
        dns = DigitalOceanDNSManager(digitalocean_token="test_token")

        assert dns.digitalocean_token == "test_token"
        assert dns._do_client is None

    def test_init_allows_none_token(self):
        """Test that token can be None."""
        dns = DigitalOceanDNSManager()

        assert dns.digitalocean_token is None
        assert dns._do_client is None


class TestFromEnv:
    """Test from_env classmethod."""

    @patch("wordops_provisioner.digitalocean.os.getenv")
    @patch("wordops_provisioner.digitalocean.load_dotenv")
    def test_from_env_with_token(self, mock_load_dotenv, mock_getenv):
        """Test from_env with DIGITALOCEAN_TOKEN set."""
        mock_getenv.return_value = "test_token"

        dns = DigitalOceanDNSManager.from_env()

        mock_load_dotenv.assert_called_once()
        mock_getenv.assert_called_once_with("DIGITALOCEAN_TOKEN")
        assert dns.digitalocean_token == "test_token"


class TestGetDoClient:
    """Test _get_do_client method."""

    def test_get_client_missing_token(self):
        """Test that missing token raises ValueError."""
        dns = DigitalOceanDNSManager()

        with pytest.raises(ValueError, match="DigitalOcean token is not configured"):
            dns._get_do_client()

    @patch("wordops_provisioner.digitalocean.Client")
    def test_get_client_creates_client(self, mock_client_class):
        """Test that client is created with token."""
        mock_client_instance = Mock()
        mock_client_class.return_value = mock_client_instance

        dns = DigitalOceanDNSManager(digitalocean_token="test_token")
        client = dns._get_do_client()

        mock_client_class.assert_called_once_with(token="test_token")
        assert client == mock_client_instance
        assert dns._do_client == mock_client_instance

    @patch("wordops_provisioner.digitalocean.Client")
    def test_get_client_reuses_existing(self, mock_client_class):
        """Test that client is reused if already created."""
        mock_client_instance = Mock()
        mock_client_class.return_value = mock_client_instance

        dns = DigitalOceanDNSManager(digitalocean_token="test_token")
        client1 = dns._get_do_client()
        client2 = dns._get_do_client()

        mock_client_class.assert_called_once()
        assert client1 == client2


class TestCreateDnsZoneIfMissing:
    """Test create_dns_zone_if_missing method."""

    @patch("wordops_provisioner.digitalocean.Client")
    def test_create_zone_when_missing(self, mock_client_class):
        """Test creating zone when it doesn't exist."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.domains.get.return_value = {"id": "not_found"}
        mock_client.domains.create.return_value = {"domain": {"name": "example.com"}}

        dns = DigitalOceanDNSManager(digitalocean_token="test_token")
        dns.create_dns_zone_if_missing("example.com")

        mock_client.domains.get.assert_called_once_with(domain_name="example.com")
        mock_client.domains.create.assert_called_once_with(body={"name": "example.com"})

    @patch("wordops_provisioner.digitalocean.Client")
    def test_skip_create_when_exists(self, mock_client_class):
        """Test skipping creation when zone exists."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.domains.get.return_value = {"domain": {"name": "example.com"}}

        dns = DigitalOceanDNSManager(digitalocean_token="test_token")
        dns.create_dns_zone_if_missing("example.com")

        mock_client.domains.get.assert_called_once_with(domain_name="example.com")
        mock_client.domains.create.assert_not_called()


class TestEnsureARecord:
    """Test ensure_a_record method."""

    @patch("wordops_provisioner.digitalocean.Client")
    def test_create_record_when_missing(self, mock_client_class):
        """Test creating A record when it doesn't exist."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.domains.list_records.return_value = {"domain_records": []}

        dns = DigitalOceanDNSManager(digitalocean_token="test_token")
        dns.ensure_a_record("example.com", "@", "192.0.2.1")

        mock_client.domains.create_record.assert_called_once_with(
            domain_name="example.com",
            body={"type": "A", "name": "@", "data": "192.0.2.1"},
        )

    @patch("wordops_provisioner.digitalocean.Client")
    def test_skip_when_record_matches(self, mock_client_class):
        """Test skipping when A record already has correct IP."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.domains.list_records.return_value = {
            "domain_records": [
                {"type": "A", "name": "@", "data": "192.0.2.1", "id": 123}
            ]
        }

        dns = DigitalOceanDNSManager(digitalocean_token="test_token")
        dns.ensure_a_record("example.com", "@", "192.0.2.1")

        mock_client.domains.create_record.assert_not_called()
        mock_client.domains.update_record.assert_not_called()

    @patch("wordops_provisioner.digitalocean.Client")
    def test_update_when_ip_differs(self, mock_client_class):
        """Test updating A record when IP differs."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.domains.list_records.return_value = {
            "domain_records": [
                {"type": "A", "name": "@", "data": "192.0.2.99", "id": 123}
            ]
        }

        dns = DigitalOceanDNSManager(digitalocean_token="test_token")
        dns.ensure_a_record("example.com", "@", "192.0.2.1")

        mock_client.domains.update_record.assert_called_once_with(
            domain_name="example.com",
            domain_record_id=123,
            body={"data": "192.0.2.1"},
        )


class TestEnsureCnameRecord:
    """Test ensure_cname_record method."""

    @patch("wordops_provisioner.digitalocean.Client")
    def test_create_record_when_missing(self, mock_client_class):
        """Test creating CNAME record when it doesn't exist."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.domains.list_records.return_value = {"domain_records": []}

        dns = DigitalOceanDNSManager(digitalocean_token="test_token")
        dns.ensure_cname_record("example.com", "www", "@")

        mock_client.domains.create_record.assert_called_once_with(
            domain_name="example.com",
            body={"type": "CNAME", "name": "www", "data": "@"},
        )

    @patch("wordops_provisioner.digitalocean.Client")
    def test_skip_when_record_matches(self, mock_client_class):
        """Test skipping when CNAME record already has correct target."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.domains.list_records.return_value = {
            "domain_records": [{"type": "CNAME", "name": "www", "data": "@", "id": 456}]
        }

        dns = DigitalOceanDNSManager(digitalocean_token="test_token")
        dns.ensure_cname_record("example.com", "www", "@")

        mock_client.domains.create_record.assert_not_called()
        mock_client.domains.update_record.assert_not_called()

    @patch("wordops_provisioner.digitalocean.Client")
    def test_update_when_target_differs(self, mock_client_class):
        """Test updating CNAME record when target differs."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.domains.list_records.return_value = {
            "domain_records": [
                {"type": "CNAME", "name": "www", "data": "old.example.com", "id": 456}
            ]
        }

        dns = DigitalOceanDNSManager(digitalocean_token="test_token")
        dns.ensure_cname_record("example.com", "www", "@")

        mock_client.domains.update_record.assert_called_once_with(
            domain_name="example.com",
            domain_record_id=456,
            body={"data": "@"},
        )


class TestEnsureBasicDnsDigitalocean:
    """Test ensure_basic_dns_digitalocean method."""

    @patch("wordops_provisioner.digitalocean.Client")
    def test_calls_all_helper_methods(self, mock_client_class):
        """Test that main method calls all helper methods."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.domains.get.return_value = {"id": "not_found"}
        mock_client.domains.create.return_value = {"domain": {"name": "example.com"}}
        mock_client.domains.list_records.return_value = {"domain_records": []}

        dns = DigitalOceanDNSManager(digitalocean_token="test_token")
        dns.ensure_basic_dns_digitalocean("example.com", "192.0.2.1")

        # Verify zone creation
        mock_client.domains.get.assert_called_with(domain_name="example.com")
        mock_client.domains.create.assert_called_once()

        # Verify A record creation
        assert any(
            call[1]["body"]["type"] == "A"
            for call in mock_client.domains.create_record.call_args_list
        )

        # Verify CNAME record creation
        assert any(
            call[1]["body"]["type"] == "CNAME"
            for call in mock_client.domains.create_record.call_args_list
        )
