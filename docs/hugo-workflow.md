# Hugo Site Deployment Workflow

Deploy a complete Hugo site with automated publishing.

## Prerequisites

- Caddy server configured (see [caddy.md](caddy.md))
- Hugo installed on server
- Domain registered with Namecheap or GoDaddy
- Site configured in `sites.csv`

## Steps

- Configure DNS
- Setup Hugo site (enable Caddy domain, generate content, configure Hugo)
- Publish initial content
- Submit to search engines
- Crontab - Setup automated publishing
- Setup web viewer (optional, once per server)

## Production Deployment


```bash
python examples/setup_dns.py --site-id <site_id>
python examples/setup_site_hugo.py --site-id <site_id>
python scripts/publish_daily_hugo.py --site-id <site_id>
python examples/indexnow.py --site-id <site_id>
```

### Edit crontab

Add entry (replace paths with your actual paths):

```cron
PROJECT_PATH=/path/to/site-automator
VENV_PYTHON=/path/to/site-automator/.venv/bin/python

# <site_id> - Publish articles
0 0 * * * flock -n /tmp/<site_id>_publish.lock -c "cd $PROJECT_PATH && $VENV_PYTHON scripts/publish_daily_hugo.py --site-id <site_id>"
```

See [../scripts/crontab.example](../scripts/crontab.example) for more examples.

### Setup web viewer (optional)

Only need to set up on one domain per server.

See [../pageview-tracking/usage-web-viewer-caddy.md](../pageview-tracking/usage-web-viewer-caddy.md) for setup instructions.

## Troubleshooting

- Wait for DNS propagation (can take up to 48 hours)
- Verify Caddy is running: `systemctl status caddy`
- Check Caddy logs: `journalctl -u caddy -f`
- Check cron logs: `grep CRON /var/log/syslog | tail -20`