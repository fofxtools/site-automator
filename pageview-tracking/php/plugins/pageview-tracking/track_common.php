<?php

declare(strict_types=1);

namespace FOfX\Utility\PageviewTracking;

/* ─────────────────────────────
   Helpers
   ───────────────────────────── */

/**
 * Load tracking configuration from track_config.php.
 * Uses static caching to load only once per request.
 *
 * @return array Configuration array
 */
function load_tracking_config(): array
{
    static $config = null;
    if ($config === null) {
        $configFile = __DIR__ . '/track_config.php';
        $config     = file_exists($configFile) ? include $configFile : [];

        // Validate and fallback to empty array
        if (!is_array($config)) {
            $config = [];
        }
    }

    return $config;
}

/**
 * Load environment variables from a .env file.
 *
 * @param string $path Path to the .env file
 *
 * @return void
 */
function load_env($path)
{
    if (!file_exists($path)) {
        return;
    }

    $lines = file($path, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
    foreach ($lines as $line) {
        if (str_starts_with($line, '#')) {
            continue;
        }
        [$key, $value] = array_map('trim', explode('=', $line, 2));
        putenv("$key=$value");
    }
}

function str_clip(?string $v, int $len): string
{
    return substr((string)$v, 0, $len);
}

/**
 * Viewport dimension: accept 1...100000 px, else NULL.
 *
 * @param mixed $val
 *
 * @return int|null
 */
function sane_dimension_or_null($val): ?int
{
    if (!isset($val)) {
        return null;
    }
    $v = (int) $val;

    return ($v > 0 && $v <= 100000) ? $v : null;
}

/**
 * JS Date.now() in ms; keep if within [minMs, maxMs], else NULL.
 *
 * @param mixed $val
 * @param int   $minMs
 * @param int   $maxMs
 *
 * @return int|null
 */
function sane_ms_or_null($val, int $minMs, int $maxMs): ?int
{
    if (!isset($val)) {
        return null;
    }
    $v = (int) $val;

    return ($v >= $minMs && $v <= $maxMs) ? $v : null;
}

/**
 * Get the remote IP address of the client.
 *
 * Order: HTTP_CLIENT_IP → HTTP_X_FORWARDED_FOR → REMOTE_ADDR
 * If multiple IPs in X_FORWARDED_FOR, take the first. If blank, default to 127.0.0.1.
 * If invalid, return null (no exception).
 *
 * @return string|null A valid IP string, or null if invalid; returns '127.0.0.1' if none found.
 */
function get_remote_addr(): ?string
{
    $ipHeaders  = ['HTTP_CLIENT_IP', 'HTTP_X_FORWARDED_FOR', 'REMOTE_ADDR'];
    $remoteAddr = null;

    foreach ($ipHeaders as $header) {
        if (!empty($_SERVER[$header])) {
            $remoteAddr = $_SERVER[$header];
            if (strpos($remoteAddr, ',') !== false) {
                $remoteAddr = trim(explode(',', $remoteAddr)[0]);
            }

            break;
        }
    }

    if ($remoteAddr === null || $remoteAddr === '') {
        $remoteAddr = '127.0.0.1';
    }

    return filter_var($remoteAddr, FILTER_VALIDATE_IP) ? $remoteAddr : null;
}

/**
 * Internal page: URL path not empty and not '/'.
 *
 * @param string $url
 *
 * @return int 1 if internal, 0 if not
 */
function is_internal_page(string $url): int
{
    $path = (string) (parse_url($url, PHP_URL_PATH) ?? '');

    return ($path !== '' && $path !== '/') ? 1 : 0;
}

/**
 * Normalize domain name for consistent tracking.
 *
 * Handles:
 * - Removes www. prefix
 * - Removes port numbers
 * - Rejects IP addresses (IPv4 and IPv6)
 * - Rejects domains without a dot (localhost, wp-includes, intranet, etc.)
 * - Rejects empty/blank domains
 * - Lowercases and trims
 *
 * @param string $domain Raw domain string
 *
 * @return string Normalized domain, or empty string if invalid
 */
function normalize_domain(string $domain): string
{
    // Lowercase and trim
    $domain = strtolower(trim($domain));

    // Remove trailing dot (FQDN: example.com. → example.com)
    $domain = rtrim($domain, '.');

    // Reject empty/blank early
    if ($domain === '') {
        return '';
    }

    // Reject anything containing slashes (not a hostname)
    if (str_contains($domain, '/')) {
        return '';
    }

    // Reject IP addresses (IPv4 and IPv6) before port removal
    // This prevents IPv6 addresses from being truncated
    if (filter_var($domain, FILTER_VALIDATE_IP)) {
        return '';
    }

    // Remove port numbers (e.g., localhost:8000 → localhost)
    // Check for IPv4:port pattern (e.g., 127.0.0.1:8000)
    $colonPos = strpos($domain, ':');
    if ($colonPos !== false) {
        $domainWithoutPort = substr($domain, 0, $colonPos);
        // After removing port, check if result is IPv4 address and reject it
        if (filter_var($domainWithoutPort, FILTER_VALIDATE_IP, FILTER_FLAG_IPV4)) {
            return '';
        }
        $domain = $domainWithoutPort;
    }

    // Remove www. prefix
    if (str_starts_with($domain, 'www.')) {
        $domain = substr($domain, 4);
    }

    // Reject domains without a dot (localhost, wp-includes, intranet, etc.)
    if (!str_contains($domain, '.')) {
        return '';
    }

    return $domain;
}

/**
 * Conditionally log error messages based on configuration.
 *
 * Checks LOG_LEVEL from .env.
 * Only logs if LOG_LEVEL is 'error' or lower severity (warning/notice/info/debug).
 * Defaults to logging if no configuration is found (fail-safe).
 *
 * Uses Monolog/PSR-3 severity hierarchy (higher number = more severe).
 *
 * Uses PHP's error_log() which writes to the default error log location.
 * Common default locations:
 *
 * - Apache: /var/log/apache2/error.log (or /var/log/apache2/[site]-error.log)
 * - Nginx: /var/log/nginx/[site].error.log (PHP-FPM stderr forwarded to Nginx)
 * - LiteSpeed:  /usr/local/lsws/logs/error.log (or /var/log/lsws/error.log)
 *
 * @param string $message The error message to log
 *
 * @return void
 */
function conditional_error_log(string $message): void
{
    static $shouldLog = null;

    // Cache the decision (config won't change during request)
    if ($shouldLog === null) {
        // Default to 'debug' (log everything) if no config found
        $shouldLog = true;

        // Define severity hierarchy matching Monolog/PSR-3 (higher number = more severe)
        $levels = [
            'debug'     => 100,
            'info'      => 200,
            'notice'    => 250,
            'warning'   => 300,
            'error'     => 400,  // threshold
            'critical'  => 500,
            'alert'     => 550,
            'emergency' => 600,
        ];

        // Check .env LOG_LEVEL
        $logLevel = getenv('LOG_LEVEL');
        if ($logLevel !== false) {
            $logLevel = strtolower(trim($logLevel));
            // Only log if configured level is 'error' or lower severity (warning/notice/info/debug)
            if (isset($levels[$logLevel])) {
                $shouldLog = ($levels[$logLevel] <= $levels['error']);
            }
        }
    }

    if ($shouldLog) {
        error_log($message);
    }
}

/* ─────────────────────────────
   Bot Detection - User Agent
   ───────────────────────────── */

/**
 * Check if user agent string contains "googlebot" (case-insensitive).
 *
 * @param string $userAgent User agent string
 *
 * @return bool True if googlebot detected
 */
function is_googlebot_ua(string $userAgent): bool
{
    return stripos($userAgent, 'googlebot') !== false;
}

/**
 * Check if user agent string contains "bingbot" (case-insensitive).
 *
 * @param string $userAgent User agent string
 *
 * @return bool True if bingbot detected
 */
function is_bingbot_ua(string $userAgent): bool
{
    return stripos($userAgent, 'bingbot') !== false;
}

/* ─────────────────────────────
   Bot Detection - IP Ranges
   ───────────────────────────── */

/**
 * Load IP ranges for a specific bot.
 * Returns empty arrays if file not found.
 *
 * @param string $bot Bot name ('google' or 'bing')
 *
 * @return array Array with 'ipv4' and 'ipv6' keys
 */
function load_bot_ip_ranges(string $bot): array
{
    $file = __DIR__ . "/{$bot}_ip_ranges.php";
    if (!file_exists($file)) {
        return ['ipv4' => [], 'ipv6' => []];
    }

    return include $file;
}

/**
 * Check if IPv4 address is in any of the given ranges.
 * Uses CIDR-based binary comparison (32-bit safe, matches IPv6 logic).
 *
 * @param string $ip     IPv4 address
 * @param array  $ranges Array of IPv4 ranges with 'cidr', 'sources' keys
 * @param array  $filter Optional array of source names to filter by (empty = all sources)
 *
 * @return bool True if IP is in range
 */
function is_ipv4_in_ranges(string $ip, array $ranges, array $filter = []): bool
{
    // Validate IPv4 before converting to binary
    if (!filter_var($ip, FILTER_VALIDATE_IP, FILTER_FLAG_IPV4)) {
        return false;
    }

    $ipBin = inet_pton($ip);
    if ($ipBin === false || strlen($ipBin) !== 4) {
        return false;
    }

    foreach ($ranges as $range) {
        // Apply source filter first (before parsing CIDR)
        if (!empty($filter)) {
            $sources       = $range['sources'] ?? [];
            $matchesFilter = false;
            foreach ($filter as $source) {
                if (in_array($source, $sources, true)) {
                    $matchesFilter = true;

                    break;
                }
            }
            if (!$matchesFilter) {
                continue;
            }
        }

        // Use CIDR for comparison (platform-agnostic)
        if (empty($range['cidr']) || strpos($range['cidr'], '/') === false) {
            continue;
        }

        [$subnet, $prefixLen] = explode('/', $range['cidr'], 2);
        if (!filter_var($subnet, FILTER_VALIDATE_IP, FILTER_FLAG_IPV4)) {
            continue;
        }
        $subnetBin = inet_pton($subnet);
        if ($subnetBin === false || strlen($subnetBin) !== 4) {
            continue;
        }

        $prefixLen = (int)$prefixLen;
        if ($prefixLen < 0 || $prefixLen > 32) {
            continue;
        }

        // Create mask
        $maskBin = str_repeat("\xff", (int)($prefixLen / 8));
        if ($prefixLen % 8 !== 0) {
            $maskBin .= chr(0xff ^ ((1 << (8 - ($prefixLen % 8))) - 1));
        }
        $maskBin = str_pad($maskBin, 4, "\x00");

        // Compare
        if (($ipBin & $maskBin) === ($subnetBin & $maskBin)) {
            return true;
        }
    }

    return false;
}

/**
 * Check if IPv6 address is in any of the given ranges.
 *
 * @param string $ip     IPv6 address
 * @param array  $ranges Array of IPv6 ranges with 'cidr', 'prefix_length', 'sources' keys
 * @param array  $filter Optional array of source names to filter by (empty = all sources)
 *
 * @return bool True if IP is in range
 */
function is_ipv6_in_ranges(string $ip, array $ranges, array $filter = []): bool
{
    // Validate IPv6 before converting to binary
    if (!filter_var($ip, FILTER_VALIDATE_IP, FILTER_FLAG_IPV6)) {
        return false;
    }

    $ipBin = inet_pton($ip);
    if ($ipBin === false || strlen($ipBin) !== 16) {
        return false;
    }

    foreach ($ranges as $range) {
        // Apply source filter first (before parsing CIDR)
        if (!empty($filter)) {
            $sources       = $range['sources'] ?? [];
            $matchesFilter = false;
            foreach ($filter as $source) {
                if (in_array($source, $sources, true)) {
                    $matchesFilter = true;

                    break;
                }
            }
            if (!$matchesFilter) {
                continue;
            }
        }

        // Use CIDR for comparison (platform-agnostic)
        if (empty($range['cidr']) || strpos($range['cidr'], '/') === false) {
            continue;
        }

        // Parse CIDR
        [$subnet, $prefixLen] = explode('/', $range['cidr'], 2);
        if (!filter_var($subnet, FILTER_VALIDATE_IP, FILTER_FLAG_IPV6)) {
            continue;
        }
        $subnetBin = inet_pton($subnet);
        if ($subnetBin === false || strlen($subnetBin) !== 16) {
            continue;
        }

        $prefixLen = (int)$prefixLen;
        if ($prefixLen < 0 || $prefixLen > 128) {
            continue;
        }

        // Create mask
        $maskBin = str_repeat("\xff", (int)($prefixLen / 8));
        if ($prefixLen % 8 !== 0) {
            $maskBin .= chr(0xff ^ ((1 << (8 - ($prefixLen % 8))) - 1));
        }
        $maskBin = str_pad($maskBin, 16, "\x00");

        // Compare
        if (($ipBin & $maskBin) === ($subnetBin & $maskBin)) {
            return true;
        }
    }

    return false;
}

/**
 * Helper function to check if an IP belongs to a bot.
 * Auto-detects IPv4 vs IPv6.
 *
 * @param string $ip      IP address (IPv4 or IPv6)
 * @param string $bot     Bot name ('google' or 'bing')
 * @param array  $sources Optional array of source names to filter by (empty = all sources)
 *
 * @return bool True if IP matches the bot and sources
 */
function check_bot_ip(string $ip, string $bot, array $sources = []): bool
{
    static $cache = [];

    if (!isset($cache[$bot])) {
        $cache[$bot] = load_bot_ip_ranges($bot);
    }

    $ranges = $cache[$bot];

    if (filter_var($ip, FILTER_VALIDATE_IP, FILTER_FLAG_IPV4)) {
        return is_ipv4_in_ranges($ip, $ranges['ipv4'], $sources);
    } elseif (filter_var($ip, FILTER_VALIDATE_IP, FILTER_FLAG_IPV6)) {
        return is_ipv6_in_ranges($ip, $ranges['ipv6'], $sources);
    }

    return false;
}

/**
 * Check if IP is a Googlebot IP (only 'goog' source).
 * Auto-detects IPv4 vs IPv6.
 *
 * @param string $ip IP address (IPv4 or IPv6)
 *
 * @return bool True if IP is a Googlebot IP
 */
function is_googlebot_ip(string $ip): bool
{
    return check_bot_ip($ip, 'google', ['goog']);
}

/**
 * Check if IP is any Google IP (all sources).
 * Auto-detects IPv4 vs IPv6.
 *
 * @param string $ip IP address (IPv4 or IPv6)
 *
 * @return bool True if IP is a Google IP
 */
function is_google_ip(string $ip): bool
{
    return check_bot_ip($ip, 'google');
}

/**
 * Check if IP is a Bingbot IP (only 'bingbot' source).
 * Auto-detects IPv4 vs IPv6.
 *
 * @param string $ip IP address (IPv4 or IPv6)
 *
 * @return bool True if IP is a Bingbot IP
 */
function is_bingbot_ip(string $ip): bool
{
    return check_bot_ip($ip, 'bing', ['bingbot']);
}

/**
 * Check if IP is any Microsoft IP (all sources).
 * Auto-detects IPv4 vs IPv6.
 *
 * @param string $ip IP address (IPv4 or IPv6)
 *
 * @return bool True if IP is a Microsoft IP
 */
function is_microsoft_ip(string $ip): bool
{
    return check_bot_ip($ip, 'bing');
}

/**
 * Get bot detection signals for IP and user agent
 *
 * @param string $ip        IP address
 * @param string $userAgent User agent string
 *
 * @return array Array of bot signal codes (e.g., ['gb_ip', 'gb_ua'])
 */
function get_bot_signals(string $ip, string $userAgent): array
{
    $signals = [];

    // IP-based detection
    if ($ip !== '') {
        if (is_googlebot_ip($ip)) {
            $signals[] = 'gb_ip';
        }
        if (is_google_ip($ip)) {
            $signals[] = 'g_ip';
        }
        if (is_bingbot_ip($ip)) {
            $signals[] = 'bb_ip';
        }
        if (is_microsoft_ip($ip)) {
            $signals[] = 'm_ip';
        }
    }

    // UA-based detection
    if ($userAgent !== '') {
        if (is_googlebot_ua($userAgent)) {
            $signals[] = 'gb_ua';
        }
        if (is_bingbot_ua($userAgent)) {
            $signals[] = 'bb_ua';
        }
    }

    return $signals;
}

/* ─────────────────────────────
   Exclude Checking
   ───────────────────────────── */

/**
 * Check if an IP address is within a CIDR range.
 * Supports both IPv4 and IPv6.
 *
 * @param string $ip   IP address to check
 * @param string $cidr CIDR range (e.g., '192.168.1.0/24' or '2001:db8::/32')
 *
 * @return bool True if IP is in CIDR range
 */
function ip_in_cidr(string $ip, string $cidr): bool
{
    // Validate CIDR format
    if (strpos($cidr, '/') === false) {
        return false;
    }

    [$subnet, $prefixStr] = explode('/', $cidr, 2);
    $subnet               = trim($subnet);
    $prefixStr            = trim($prefixStr);

    // Prefix must be digits only
    if ($prefixStr === '' || !ctype_digit($prefixStr)) {
        return false;
    }
    $prefixLen = (int)$prefixStr;

    // Validate IP and subnet
    $ipBin     = inet_pton($ip);
    $subnetBin = inet_pton($subnet);

    if ($ipBin === false || $subnetBin === false) {
        return false;
    }

    // Must be same IP version
    if (strlen($ipBin) !== strlen($subnetBin)) {
        return false;
    }

    $maxPrefixLen = (strlen($ipBin) === 4) ? 32 : 128;

    // Validate prefix length
    if ($prefixLen < 0 || $prefixLen > $maxPrefixLen) {
        return false;
    }

    // Create mask
    $fullBytes = intdiv($prefixLen, 8);
    $remBits   = $prefixLen % 8;

    $mask = ($fullBytes > 0) ? str_repeat("\xff", $fullBytes) : '';
    if ($remBits > 0) {
        $mask .= chr(0xff ^ ((1 << (8 - $remBits)) - 1));
    }
    $mask = str_pad($mask, strlen($ipBin), "\x00");

    // Compare network portions
    return ($ipBin & $mask) === ($subnetBin & $mask);
}

/**
 * Check if an IP address is excluded.
 *
 * @param string     $ip         IP address to check
 * @param array|null $ips        Individual IPs to check against (null = use config)
 * @param array|null $cidrBlocks CIDR ranges to check against (null = use config)
 *
 * @return bool True if IP is excluded
 */
function is_ip_excluded(string $ip, ?array $ips = null, ?array $cidrBlocks = null): bool
{
    // Load config if not provided
    if ($ips === null || $cidrBlocks === null) {
        $config = load_tracking_config();

        if ($ips === null) {
            $ips = $config['exclude_ips'] ?? [];
        }
        if ($cidrBlocks === null) {
            $cidrBlocks = $config['exclude_ips_cidr'] ?? [];
        }
    }

    // Clean config arrays (trim whitespace, remove empty strings, ensure strings)
    $ips        = array_filter(array_map(static fn ($v) => is_string($v) ? trim($v) : '', $ips));
    $cidrBlocks = array_filter(array_map(static fn ($v) => is_string($v) ? trim($v) : '', $cidrBlocks));

    // Validate IP
    $ipBin = inet_pton($ip);
    if ($ipBin === false) {
        return false; // Invalid IPs can not be excluded
    }

    // Normalize IPv4-mapped IPv6 to IPv4
    $ipForCidr = $ip; // Default to original
    if (strlen($ipBin) === 16 && substr($ipBin, 0, 12) === str_repeat("\x00", 10) . "\xFF\xFF") {
        $ipv4Tail  = substr($ipBin, 12);
        $ipBin     = $ipv4Tail;                // For exact matches
        $ipForCidr = inet_ntop($ipv4Tail); // For CIDR checks
    }

    // Check individual IPs (binary comparison to handle IPv6 textual variants)
    foreach ($ips as $excludedIp) {
        $excludedBin = inet_pton($excludedIp);
        if ($excludedBin === false) {
            continue;
        }

        // Normalize IPv4-mapped IPv6 to IPv4
        if (strlen($excludedBin) === 16 && substr($excludedBin, 0, 12) === str_repeat("\x00", 10) . "\xFF\xFF") {
            $excludedBin = substr($excludedBin, 12);
        }

        if (strlen($ipBin) === strlen($excludedBin) && $ipBin === $excludedBin) {
            return true;
        }
    }

    // Check CIDR ranges (use normalized IP string)
    foreach ($cidrBlocks as $cidr) {
        if (ip_in_cidr($ipForCidr, $cidr)) {
            return true;
        }
    }

    return false;
}

/**
 * Check if a user agent is excluded.
 *
 * @param string     $userAgent  User agent string to check
 * @param array|null $exact      Exact match strings (null = use config)
 * @param array|null $substrings Substring match strings (null = use config)
 *
 * @return bool True if user agent is excluded
 */
function is_user_agent_excluded(string $userAgent, ?array $exact = null, ?array $substrings = null): bool
{
    // Load config if not provided
    if ($exact === null || $substrings === null) {
        $config = load_tracking_config();

        if ($exact === null) {
            $exact = $config['exclude_user_agents_exact'] ?? [];
        }
        if ($substrings === null) {
            $substrings = $config['exclude_user_agents_substring'] ?? [];
        }
    }

    // Check exact matches (case-insensitive)
    foreach ($exact as $excludedUA) {
        if (strcasecmp($userAgent, $excludedUA) === 0) {
            return true;
        }
    }

    // Check substring matches (case-insensitive)
    foreach ($substrings as $substring) {
        if (stripos($userAgent, $substring) !== false) {
            return true;
        }
    }

    return false;
}

/**
 * Check if an IP address or user agent is excluded.
 *
 * @param string $ip        IP address to check
 * @param string $userAgent User agent string to check
 *
 * @return bool True if either IP or user agent is excluded
 */
function is_excluded(string $ip, string $userAgent): bool
{
    return is_ip_excluded($ip) || is_user_agent_excluded($userAgent);
}

/* ─────────────────────────────
   Config
   ───────────────────────────── */

/**
 * Get tracking configuration from request.
 *
 * @return array Tracking configuration
 */
function get_tracking_config(): array
{
    // Try to parse JSON payload (if POST with JSON)
    $raw     = '';
    $payload = [];
    if (($_SERVER['REQUEST_METHOD'] ?? '') === 'POST') {
        $contentType = $_SERVER['CONTENT_TYPE'] ?? $_SERVER['HTTP_CONTENT_TYPE'] ?? '';
        if (stripos($contentType, 'application/json') !== false) {
            $raw     = file_get_contents('php://input');
            $decoded = json_decode($raw, true);
            if (is_array($decoded)) {
                $payload = $decoded;
            }
        }
    }

    $type   = (string) ($payload['type'] ?? $_GET['type'] ?? '');
    $viewId = (string) ($payload['view_id'] ?? $_GET['view_id'] ?? '');

    $url      = str_clip($payload['url'] ?? $_GET['url'] ?? $_SERVER['REQUEST_URI'] ?? '', 4096);
    $referrer = str_clip($payload['referrer'] ?? $_GET['referrer'] ?? '', 4096);
    $language = str_clip($payload['language'] ?? $_GET['language'] ?? '', 64);
    $timezone = str_clip($payload['timezone'] ?? $_GET['timezone'] ?? '', 64);

    $userAgent = str_clip($_SERVER['HTTP_USER_AGENT'] ?? '', 1024);

    // Extract domain from URL, fallback to HTTP_HOST for relative URLs
    $parsedHost = parse_url($url, PHP_URL_HOST);
    if ($parsedHost === null || $parsedHost === '') {
        // URL is relative (e.g., /scripts/test.php), use HTTP_HOST
        $parsedHost = $_SERVER['HTTP_HOST'] ?? '';
    }
    $domain = normalize_domain((string) $parsedHost);
    $domain = str_clip($domain, 255);

    $viewportWidth  = sane_dimension_or_null($payload['viewport_width'] ?? null);
    $viewportHeight = sane_dimension_or_null($payload['viewport_height'] ?? null);

    // timestamps (ms) window: 2000-01-01...now + 1y
    $nowMs = (int) round(microtime(true) * 1000);
    $minMs = 946684800000;            // 2000-01-01T00:00:00Z
    $maxMs = $nowMs + 31_536_000_000; // +1 year (365d * 24 * 60 * 60 * 1000)

    $tsPageviewMs = sane_ms_or_null($payload['ts_pageview_ms'] ?? null, $minMs, $maxMs);
    $tsMetricsMs  = sane_ms_or_null($payload['ts_metrics_ms'] ?? null, $minMs, $maxMs);

    // perf metrics (1...1h)
    $ttfbMs = sane_ms_or_null($payload['ttfb_ms'] ?? null, 1, 3_600_000);
    $dclMs  = sane_ms_or_null($payload['dom_content_loaded_ms'] ?? null, 1, 3_600_000);
    $loadMs = sane_ms_or_null($payload['load_event_end_ms'] ?? null, 1, 3_600_000);

    // engagement metrics (simple clamping, not strict validation)
    $timeOnPageMs = max(0, (int)($payload['time_on_page_ms'] ?? 0));
    $scrollDepth  = max(0, min(100, (int)($payload['scroll_depth'] ?? 0)));
    $scrollEvents = max(0, (int)($payload['scroll_events'] ?? 0));

    // page bucket (UTC)
    $pageviewDate = $tsPageviewMs
        ? gmdate('Y-m-d', (int) ($tsPageviewMs / 1000))
        : gmdate('Y-m-d');

    // Get IP
    $ip = get_remote_addr();

    // 1 if path beyond '/', else 0
    $isInternal = is_internal_page($url);

    // Default category (null = no category set)
    $category = null;

    // Load tracking config to get env_file setting
    $trackConfig = load_tracking_config();
    $envFile     = $trackConfig['env_file'] ?? '../../../../.env';

    // Load the specified .env file
    // If absolute path (starts with /), use as-is; otherwise resolve relative to __DIR__
    if (str_starts_with($envFile, '/')) {
        $resolvedPath = $envFile;
    } else {
        $resolvedPath = __DIR__ . '/' . $envFile;
    }

    if (file_exists($resolvedPath)) {
        load_env($resolvedPath);
    }

    // Check for TRACKING_ENABLED environment variable
    $trackingEnabled = (getenv('TRACKING_ENABLED') === 'true');
    if (!$trackingEnabled) {
        return [
            'tracking_enabled' => false,
        ];
    }

    // Get data root directory for flat file storage
    $dataRoot = $trackConfig['data_root'] ?? '/var/lib/pageview-tracking';

    // If absolute path (starts with /), use as-is; otherwise resolve relative to __DIR__
    if (str_starts_with($dataRoot, '/')) {
        $resolvedDataRoot = $dataRoot;
    } else {
        $resolvedDataRoot = __DIR__ . '/' . $dataRoot;
    }

    return [
        'raw'              => $raw,
        'payload'          => $payload,
        'type'             => $type,
        'view_id'          => $viewId,
        'url'              => $url,
        'referrer'         => $referrer,
        'language'         => $language,
        'timezone'         => $timezone,
        'user_agent'       => $userAgent,
        'domain'           => $domain,
        'viewport_width'   => $viewportWidth,
        'viewport_height'  => $viewportHeight,
        'now_ms'           => $nowMs,
        'min_ms'           => $minMs,
        'max_ms'           => $maxMs,
        'ts_pageview_ms'   => $tsPageviewMs,
        'ts_metrics_ms'    => $tsMetricsMs,
        'ttfb_ms'          => $ttfbMs,
        'dcl_ms'           => $dclMs,
        'load_ms'          => $loadMs,
        'time_on_page_ms'  => $timeOnPageMs,
        'scroll_depth'     => $scrollDepth,
        'scroll_events'    => $scrollEvents,
        'pageview_date'    => $pageviewDate,
        'ip'               => $ip,
        'is_internal'      => $isInternal,
        'category'         => $category,
        'tracking_enabled' => $trackingEnabled,
        'data_root'        => $resolvedDataRoot,
    ];
}
