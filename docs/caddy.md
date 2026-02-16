# Caddy Provisioner

Connect to your server via SSH and manage static sites with Caddy.

## What it does

`CaddyProvisioner` establishes an SSH connection to your server and lets you:
- Enable/disable domains with automatic HTTPS
- Manage site configurations
- Reload Caddy gracefully (zero-downtime)
- Run shell commands remotely

## Prerequisites

Caddy must be installed on your server. See the [Caddy installation guide](https://caddyserver.com/docs/install).

Commands to install Caddy on Ubuntu/Debian:

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl

curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg

curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list

chmod o+r /usr/share/keyrings/caddy-stable-archive-keyring.gpg
chmod o+r /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy
```

For PHP support (optional):

```bash
sudo apt install -y php8.3-fpm
```

## Setup

Configure SSH access using `~/.ssh/config`. Append:

```bash
# ~/.ssh/config
Host your-server-alias
  HostName 123.45.67.89
  User root
  IdentityFile ~/.ssh/id_ed25519
  IdentitiesOnly yes
  ServerAliveInterval 60
  ServerAliveCountMax 10
```

Add the server to your site configuration in `sites.csv`:

```csv
site_id,domain,server,...
mysite,example.com,your-server-alias,...
```

## Basic Usage

```python
from site_automator.caddy import CaddyProvisioner

# Connect using SSH config alias
caddy = CaddyProvisioner(host="your-server-alias")

# Or connect with IP/hostname (still uses SSH keys)
caddy = CaddyProvisioner(host="123.45.67.89")

# Close when done
caddy.close()
```

## Enabling Sites

```python
# Enable a domain (creates config and enables it)
caddy.enable_domain("example.com")
```

This automatically:
- Creates `/var/www/example.com/public` directory
- Generates site config at `/etc/caddy/sites-available/example.com.caddy`
- Creates symlink at `/etc/caddy/sites-enabled/example.com.caddy`
- Sets up JSON access logging (GoAccess compatible)
- Configures PHP 8.3 FPM support
- Enables gzip compression
- Validates and reloads Caddy

## Disabling Sites

```python
# Disable a domain (preserves config file)
caddy.disable_domain("example.com")
```

This removes the symlink from `sites-enabled/` but keeps the config in `sites-available/` for later re-enabling.

## Reloading Caddy

```python
# Graceful reload (zero-downtime)
caddy.reload_caddy()
```

This validates the config before reloading to prevent breaking the server.

## Running Commands

```python
# Run any shell command
output, exit_code = caddy.ssh.run_command("ls -la /var/www")

# Don't raise on failure with check=False (check exit code instead)
output, exit_code = caddy.ssh.run_command("test -f /some/file", check=False)
if exit_code == 0:
    print("File exists")
```

## Swap Space

```python
# Create 4GB swap (default is 2GB)
caddy.ssh.ensure_swap(size_gb=4)
```

## Complete Example

```python
from site_automator.caddy import CaddyProvisioner
from site_automator.utils import configure_logging

configure_logging()

caddy = CaddyProvisioner(host="your-server-alias")

try:
    # Set up swap for small VPS
    caddy.ssh.ensure_swap(size_gb=2)

    # Enable domain (automatic HTTPS via Let's Encrypt)
    caddy.enable_domain("example.com")

    # Configure git safe.directory
    caddy.ssh.ensure_git_safe_directory()

finally:
    caddy.close()
```