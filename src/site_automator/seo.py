"""SEO utilities."""

import logging
import os
import secrets
import shlex
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv

from site_automator.ssh import SSHConnection
from base64 import b64decode

logger = logging.getLogger(__name__)

load_dotenv()

INDEXNOW_URL = "https://www.bing.com/indexnow"


def create_indexnow_key(
    domain: str, ssh: SSHConnection, webroot: str = "htdocs"
) -> str:
    """Generate an IndexNow key and write the verification file to the site webroot.

    Generates a random 32-character hex key and writes it to
    /var/www/{domain}/{webroot}/{key}.txt. IndexNow requires this file
    to verify domain ownership.

    Args:
        domain: Domain name (e.g., "example.com")
        ssh: SSHConnection instance for remote file operations
        webroot: Web document root folder (default: "htdocs")
                 Common values: "htdocs" (Nginx), "public" (Caddy)

    Returns:
        The generated key string. Store this for use with submit_indexnow().

    Raises:
        RuntimeError: If writing the key file fails
    """
    key = secrets.token_hex(16)

    key_file = f"/var/www/{domain}/{webroot}/{key}.txt"
    key_escaped = shlex.quote(key)
    key_file_escaped = shlex.quote(key_file)

    logger.info(f"Creating IndexNow key file for {domain}")
    ssh.run_command(f"echo {key_escaped} > {key_file_escaped}", check=True)
    logger.info(f"IndexNow key file created: {key_file}")

    return key


def submit_indexnow(
    url: str,
    key: str,
    use_zyte: bool = False,
) -> None:
    """Submit a URL to IndexNow for indexing.

    Args:
        url: Full URL to submit (e.g., "https://example.com/page1")
        key: IndexNow key for this domain (from create_indexnow_key)
        use_zyte: If True, route request through Zyte API.
                  Requires ZYTE_API_KEY environment variable.

    Raises:
        ValueError: If use_zyte is True and ZYTE_API_KEY is not set
        requests.HTTPError: If the API returns an error
    """
    indexnow_url = f"{INDEXNOW_URL}?{urlencode({'url': url, 'key': key})}"

    if use_zyte:
        zyte_api_key = os.getenv("ZYTE_API_KEY")
        if not zyte_api_key:
            raise ValueError("ZYTE_API_KEY environment variable is required")

        logger.info(f"Submitting to IndexNow via Zyte API: {url}")

        # Zyte API expects a POST request with JSON body
        response = requests.post(
            "https://api.zyte.com/v1/extract",
            auth=(zyte_api_key, ""),
            json={
                "url": indexnow_url,
                "httpResponseBody": True,
            },
        )
        response.raise_for_status()

        # Decode and log response body (if present)
        data = response.json()
        body_b64 = data.get("httpResponseBody")
        if body_b64:
            try:
                decoded_bytes = b64decode(body_b64)
                decoded = decoded_bytes.decode("utf-8", errors="ignore")
                logger.debug(f"HTTP response body:\n{decoded}")
            except Exception as e:
                logger.warning(f"Failed to decode HTTP response body: {e}")
    else:
        logger.info(f"Submitting to IndexNow: {url}")
        response = requests.get(indexnow_url)
        response.raise_for_status()

    logger.info(f"IndexNow submission successful (HTTP {response.status_code})")
