# Hugo Deployer

Deploy and manage Hugo static sites over SSH.

## What it does

`HugoDeployer` manages Hugo sites and lets you:
- Initialize Hugo sites
- Install and configure themes
- Deploy content (markdown files)
- Build static sites
- Setup tracking and internal links

## Prerequisites

### Installing Hugo Extended

Hugo Extended is required (includes SCSS/Sass support). Install on your server:

```bash
# Set version (check https://github.com/gohugoio/hugo/releases/latest)
HUGO_VERSION="0.155.3"

cd /tmp

wget https://github.com/gohugoio/hugo/releases/download/v${HUGO_VERSION}/hugo_extended_${HUGO_VERSION}_linux-amd64.deb

sudo dpkg -i hugo_extended_${HUGO_VERSION}_linux-amd64.deb
```

Verify installation:

```bash
hugo version
```

**Note:** If you get `-bash: /usr/bin/hugo: No such file or directory` after install, either:
- Exit and re-enter your shell, or
- Clear the bash cache: `hash -r`

## Setup

Requires an SSH connection:

```python
from site_automator.ssh import SSHConnection
from site_automator.hugo import HugoDeployer

ssh = SSHConnection(host="your-server-alias")
hugo = HugoDeployer(ssh)
```

## Initial Setup

```python
# Complete initial setup
hugo.initial_setup("example.com")
```

This automatically:
- Initializes Hugo site skeleton
- Uploads theme from storage (uses config or explicit parameter)
- Applies theme overrides
- Writes hugo.toml configuration
- Creates robots.txt
- Sets up internal links partial
- Configures pageview tracking
- Sets correct permissions

## Themes

Available themes are defined in `config/themes.toml`.

```python
# Upload theme from local storage
hugo.upload_theme("example.com", "ananke")

# Apply theme overrides from resources
hugo.apply_theme_overrides("example.com", "ananke")
```

## Content Deployment

```python
# Deploy single article as page bundle
hugo.deploy_content_file(
    "example.com",
    slug="my-first-post",
    markdown_path=Path("content/my-first-post.md")
)

# Deploy entire directory of markdown files
hugo.deploy_content_directory(
    "example.com",
    local_content_dir="content/articles/markdown"
)
```

## Featured Images

```python
# Symlink shared image to site (assumes SHARED_IMAGES_PATH in .env)
hugo.symlink_shared_image("example.com", "cover.jpg")

# Set featured image in local markdown front matter
hugo.set_featured_image_local(
    site_id="mysite",
    slug="my-post",
    theme="ananke",
    image_url="/images/cover.jpg"
)
```

## Wipe Site

```python
# Wipe all site files (DESTRUCTIVE!)
hugo.wipe_site("example.com", confirm=True)

# Wipe but preserve specific directories
hugo.wipe_site(
    "example.com",
    confirm=True,
    exclude_dirs=["public/stats"]
)
```

## Complete Example

```python
from site_automator.caddy import CaddyProvisioner
from site_automator.hugo import HugoDeployer
from site_automator.utils import configure_logging

configure_logging()

caddy = CaddyProvisioner(host="your-server-alias")
hugo = HugoDeployer(caddy.ssh)

domain = "example.com"

try:
    # Initial setup
    caddy.enable_domain(domain)
    hugo.initial_setup(domain)

    # Deploy content
    hugo.deploy_content_directory(
        domain,
        local_content_dir="storage/content/mysite/articles/markdown"
    )

    # Build site
    hugo.build_site(domain)

finally:
    caddy.close()
```

