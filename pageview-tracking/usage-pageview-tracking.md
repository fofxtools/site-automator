# Pageview and Bot Tracking

Pageview tracking system with bot detection using JavaScript and PHP.

## Bot IP Ranges Setup

For bot IP detection, we use source data from Google (gstatic.com), Microsoft (bing.com), and ARIN whois registry.

Download source IP data for Google and Bing from within the `resources/` folder. From project root:

```bash
cd resources

curl -L "https://whois.arin.net/rest/nets;q=google?showDetails=true&showARIN=true&showNonArinTopLevelNet=false&ext=netref2" \
  | xmllint --format - > whois.arin.net-rest-nets-q-google.xml

curl -s https://www.gstatic.com/ipranges/goog.json -o gstatic.com-ipranges-goog.json

curl -s https://www.gstatic.com/ipranges/cloud.json -o gstatic.com-ipranges-cloud.json

curl -L "https://whois.arin.net/rest/nets;q=microsoft?showDetails=true&showARIN=true&showNonArinTopLevelNet=false&ext=netref2" \
  | xmllint --format - > whois.arin.net-rest-nets-q-microsoft.xml

curl -s https://www.bing.com/toolbox/bingbot.json -o bing.com-toolbox-bingbot.json
```

Process the downloaded data. From project root:

```bash
cd pageview-tracking/php
php convert_arin_xml_to_cidr.php
php generate_bot_ip_arrays.php
```

This creates:
- `pageview-tracking/php/plugins/pageview-tracking/google_ip_ranges.php`
- `pageview-tracking/php/plugins/pageview-tracking/bing_ip_ranges.php`

## WordPress Plugin

The tracking plugin is located at `pageview-tracking/php/plugins/pageview-tracking/`.

**Files:**
- `pageview-tracking.php` - Main plugin file
- `track_pageview.js` - JavaScript beacon
- `track_pageview.php` - PHP backend
- `track_bots.php` - Bot tracking (detects Googlebot and Bingbot)
- `track_common.php` - Shared functions
- `track_config.php` - Configuration (exclusions, data paths)
- `google_ip_ranges.php` - Google bot IP ranges (generated)
- `bing_ip_ranges.php` - Bing bot IP ranges (generated)
- `test_track_pageview.php` - Test page

**Features:** Tracks pageviews with performance metrics (TTFB, DCL, Load) and bot detection.

### Data Storage

Pageview data is stored as flat files in `/var/lib/pageview-tracking/raw/{domain}/{date}/`:
- `pageview.jsonl` - Pageview events
- `metrics.jsonl` - Performance metrics
- `bots.jsonl` - Bot signals

This folder will need to be created and writable by the web server. To do this, run the following commands:

```bash
sudo mkdir -p /var/lib/pageview-tracking
sudo chown -R $USER:www-data /var/lib/pageview-tracking
sudo chmod -R 775 /var/lib/pageview-tracking
sudo chmod g+s /var/lib/pageview-tracking
```

### Installation

**WordPress:**
1. Copy `pageview-tracking/php/plugins/pageview-tracking/` to your WordPress plugins directory
2. Activate the plugin in WordPress admin

The plugin will automatically enqueue the JavaScript tracking script and handle bot tracking.

**Standalone (Non-WordPress):**

Include the tracking script in your HTML pages:
```html
<script src="/path/to/pageview-tracking/track_pageview.js"></script>
```

For bot tracking, add to your PHP pages:
```php
<?php require_once __DIR__ . '/path/to/pageview-tracking/track_bots.php'; ?>
```

### Configuration

Edit `pageview-tracking/php/plugins/pageview-tracking/track_config.php`:

```php
return [
    // Path to .env file (relative to plugin directory)
    'env_file' => '../../../../.env',
    
    // Data root directory for flat file storage
    'data_root' => '/var/lib/pageview-tracking',
    
    // Exclude specific IPs
    'exclude_ips' => ['127.0.0.1'],
    
    // Exclude CIDR ranges
    'exclude_ips_cidr' => ['192.168.1.0/24'],
    
    // Exclude user agents (exact match)
    'exclude_user_agents_exact' => ['BadBot/1.0'],
    
    // Exclude user agents (substring match)
    'exclude_user_agents_substring' => ['badbot'],
];
```

### Testing

Visit the test page to verify tracking is working:
- `http://yoursite.com/wp-content/plugins/pageview-tracking/test_track_pageview.php`

## track_common.php Functions

Shared functions for all tracking scripts:
- `is_internal_page($url)` - Check if URL is an internal page
- `is_googlebot_ua($userAgent)` - Check if user agent is Googlebot
- `is_bingbot_ua($userAgent)` - Check if user agent is Bingbot
- `is_googlebot_ip($ip)` - Check if IP is Googlebot (only 'goog' source)
- `is_google_ip($ip)` - Check if IP is any Google IP (all sources)
- `is_bingbot_ip($ip)` - Check if IP is Bingbot (only 'bingbot' source)
- `is_microsoft_ip($ip)` - Check if IP is any Microsoft IP (all sources)
- `is_ip_excluded($ip)` - Check if IP is excluded according to `track_config.php`
- `is_user_agent_excluded($userAgent)` - Check if user agent is excluded according to `track_config.php`
- `is_excluded($ip, $userAgent)` - Check if IP or user agent is excluded according to `track_config.php`
- `get_bot_signals($ip, $userAgent)` - Get bot signals for an IP and user agent
- `get_tracking_config()` - Parse request data, resolve data root, and return tracking configuration array