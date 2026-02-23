"""Registrar Nameserver Manager"""

import logging
import os

import requests
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class RegistrarNameserverManager:
    """Manage nameservers and DNS records across registrars.

    Supports:
    - Nameserver updates: Namecheap, GoDaddy, Porkbun
    - DNS record management: Porkbun (A, CNAME)
    """

    namecheap_username: str | None
    namecheap_token: str | None
    godaddy_api_key: str | None
    godaddy_api_secret: str | None
    porkbun_api_key: str | None
    porkbun_secret_key: str | None

    def __init__(
        self,
        namecheap_username: str | None = None,
        namecheap_token: str | None = None,
        godaddy_api_key: str | None = None,
        godaddy_api_secret: str | None = None,
        porkbun_api_key: str | None = None,
        porkbun_secret_key: str | None = None,
    ) -> None:
        """Initialize Registrar Nameserver Manager.

        Args:
            namecheap_username: Namecheap API username
            namecheap_token: Namecheap API token
            godaddy_api_key: GoDaddy API key
            godaddy_api_secret: GoDaddy API secret
            porkbun_api_key: Porkbun API key
            porkbun_secret_key: Porkbun secret API key
        """
        self.namecheap_username = namecheap_username
        self.namecheap_token = namecheap_token
        self.godaddy_api_key = godaddy_api_key
        self.godaddy_api_secret = godaddy_api_secret
        self.porkbun_api_key = porkbun_api_key
        self.porkbun_secret_key = porkbun_secret_key

    @classmethod
    def from_env(cls) -> "RegistrarNameserverManager":
        """Create Registrar Nameserver Manager from .env file.

        Expects environment variables:
            - NAMECHEAP_USERNAME: Namecheap API username
            - NAMECHEAP_TOKEN: Namecheap API token
            - GODADDY_API_KEY: GoDaddy API key
            - GODADDY_API_SECRET: GoDaddy API secret
            - PORKBUN_API_KEY: Porkbun API key
            - PORKBUN_SECRET_KEY: Porkbun secret API key

        Returns:
            RegistrarNameserverManager instance
        """
        load_dotenv()

        return cls(
            namecheap_username=os.getenv("NAMECHEAP_USERNAME"),
            namecheap_token=os.getenv("NAMECHEAP_TOKEN"),
            godaddy_api_key=os.getenv("GODADDY_API_KEY"),
            godaddy_api_secret=os.getenv("GODADDY_API_SECRET"),
            porkbun_api_key=os.getenv("PORKBUN_API_KEY"),
            porkbun_secret_key=os.getenv("PORKBUN_SECRET_KEY"),
        )

    def update_nameservers_namecheap(
        self,
        domain: str,
        nameservers: list[str] | None = None,
        sandbox: bool = False,
        client_ip: str = "127.0.0.1",
    ) -> None:
        """Update nameservers on Namecheap for a domain.

        Note:
        - The public IP of the machine running this script must be whitelisted
          in Namecheap API settings.
        - Using client_ip="127.0.0.1" commonly works when running locally and
          your public IP is whitelisted, as Namecheap validates the request source.

        Args:
            domain: Domain name (e.g. "example.com")
            nameservers: List of nameservers (defaults to DigitalOcean)
            sandbox: Use Namecheap sandbox API
            client_ip: ClientIp parameter (default: 127.0.0.1)

        Raises:
            ValueError: If Namecheap credentials are not configured or domain format is invalid
            requests.RequestException: If API request fails
            RuntimeError: If Namecheap API returns an error status
        """
        if not self.namecheap_username or not self.namecheap_token:
            raise ValueError("Namecheap credentials are not configured")

        nameservers = nameservers or [
            "ns1.digitalocean.com",
            "ns2.digitalocean.com",
            "ns3.digitalocean.com",
        ]

        try:
            sld, tld = domain.split(".", 1)
        except ValueError as e:
            raise ValueError(f"Invalid domain format: {domain}") from e

        base_url = (
            "https://api.sandbox.namecheap.com/xml.response"
            if sandbox
            else "https://api.namecheap.com/xml.response"
        )

        params = {
            "ApiUser": self.namecheap_username,
            "ApiKey": self.namecheap_token,
            "UserName": self.namecheap_username,
            "Command": "namecheap.domains.dns.setCustom",
            "ClientIp": client_ip,
            "SLD": sld,
            "TLD": tld,
            "Nameservers": ",".join(nameservers),
        }

        response = requests.get(base_url, params=params, timeout=30)
        try:
            response.raise_for_status()
        except requests.HTTPError:
            logger.error(
                "Namecheap updateNs error %s: %s", response.status_code, response.text
            )
            raise

        # Check for API errors in XML response
        if 'Status="ERROR"' in response.text:
            raise RuntimeError(
                f"Namecheap API error updating {domain}: {response.text}"
            )

        logger.info(
            "Successfully updated nameservers for %s on Namecheap",
            domain,
        )

    def update_nameservers_godaddy(
        self,
        domain: str,
        nameservers: list[str] | None = None,
    ) -> None:
        """Update nameservers on GoDaddy for a domain.

        Args:
            domain: Domain name to update (e.g., "example.com")
            nameservers: List of nameservers. Defaults to DigitalOcean's nameservers.

        Raises:
            ValueError: If GoDaddy credentials are not configured
            requests.RequestException: If API request fails
            RuntimeError: If GoDaddy API returns unexpected status code
        """
        if not self.godaddy_api_key or not self.godaddy_api_secret:
            raise ValueError("GoDaddy credentials are not configured")

        nameservers = nameservers or [
            "ns1.digitalocean.com",
            "ns2.digitalocean.com",
            "ns3.digitalocean.com",
        ]

        url = f"https://api.godaddy.com/v1/domains/{domain}"
        headers = {
            "Authorization": f"sso-key {self.godaddy_api_key}:{self.godaddy_api_secret}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        data = {"nameServers": nameservers}

        response = requests.patch(url, headers=headers, json=data, timeout=30)
        try:
            response.raise_for_status()
        except requests.HTTPError:
            logger.error(
                "GoDaddy updateNs error %s: %s", response.status_code, response.text
            )
            raise

        if response.status_code not in (200, 204):
            raise RuntimeError(
                f"GoDaddy API returned unexpected status {response.status_code} "
                f"for domain {domain}: {response.text}"
            )

        logger.info("Successfully updated nameservers for %s on GoDaddy", domain)

    def update_nameservers_porkbun(
        self,
        domain: str,
        nameservers: list[str] | None = None,
    ) -> None:
        """Update nameservers on Porkbun for a domain.

        Args:
            domain: Domain name to update (e.g., "example.com")
            nameservers: List of nameservers. Defaults to DigitalOcean's nameservers.

        Raises:
            ValueError: If Porkbun credentials are not configured
            requests.RequestException: If API request fails
            RuntimeError: If Porkbun API returns error status
        """
        if not self.porkbun_api_key or not self.porkbun_secret_key:
            raise ValueError("Porkbun credentials are not configured")

        nameservers = nameservers or [
            "ns1.digitalocean.com",
            "ns2.digitalocean.com",
            "ns3.digitalocean.com",
        ]

        url = f"https://api.porkbun.com/api/json/v3/domain/updateNs/{domain}"
        payload = {
            "secretapikey": self.porkbun_secret_key,
            "apikey": self.porkbun_api_key,
            "ns": nameservers,
        }

        response = requests.post(url, json=payload, timeout=30)
        try:
            response.raise_for_status()
        except requests.HTTPError:
            logger.error(
                "Porkbun updateNs error %s: %s", response.status_code, response.text
            )
            raise

        data = response.json()
        if data.get("status") != "SUCCESS":
            raise RuntimeError(
                f"Porkbun API error updating {domain}: {data.get('message', response.text)}"
            )

        logger.info("Successfully updated nameservers for %s on Porkbun", domain)

    def set_porkbun_dns_a_record(
        self,
        domain: str,
        ip: str,
        subdomain: str = "",
        ttl: int = 600,
    ) -> None:
        """Set A record using Porkbun DNS.

        Args:
            domain: Domain name (e.g., "example.com")
            ip: IP address to point to (e.g., "143.198.123.45")
            subdomain: Subdomain (empty string for apex/root domain)
            ttl: Time to live in seconds (default: 600)

        Raises:
            ValueError: If Porkbun credentials are not configured
            requests.RequestException: If API request fails
            RuntimeError: If Porkbun API returns error status
        """
        if not self.porkbun_api_key or not self.porkbun_secret_key:
            raise ValueError("Porkbun credentials are not configured")

        # Porkbun expects '@' for apex/root records, not empty string
        record_host = subdomain if subdomain else "@"

        url = f"https://api.porkbun.com/api/json/v3/dns/editByNameType/{domain}/A/{record_host}"
        payload = {
            "secretapikey": self.porkbun_secret_key,
            "apikey": self.porkbun_api_key,
            "content": ip,
            "ttl": str(ttl),
        }

        response = requests.post(url, json=payload, timeout=30)
        try:
            response.raise_for_status()
        except requests.HTTPError:
            logger.error(
                "Porkbun DNS A record error %s: %s", response.status_code, response.text
            )
            raise

        data = response.json()
        if data.get("status") != "SUCCESS":
            raise RuntimeError(
                f"Porkbun API error setting A record for {domain}: {data.get('message', response.text)}"
            )

        record_name = domain if record_host == "@" else f"{record_host}.{domain}"
        logger.info("Successfully set A record for %s → %s", record_name, ip)

    def set_porkbun_dns_cname(
        self,
        domain: str,
        target: str,
        subdomain: str = "www",
        ttl: int = 600,
    ) -> None:
        """Set CNAME record using Porkbun DNS.

        Args:
            domain: Domain name (e.g., "example.com")
            target: Target domain to point to (e.g., "example.com")
            subdomain: Subdomain (default: "www")
            ttl: Time to live in seconds (default: 600)

        Raises:
            ValueError: If Porkbun credentials are not configured
            requests.RequestException: If API request fails
            RuntimeError: If Porkbun API returns error status
        """
        if not self.porkbun_api_key or not self.porkbun_secret_key:
            raise ValueError("Porkbun credentials are not configured")

        # Porkbun expects subdomain name (e.g., "www"), not "@" for CNAME
        url = f"https://api.porkbun.com/api/json/v3/dns/editByNameType/{domain}/CNAME/{subdomain}"
        payload = {
            "secretapikey": self.porkbun_secret_key,
            "apikey": self.porkbun_api_key,
            "content": target,
            "ttl": str(ttl),
        }

        response = requests.post(url, json=payload, timeout=30)
        try:
            response.raise_for_status()
        except requests.HTTPError:
            logger.error(
                "Porkbun DNS CNAME record error %s: %s",
                response.status_code,
                response.text,
            )
            raise

        data = response.json()
        if data.get("status") != "SUCCESS":
            raise RuntimeError(
                f"Porkbun API error setting CNAME record for {domain}: {data.get('message', response.text)}"
            )

        record_name = f"{subdomain}.{domain}"
        logger.info("Successfully set CNAME record for %s → %s", record_name, target)
