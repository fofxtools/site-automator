# Pageview Statistics Web Viewer (Caddy)

PHP-based web interface for viewing aggregated pageview statistics on Caddy servers.

## Steps

- Create password hash
- Configure Caddy to add auth
- Reload Caddy
- Upload files
- Visit: https://{domain}/stats/

## Production Deployment

### Create password hash

```bash
caddy hash-password
# Enter password when prompted
# Copy the bcrypt hash (starts with $2a$14$)
```

### Configure Caddy

Edit `/etc/caddy/sites-available/{domain}.caddy` (substitute `{domain}` with your domain). Replace `$2a$14$your_bcrypt_hash_here` with the bcrypt hash you created above:

```caddy
{domain} {
    root * /var/www/{domain}/public

    # Stats viewer with basic auth
    handle /stats* {
        basic_auth {
            stats $2a$14$your_bcrypt_hash_here
        }
        php_fastcgi unix//run/php/php8.3-fpm.sock
        file_server
    }

    # Regular site configuration continues...
    php_fastcgi unix//run/php/php8.3-fpm.sock
    encode gzip
    file_server

    log {
        output file /var/log/caddy/{domain}-access.log {
            roll_size 100MiB
            roll_keep 10
            roll_keep_for 87600h
        }
        format json
    }
}
```

**Note:** Adjust `php8.3-fpm.sock` to match your PHP version. Check with: `ls /var/run/php/`

### Reload Caddy

```bash
caddy validate --config /etc/caddy/Caddyfile
caddy reload --config /etc/caddy/Caddyfile
```

### Upload files

Substitute `{server}` with the server hostname/IP and `{domain}` with the domain:

```bash
rsync -avz pageview-tracking/php/{index.php,day.php,views.php,logs.php} {server-alias}:/var/www/{domain}/public/stats/
```

Visit: https://{domain}/stats/

**To logout:** Visit `https://logout@{domain}/stats/` to clear saved credentials.