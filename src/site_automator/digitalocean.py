"""DigitalOcean DNS Manager"""

import logging
import os

from dotenv import load_dotenv
from pydo import Client

logger = logging.getLogger(__name__)


class DigitalOceanDNSManager:
    """Manage DigitalOcean DNS records."""

    digitalocean_token: str | None
    _do_client: Client | None

    def __init__(self, digitalocean_token: str | None = None) -> None:
        """Initialize DigitalOcean DNS Manager.

        Args:
            digitalocean_token: DigitalOcean API token
        """
        self.digitalocean_token = digitalocean_token
        self._do_client = None

    @classmethod
    def from_env(cls) -> "DigitalOceanDNSManager":
        """Create DigitalOcean DNS Manager from .env file.

        Expects environment variables:
            - DIGITALOCEAN_TOKEN: DigitalOcean API token

        Returns:
            DigitalOceanDNSManager instance
        """
        load_dotenv()

        return cls(digitalocean_token=os.getenv("DIGITALOCEAN_TOKEN"))

    def _get_do_client(self) -> Client:
        """Get or create DigitalOcean client.

        Returns:
            DigitalOcean pydo Client instance

        Raises:
            ValueError: If DigitalOcean token is not configured
        """
        if not self.digitalocean_token:
            raise ValueError("DigitalOcean token is not configured")

        if not self._do_client:
            self._do_client = Client(token=self.digitalocean_token)

        return self._do_client

    def create_dns_zone_if_missing(self, domain: str) -> None:
        """Create DNS zone on DigitalOcean if it doesn't exist.

        This method is idempotent - if the zone already exists, it does nothing.

        Args:
            domain: Domain name (e.g., "example.com")

        Raises:
            ValueError: If DigitalOcean token is not configured
            Exception: If API request fails
        """
        client = self._get_do_client()

        # Check if domain already exists
        # NOTE: pydo returns {"id": "not_found"} instead of raising when domain is missing
        # This check is a workaround for upstream limitations
        resp = client.domains.get(domain_name=domain)
        if isinstance(resp, dict) and resp.get("id") != "not_found":
            logger.info("DNS zone %s already exists on DigitalOcean", domain)
            return

        # Create the domain
        client.domains.create(body={"name": domain})
        logger.info("Created DNS zone %s on DigitalOcean", domain)

    def ensure_a_record(self, domain: str, name: str, ip: str) -> None:
        """Ensure A record exists with correct IP on DigitalOcean.

        This method is idempotent:
        - If record exists with correct IP: does nothing
        - If record exists with wrong IP: updates it
        - If record doesn't exist: creates it

        Args:
            domain: Domain name (e.g., "example.com")
            name: Record name (e.g., "@" for root, "www" for subdomain)
            ip: IP address to point to

        Raises:
            ValueError: If DigitalOcean token is not configured
            Exception: If API request fails
        """
        client = self._get_do_client()

        # Get all domain records
        resp = client.domains.list_records(domain_name=domain)
        records = resp.get("domain_records", [])

        # Find existing A record with this name
        existing_record = None
        for record in records:
            if record.get("type") == "A" and record.get("name") == name:
                existing_record = record
                break

        if existing_record:
            # Record exists - check if IP matches
            if existing_record.get("data") == ip:
                logger.info("A record %s for %s already points to %s", name, domain, ip)
                return

            # Update existing record
            client.domains.update_record(
                domain_name=domain,
                domain_record_id=existing_record["id"],
                body={"data": ip},
            )
            logger.info("Updated A record %s for %s to %s", name, domain, ip)
        else:
            # Create new record
            client.domains.create_record(
                domain_name=domain,
                body={"type": "A", "name": name, "data": ip},
            )
            logger.info("Created A record %s for %s pointing to %s", name, domain, ip)

    def ensure_cname_record(self, domain: str, name: str, target: str) -> None:
        """Ensure CNAME record exists with correct target on DigitalOcean.

        This method is idempotent:
        - If record exists with correct target: does nothing
        - If record exists with wrong target: updates it
        - If record doesn't exist: creates it

        Args:
            domain: Domain name (e.g., "example.com")
            name: Record name (e.g., "www")
            target: Target to point to (e.g., "@" for root domain)

        Raises:
            ValueError: If DigitalOcean token is not configured
            Exception: If API request fails
        """
        client = self._get_do_client()

        # Get all domain records
        resp = client.domains.list_records(domain_name=domain)
        records = resp.get("domain_records", [])

        # Find existing CNAME record with this name
        existing_record = None
        for record in records:
            if record.get("type") == "CNAME" and record.get("name") == name:
                existing_record = record
                break

        # Normalize target (add trailing dot if pointing to @)
        normalized_target = target if target != "@" else "@"

        if existing_record:
            # Record exists - check if target matches
            existing_data = existing_record.get("data", "").rstrip(".")
            if existing_data == normalized_target or existing_data == "@":
                logger.info(
                    "CNAME record %s for %s already points to %s",
                    name,
                    domain,
                    target,
                )
                return

            # Update existing record
            client.domains.update_record(
                domain_name=domain,
                domain_record_id=existing_record["id"],
                body={"data": normalized_target},
            )
            logger.info("Updated CNAME record %s for %s to %s", name, domain, target)
        else:
            # Create new record
            client.domains.create_record(
                domain_name=domain,
                body={"type": "CNAME", "name": name, "data": normalized_target},
            )
            logger.info(
                "Created CNAME record %s for %s pointing to %s", name, domain, target
            )

    def ensure_basic_dns_digitalocean(self, domain: str, server_ip: str) -> None:
        """Ensure basic DNS configuration on DigitalOcean.

        Creates/updates:
        - DNS zone for the domain
        - A record for @ (root) pointing to server_ip
        - CNAME record for www pointing to @ (root)

        This method is idempotent and can be run multiple times safely.

        Args:
            domain: Domain name (e.g., "example.com")
            server_ip: IP address of the server

        Raises:
            ValueError: If DigitalOcean token is not configured
            Exception: If API request fails
        """
        self.create_dns_zone_if_missing(domain)
        self.ensure_a_record(domain, "@", server_ip)
        self.ensure_cname_record(domain, "www", "@")
