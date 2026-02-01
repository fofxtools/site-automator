# WordOps Provisioner

Connect to your server via SSH and run WordOps commands.

## What it does

`WordOpsProvisioner` establishes an SSH connection to your server and lets you:
- Create WordPress sites with WordOps
- Run shell commands remotely
- Enable SSL certificates
- Set up swap space

## Prerequisites

WordOps must be installed on your server. See the [WordOps installation guide](https://docs.wordops.net/getting-started/installation-guide/).

## Setup

Add your server credentials to `.env`:

```bash
SERVER_HOST=123.45.67.89
SSH_USER=root
SSH_PASSWORD=your_password
```

## Basic Usage

```python
from site_automator.wordops import WordOpsProvisioner

# Connect using .env credentials
wordops = WordOpsProvisioner.from_env()

# Or connect directly
wordops = WordOpsProvisioner(host="123.45.67.89", password="your_password")

# Close when done
wordops.close()
```

## Creating Sites

```python
# Create HTML site
wordops.create_site("example.com", flags=["--html"])

# Create basic WordPress site
wordops.create_site("example.com", flags=["--wp"])

# Create with specific PHP version
wordops.create_site("example.com", flags=["--wp", "--php82"])

# Create with cache (Redis)
wordops.create_site("example.com", flags=["--wp", "--redis"])
```

Common flags:
- `--wp` - Install WordPress
- `--php81`, `--php82` - PHP version
- `--redis` - Redis cache
- `--letsencrypt` - SSL certificate

For more flags see [WordOps dcoumentation](https://docs.wordops.net/commands/site/).

## SSL Certificates

```python
# Enable SSL (uses Let's Encrypt)
wordops.ensure_ssl("example.com")
```

## Running Commands

```python
# Run any shell command
output, exit_code = wordops.run_command("ls -la /var/www")

# Don't raise on failure with check=False (check exit code instead)
output, exit_code = wordops.run_command("test -f /some/file", check=False)
if exit_code == 0:
    print("File exists")
```

## Swap Space

```python
# Create 4GB swap (default is 2GB)
wordops.ensure_swap(size_gb=4)
```

## Default Catch-all

Creates a default catch-all Nginx server block that returns 444 for any domain not explicitly configured.

This avoids a domain pointed to the server, but not set up as a site. From being served by the first available site by Nginx.

```python
# Create default catch-all
wordops.ensure_default_catchall()
```

## Complete Example

```python
from site_automator.wordops import WordOpsProvisioner

wordops = WordOpsProvisioner.from_env()

try:
    # Set up swap for small VPS
    wordops.ensure_swap(size_gb=2)

    # Create WordPress site with Nginx fastcgi_cache
    wordops.create_site("example.com", flags=["--wpfc"])

    # Enable SSL
    wordops.ensure_ssl("example.com")

    # Restart nginx
    wordops.restart_nginx()

    # Create default catch-all
    wordops.ensure_default_catchall()

finally:
    wordops.close()
```