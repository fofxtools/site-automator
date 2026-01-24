# DNS Setup

Point your domain to a server using registrar nameserver updates and DigitalOcean DNS.

## What it does

- **Registrar Nameservers** - Updates nameservers at your registrar (Namecheap or GoDaddy) to use DigitalOcean DNS
- **DNS Records** - Creates DNS zone and records at DigitalOcean

## Setup

Add credentials to `.env`:

```bash
# DigitalOcean
DIGITALOCEAN_TOKEN=your_token_here

# Namecheap (optional - only if using Namecheap)
NAMECHEAP_USERNAME=your_username
NAMECHEAP_TOKEN=your_api_token

# GoDaddy (optional - only if using GoDaddy)
GODADDY_API_KEY=your_key
GODADDY_API_SECRET=your_secret
```

## Basic Usage

```python
from site_automator.registrars import RegistrarNameserverManager
from site_automator.digitalocean import DigitalOceanDNSManager

domain = "example.com"
server_ip = "203.0.113.10"

# Step 1: Point nameservers to DigitalOcean
registrars = RegistrarNameserverManager.from_env()
registrars.update_nameservers_namecheap(domain)  # or update_nameservers_godaddy()

# Step 2: Configure DNS at DigitalOcean (root + www)
dns = DigitalOceanDNSManager.from_env()
dns.ensure_basic_dns_digitalocean(domain, server_ip)

print(f"DNS configured for {domain}")
```

## Individual DNS Methods

For more control, use individual methods:

```python
dns = DigitalOceanDNSManager.from_env()

# Create DNS zone
dns.create_dns_zone_if_missing("example.com")

# Add A records
dns.ensure_a_record("example.com", "@", "203.0.113.10")
dns.ensure_a_record("example.com", "www", "203.0.113.10")

# Add CNAME record
dns.ensure_cname_record("example.com", "blog", "example.com")
```

## Notes

- **Nameserver propagation** takes 24-48 hours (usually faster)
- **DNS changes** at DigitalOcean propagate in minutes
- **Namecheap API** requires your IP to be whitelisted in API settings
