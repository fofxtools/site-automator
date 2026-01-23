# Site Automator

Automate WordPress site provisioning, DNS configuration, and deployment. Uses WordOps.

## Features

- **Server Provisioning** - Set up WordPress servers with WordOps via SSH
- **DNS Management** - Configure nameservers (Namecheap/GoDaddy) and DNS records (DigitalOcean)
- **WordPress Deployment** - Deploy and configure WordPress sites with WP-CLI
- **Pageview Tracking** - Optional database-backed pageview tracking system

## Prerequisites

- [WordOps](https://docs.wordops.net/getting-started/installation-guide/) must be installed on your server. Includes WP-CLI.

## Installation

```bash
git clone https://github.com/yourusername/site-automator.git
cd site-automator
pip install -e .
```

## Quick Start

```python
from site_automator import (
    WordOpsProvisioner,
    RegistrarNameserverManager,
    DigitalOceanDNSManager,
    WordPressDeployer,
)

# Create site (use --wpfc for Nginx fastcgi_cache)
wordops = WordOpsProvisioner.from_env()
wordops.create_site("example.com", flags=["--wp"])

# Configure DNS
registrar = RegistrarNameserverManager.from_env()
registrar.update_nameservers_namecheap("example.com")

dns = DigitalOceanDNSManager.from_env()
dns.ensure_basic_dns_digitalocean("example.com", "203.0.113.10")

# Deploy WordPress
wordpress = WordPressDeployer(wordops)
wordpress.configure_site(
    domain="example.com",
    title="My Site",
    admin_user="admin",
    admin_email="admin@example.com",
)

wordops.close()
```

## Configuration

Create a `.env` file with your credentials:

```bash
# SSH
SERVER_HOST=203.0.113.10
SSH_USER=root
SSH_PASSWORD=your_password

# DNS
DIGITALOCEAN_TOKEN=your_token
NAMECHEAP_USERNAME=your_username
NAMECHEAP_TOKEN=your_token
```

## Documentation

- [WordOps Provisioning](docs/wordops.md) - Set up server with WordOps
- [DNS Setup](docs/dns.md) - Point domain to server
- [WordPress Deployment](docs/wordpress.md) - Deploy and configure WordPress
- [Pageview Tracking](docs/tracking.md) - Optional tracking setup

## License

MIT
