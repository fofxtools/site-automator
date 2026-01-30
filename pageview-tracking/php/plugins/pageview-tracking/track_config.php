<?php

declare(strict_types=1);

/**
 * Tracking Configuration
 *
 * Data storage and exclude IP and user agent settings.
 */

return [
    /**
     * Path to .env file for loading environment variables.
     *
     * Example:
     * - '../../../../.env' (site root, one level above document root)
     */
    'env_file' => '../../../../.env',

    /**
     * Data root directory for flat file storage.
     *
     * Example:
     * - '/var/lib/pageview-tracking'
     */
    'data_root' => '/var/lib/pageview-tracking',

    /**
     * Individual IP addresses to exclude (IPv4 or IPv6).
     *
     * e.g. admin IP, banned IPs, etc.
     *
     * Example: ['127.0.0.1', '192.168.1.100', '2001:db8::1']
     */
    'exclude_ips' => [],

    /**
     * CIDR ranges to exclude (IPv4 or IPv6).
     *
     * Example: ['192.168.1.0/24', '2001:db8::/32']
     */
    'exclude_ips_cidr' => [],

    /**
     * User agent strings to exclude (exact match, case-insensitive).
     *
     * Example: ['BadBot/1.0', 'Scraper/2.0']
     */
    'exclude_user_agents_exact' => [],

    /**
     * User agent substrings to exclude (substring match, case-insensitive).
     *
     * Example: ['badbot', 'scraper']
     */
    'exclude_user_agents_substring' => [],
];
