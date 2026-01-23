# WordPress Deployer

Manage WordPress sites using WP-CLI commands over SSH.

## What it does

`WordPressDeployer` wraps WP-CLI commands and lets you:
- Configure site settings
- Install and manage themes/plugins
- Create posts and pages with featured images
- Disable comments and widgets
- Clean up demo content

## Setup

Requires a `WordOpsProvisioner` instance:

```python
from site_automator import WordOpsProvisioner, WordPressDeployer

wordops = WordOpsProvisioner.from_env()
wordpress = WordPressDeployer(wordops)
```

## Site Configuration

```python
# Configure site settings
wordpress.configure_site(
    "example.com",
    title="My Blog",
    description="Just another WordPress site",
    timezone="America/New_York",
    public=True,  # Allow search engines
    permalink_structure="/%postname%/",
)

# Sync admin password to match database password
wordpress.sync_admin_password_to_db("example.com")
```

## Themes

```python
# Install theme from WordPress.org
wordpress.install_theme("example.com", "astra", activate=True)

# Install theme from file
wordpress.install_theme("example.com", "/path/to/theme.zip", activate=True)

# Install without activating
wordpress.install_theme("example.com", "kadence", activate=False)

# Activate already-installed theme
wordpress.activate_theme("example.com", "kadence")

# Delete themes
wordpress.delete_themes("example.com", ["twentytwentythree", "twentytwentyfour"])
```

## Plugins

```python
# Install and activate plugins
wordpress.install_plugins(
    "example.com",
    ["akismet", "jetpack"],
    activate=True
)

# Install from file
wordpress.install_plugins(
    "example.com",
    ["/path/to/plugin.zip"],
    activate=True
)

# Activate already-installed plugins
wordpress.activate_plugins("example.com", ["akismet"])

# Deactivate plugins
wordpress.deactivate_plugins("example.com", ["akismet", "jetpack"])

# Deactivate all except specified
wordpress.deactivate_all_plugins("example.com", exclude=["nginx-helper"])
```

## Posts and Pages

```python
# Create a post
post_id = wordpress.create_post(
    "example.com",
    title="Hello World",
    content="This is my first post",
    status="publish",  # or "draft"
)

# Create a page
page_id = wordpress.create_post(
    "example.com",
    title="About Us",
    content="Learn more about our company",
    status="publish",
    post_type="page",
)

# Create with options
post_id = wordpress.create_post(
    domain="example.com",
    title="My Post",
    content="Content here",
    status="publish",
    post_type="post",
    author="admin",
    date="2024-01-15 10:30:00",
    slug="my-custom-slug",
    additional_flags=["--comment_status=closed"],
)
```

## Featured Images

```python
# Import image (returns attachment ID)
attachment_id = wordpress.ensure_attachment(
    "example.com",
    "/path/to/image.jpg",
    title="My Image",
    alt_text="Description",
)

# Set as featured image
wordpress.set_featured_image("example.com", post_id, attachment_id)

# Idempotent - same image path returns existing attachment
attachment_id = wordpress.ensure_attachment("example.com", "/path/to/image.jpg")
```

## Comments

```python
# Disable comments site-wide (manual method, does not remove comment boxes)
wordpress.disable_comments("example.com")

# Disable comments using plugin (removes comment boxes)
wordpress.disable_comments_with_plugin("example.com")

# Use local path for disable-comments plugin
wordpress.disable_comments_with_plugin(
    "example.com",
    plugin_path="/path/to/disable-comments.zip"
)
```

## Widgets

```python
# Delete widgets by ID (block-4 is Recent Comments)
wordpress.delete_widgets("example.com", ["block-3", "block-4"])

# List widgets to find IDs
output, _ = wordpress.wp("example.com", "widget list sidebar-1")
```

## Cleanup

```python
# Delete demo content (Hello World post, Sample Page, etc.)
wordpress.delete_demo_content("example.com")
```

## Run WP-CLI Directly

```python
# Run any WP-CLI command
output, exit_code = wordpress.wp("example.com", "plugin list --status=active")

# Don't raise on failure with check=False
output, exit_code = wordpress.wp("example.com", "post get 999", check=False)
```

## Complete Example

```python
from site_automator import WordOpsProvisioner, WordPressDeployer

wordops = WordOpsProvisioner.from_env()
wordpress = WordPressDeployer(wordops)

try:
    # Configure site
    wordpress.configure_site(
        "example.com",
        title="My Blog",
        description="Thoughts and ideas",
        permalink_structure="/%postname%/",
    )

    # Clean up
    wordpress.delete_demo_content("example.com")
    wordpress.disable_comments_with_plugin("example.com")
    wordpress.delete_widgets("example.com", ["block-4"])

    # Install theme
    wordpress.install_theme("example.com", "astra", activate=True)
    wordpress.delete_themes("example.com", ["twentytwentythree", "twentytwentyfour"])

    # Create content
    post_id = wordpress.create_post(
        "example.com",
        title="First Post",
        content="Welcome to my blog!",
        status="publish",
    )

    # Add featured image
    attachment_id = wordpress.ensure_attachment("example.com", "/path/to/image.jpg")
    wordpress.set_featured_image("example.com", post_id, attachment_id)

finally:
    wordops.close()
```