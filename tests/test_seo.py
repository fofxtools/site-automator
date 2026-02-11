from unittest.mock import patch, Mock

import pytest

from site_automator.seo import create_indexnow_key, submit_indexnow


class TestCreateIndexnowKey:
    """Test create_indexnow_key function."""

    def test_generates_key_and_writes_file(self, mock_ssh_connection):
        """Test key is generated and written to the webroot."""
        key = create_indexnow_key("example.com", mock_ssh_connection)

        assert len(key) == 32
        assert key.isalnum()

        cmd = mock_ssh_connection.run_command.call_args[0][0]
        assert f"{key}.txt" in cmd
        assert "/var/www/example.com/htdocs/" in cmd

    def test_generates_key_with_custom_webroot(self, mock_ssh_connection):
        """Test key is generated with custom webroot."""
        key = create_indexnow_key("example.com", mock_ssh_connection, webroot="public")

        assert len(key) == 32
        assert key.isalnum()

        cmd = mock_ssh_connection.run_command.call_args[0][0]
        assert f"{key}.txt" in cmd
        assert "/var/www/example.com/public/" in cmd


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

    @patch.dict("os.environ", {"ZYTE_API_KEY": "zyte_key_123"})
    @patch("site_automator.seo.requests.post")
    def test_submit_via_zyte(self, mock_post):
        """Test submission routed through Zyte API."""
        # Mock Zyte API response with base64-encoded empty body
        mock_post.return_value = Mock(
            status_code=200,
            json=lambda: {"httpResponseBody": ""},  # Empty base64 string
        )

        submit_indexnow("https://example.com/page", "abc123", use_zyte=True)

        # Verify POST request to Zyte API
        assert mock_post.call_args[0][0] == "https://api.zyte.com/v1/extract"

        # Verify authentication (API key as username, empty password)
        assert mock_post.call_args[1]["auth"] == ("zyte_key_123", "")

        # Verify JSON body contains the IndexNow URL
        json_body = mock_post.call_args[1]["json"]
        assert "bing.com/indexnow" in json_body["url"]
        assert "url=https%3A%2F%2Fexample.com%2Fpage" in json_body["url"]
        assert "key=abc123" in json_body["url"]
        assert json_body["httpResponseBody"] is True

    @patch.dict("os.environ", {}, clear=True)
    def test_submit_zyte_missing_key_raises(self):
        """Test ValueError when ZYTE_API_KEY is not set."""
        with pytest.raises(ValueError, match="ZYTE_API_KEY"):
            submit_indexnow("https://example.com/page", "abc123", use_zyte=True)

    @patch("site_automator.seo.requests.get")
    def test_submit_raises_on_http_error(self, mock_get):
        """Test HTTPError is raised on non-2xx response."""
        mock_get.return_value = Mock(status_code=422)
        mock_get.return_value.raise_for_status.side_effect = Exception("422 error")

        with pytest.raises(Exception, match="422"):
            submit_indexnow("https://example.com/page", "abc123")

    @patch.dict("os.environ", {"ZYTE_API_KEY": "zyte_key_123"})
    @patch("site_automator.seo.requests.post")
    def test_submit_zyte_no_body(self, mock_post):
        mock_post.return_value = Mock(
            status_code=200, json=lambda: {}  # No httpResponseBody
        )

        submit_indexnow("https://example.com/page", "abc123", use_zyte=True)
