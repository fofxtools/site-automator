"""Unit tests for RegistrarNameserverManager - Critical path only."""

import pytest
import responses
from unittest.mock import patch

from site_automator import RegistrarNameserverManager


class TestInit:
    """Test __init__ method."""

    def test_init_stores_credentials(self):
        """Test that credentials are stored correctly."""
        dns = RegistrarNameserverManager(
            namecheap_username="ncuser",
            namecheap_token="nctoken",
            godaddy_api_key="gdkey",
            godaddy_api_secret="gdsecret",
        )

        assert dns.namecheap_username == "ncuser"
        assert dns.namecheap_token == "nctoken"
        assert dns.godaddy_api_key == "gdkey"
        assert dns.godaddy_api_secret == "gdsecret"

    def test_init_allows_none_credentials(self):
        """Test that credentials can be None."""
        dns = RegistrarNameserverManager()

        assert dns.namecheap_username is None
        assert dns.namecheap_token is None
        assert dns.godaddy_api_key is None
        assert dns.godaddy_api_secret is None


class TestFromEnv:
    """Test from_env classmethod."""

    @patch("site_automator.registrars.os.getenv")
    @patch("site_automator.registrars.load_dotenv")
    def test_from_env_with_all_vars(self, mock_load_dotenv, mock_getenv):
        """Test from_env with all environment variables set."""
        mock_getenv.side_effect = lambda key, default=None: {
            "NAMECHEAP_USERNAME": "ncuser",
            "NAMECHEAP_TOKEN": "nctoken",
            "GODADDY_API_KEY": "gdkey",
            "GODADDY_API_SECRET": "gdsecret",
        }.get(key, default)

        dns = RegistrarNameserverManager.from_env()

        mock_load_dotenv.assert_called_once()
        assert dns.namecheap_username == "ncuser"
        assert dns.namecheap_token == "nctoken"
        assert dns.godaddy_api_key == "gdkey"
        assert dns.godaddy_api_secret == "gdsecret"


class TestUpdateNameserversNamecheap:
    """Test update_nameservers_namecheap method."""

    @responses.activate
    def test_update_nameservers_success(self):
        """Test successful nameserver update on Namecheap."""
        responses.add(
            responses.GET,
            "https://api.namecheap.com/xml.response",
            body='<?xml version="1.0" encoding="utf-8"?><ApiResponse Status="OK"></ApiResponse>',
            status=200,
        )

        dns = RegistrarNameserverManager(
            namecheap_username="user", namecheap_token="token"
        )
        # Should not raise any exception
        dns.update_nameservers_namecheap("example.com")

        assert len(responses.calls) == 1
        request_url = responses.calls[0].request.url
        assert request_url is not None
        assert "namecheap.domains.dns.setCustom" in request_url

    @responses.activate
    def test_update_nameservers_with_custom_nameservers(self):
        """Test nameserver update with custom nameservers."""
        responses.add(
            responses.GET,
            "https://api.namecheap.com/xml.response",
            body='<?xml version="1.0" encoding="utf-8"?><ApiResponse Status="OK"></ApiResponse>',
            status=200,
        )

        dns = RegistrarNameserverManager(
            namecheap_username="user", namecheap_token="token"
        )
        custom_ns = ["ns1.custom.com", "ns2.custom.com"]
        # Should not raise any exception
        dns.update_nameservers_namecheap("example.com", nameservers=custom_ns)

        request_url = responses.calls[0].request.url
        assert request_url is not None
        assert "ns1.custom.com" in request_url
        assert "ns2.custom.com" in request_url

    @responses.activate
    def test_update_nameservers_api_error(self):
        """Test handling of Namecheap API error."""
        responses.add(
            responses.GET,
            "https://api.namecheap.com/xml.response",
            body='<?xml version="1.0" encoding="utf-8"?><ApiResponse Status="ERROR"><Errors><Error>Invalid domain</Error></Errors></ApiResponse>',
            status=200,
        )

        dns = RegistrarNameserverManager(
            namecheap_username="user", namecheap_token="token"
        )

        with pytest.raises(RuntimeError, match="Namecheap API error"):
            dns.update_nameservers_namecheap("example.com")

    def test_update_nameservers_missing_credentials(self):
        """Test that missing credentials raises ValueError."""
        dns = RegistrarNameserverManager()

        with pytest.raises(
            ValueError, match="Namecheap credentials are not configured"
        ):
            dns.update_nameservers_namecheap("example.com")

    def test_update_nameservers_invalid_domain(self):
        """Test handling of invalid domain format."""
        dns = RegistrarNameserverManager(
            namecheap_username="user", namecheap_token="token"
        )

        with pytest.raises(ValueError, match="Invalid domain format"):
            dns.update_nameservers_namecheap("invaliddomain")


class TestUpdateNameserversGodaddy:
    """Test update_nameservers_godaddy method."""

    @responses.activate
    def test_update_nameservers_success(self):
        """Test successful nameserver update on GoDaddy."""
        responses.add(
            responses.PATCH,
            "https://api.godaddy.com/v1/domains/example.com",
            status=200,
        )

        dns = RegistrarNameserverManager(
            godaddy_api_key="key", godaddy_api_secret="secret"
        )
        # Should not raise any exception
        dns.update_nameservers_godaddy("example.com")

        assert len(responses.calls) == 1

    @responses.activate
    def test_update_nameservers_with_custom_nameservers(self):
        """Test nameserver update with custom nameservers."""
        responses.add(
            responses.PATCH,
            "https://api.godaddy.com/v1/domains/example.com",
            status=204,
        )

        dns = RegistrarNameserverManager(
            godaddy_api_key="key", godaddy_api_secret="secret"
        )
        custom_ns = ["ns1.custom.com", "ns2.custom.com"]
        # Should not raise any exception
        dns.update_nameservers_godaddy("example.com", nameservers=custom_ns)

    def test_update_nameservers_missing_credentials(self):
        """Test that missing credentials raises ValueError."""
        dns = RegistrarNameserverManager()

        with pytest.raises(ValueError, match="GoDaddy credentials are not configured"):
            dns.update_nameservers_godaddy("example.com")

    @responses.activate
    def test_update_nameservers_unexpected_status(self):
        """Test handling of unexpected status code from GoDaddy."""
        responses.add(
            responses.PATCH,
            "https://api.godaddy.com/v1/domains/example.com",
            status=500,
            body="Internal Server Error",
        )

        dns = RegistrarNameserverManager(
            godaddy_api_key="key", godaddy_api_secret="secret"
        )

        with pytest.raises(Exception):  # requests.HTTPError from raise_for_status()
            dns.update_nameservers_godaddy("example.com")
