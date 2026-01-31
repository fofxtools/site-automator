from unittest.mock import patch, Mock

import pytest

from site_automator.seo import create_indexnow_key, submit_indexnow


class TestCreateIndexnowKey:
    """Test create_indexnow_key function."""

    def test_generates_key_and_writes_file(self, wordops, mock_ssh_client):
        """Test key is generated and written to the webroot."""
        key = create_indexnow_key("example.com", wordops)

        assert len(key) == 32
        assert key.isalnum()

        cmd = mock_ssh_client.exec_command.call_args[0][0]
        assert f"{key}.txt" in cmd
        assert "/var/www/example.com/htdocs/" in cmd


class TestSubmitIndexnow:
    """Test submit_indexnow function."""

    @patch("site_automator.seo.requests.get")
    def test_submit_direct(self, mock_get):
        """Test direct submission to Bing."""
        mock_get.return_value = Mock(status_code=200)

        submit_indexnow("https://example.com/page", "abc123")

        called_url = mock_get.call_args[0][0]
        assert "bing.com/indexnow" in called_url
        assert "url=https%3A%2F%2Fexample.com%2Fpage" in called_url
        assert "key=abc123" in called_url

    @patch.dict("os.environ", {"SCRAPERAPI_KEY": "scraper_key_123"})
    @patch("site_automator.seo.requests.get")
    def test_submit_via_scraperapi(self, mock_get):
        """Test submission routed through ScraperAPI."""
        mock_get.return_value = Mock(status_code=200)

        submit_indexnow("https://example.com/page", "abc123", use_scraperapi=True)

        called_url = mock_get.call_args[0][0]
        assert called_url.startswith("https://api.scraperapi.com")
        assert "api_key=scraper_key_123" in called_url
        # Inner URL should be percent-encoded
        assert "bing.com%2Findexnow" in called_url

    @patch.dict("os.environ", {}, clear=True)
    def test_submit_scraperapi_missing_key_raises(self):
        """Test ValueError when SCRAPERAPI_KEY is not set."""
        with pytest.raises(ValueError, match="SCRAPERAPI_KEY"):
            submit_indexnow("https://example.com/page", "abc123", use_scraperapi=True)

    @patch("site_automator.seo.requests.get")
    def test_submit_raises_on_http_error(self, mock_get):
        """Test HTTPError is raised on non-2xx response."""
        mock_get.return_value = Mock(status_code=422)
        mock_get.return_value.raise_for_status.side_effect = Exception("422 error")

        with pytest.raises(Exception, match="422"):
            submit_indexnow("https://example.com/page", "abc123")
