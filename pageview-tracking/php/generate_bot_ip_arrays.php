<?php

/**
 * Generate Bot IP Range Arrays
 *
 * Reads bot IP ranges from multiple JSON sources and generates PHP files
 * with hardcoded arrays for fast IP checking.
 *
 * Supported bots:
 *   - Google (Googlebot crawler)
 *   - Bing (Bingbot, Microsoft ARIN registry)
 *
 * Input files (from ../../resources/):
 *   Google:
 *     - googlebot.json (Googlebot crawler IPs)
 *   Bing:
 *     - bing.com-toolbox-bingbot.json
 *     - whois.arin.net-rest-nets-q-microsoft.json (ARIN registry)
 *
 * Output files (to plugins/pageview-tracking/):
 *   - google_ip_ranges.php
 *   - bing_ip_ranges.php
 *
 * To generate the whois.arin.net-rest-nets-q-{company}.json files, run:
 *   - convert_arin_xml_to_json.php
 */

/* ─────────────────────────────
   Helper Functions
   ───────────────────────────── */

/**
 * Process bot sources and return IPv4/IPv6 ranges
 *
 * @param array $sources Array of source files
 *
 * @return array Array with 'ipv4' and 'ipv6' keys
 */
function processBotSources(array $sources): array
{
    $ipv4Ranges = [];
    $ipv6Ranges = [];

    foreach ($sources as $source => $file) {
        $json = file_get_contents($file);
        $data = json_decode($json, true);

        if (!isset($data['prefixes']) || !is_array($data['prefixes'])) {
            echo '    ⚠ Warning: Invalid JSON structure in ' . basename($file) . ", skipping\n";

            continue;
        }

        foreach ($data['prefixes'] as $prefix) {
            if (isset($prefix['ipv4Prefix'])) {
                $cidr = $prefix['ipv4Prefix'];

                // Parse CIDR notation
                [$ip, $prefixLen] = explode('/', $cidr, 2);

                // Calculate start and end IP addresses (32-bit safe)
                $ipLong = ip2long($ip);
                if ($ipLong === false) {
                    continue; // Skip invalid IP addresses
                }
                $prefix = (int) $prefixLen;

                // Build a 32-bit mask without shifting negatives
                $mask32 = ((0xFFFFFFFF << (32 - $prefix)) & 0xFFFFFFFF);

                // Clamp all intermediates to 32 bits
                $start32 = ($ipLong & $mask32) & 0xFFFFFFFF;
                $end32   = ($start32 | (~$mask32 & 0xFFFFFFFF)) & 0xFFFFFFFF;

                // Store as zero-padded strings (32-bit safe, no overflow)
                $start = sprintf('%010u', $start32);
                $end   = sprintf('%010u', $end32);

                $ipv4Ranges[] = [
                    'start'  => $start,
                    'end'    => $end,
                    'cidr'   => $cidr,
                    'source' => $source,
                ];
            } elseif (isset($prefix['ipv6Prefix'])) {
                $cidr = $prefix['ipv6Prefix'];

                // Parse CIDR notation
                [$ip, $prefixLen] = explode('/', $cidr, 2);

                $ipv6Ranges[] = [
                    'cidr'          => $cidr,
                    'prefix_length' => (int)$prefixLen,
                    'source'        => $source,
                ];
            }
        }
    }

    // Sort IPv4 ranges by start address (strcmp for zero-padded strings)
    usort($ipv4Ranges, function ($a, $b) {
        return strcmp($a['start'], $b['start']);
    });

    // Sort IPv6 ranges by CIDR
    usort($ipv6Ranges, function ($a, $b) {
        return strcmp($a['cidr'], $b['cidr']);
    });

    // Remove duplicates while preserving sources
    $ipv4Ranges = mergeDuplicates($ipv4Ranges, 'ipv4');
    $ipv6Ranges = mergeDuplicates($ipv6Ranges, 'ipv6');

    return [
        'ipv4' => $ipv4Ranges,
        'ipv6' => $ipv6Ranges,
    ];
}

/**
 * Merge duplicate ranges, combining sources
 *
 * @param array  $ranges Array of ranges
 * @param string $type   'ipv4' or 'ipv6'
 *
 * @return array Merged ranges
 */
function mergeDuplicates(array $ranges, string $type): array
{
    $merged = [];

    if ($type === 'ipv4') {
        $seen = [];
        foreach ($ranges as $range) {
            $key = $range['start'] . '-' . $range['end'];
            if (isset($seen[$key])) {
                // Duplicate found - merge sources
                if (!in_array($range['source'], $seen[$key]['sources'])) {
                    $seen[$key]['sources'][] = $range['source'];
                }
            } else {
                $seen[$key] = [
                    'start'   => $range['start'],
                    'end'     => $range['end'],
                    'cidr'    => $range['cidr'],
                    'sources' => [$range['source']],
                ];
            }
        }
        $merged = array_values($seen);
    } else { // ipv6
        $seen = [];
        foreach ($ranges as $range) {
            $key = $range['cidr'];
            if (isset($seen[$key])) {
                // Duplicate found - merge sources
                if (!in_array($range['source'], $seen[$key]['sources'])) {
                    $seen[$key]['sources'][] = $range['source'];
                }
            } else {
                $seen[$key] = [
                    'cidr'          => $range['cidr'],
                    'prefix_length' => $range['prefix_length'],
                    'sources'       => [$range['source']],
                ];
            }
        }
        $merged = array_values($seen);
    }

    return $merged;
}

/**
 * Generate PHP file content
 *
 * @param array  $ipv4Ranges         Array of IPv4 ranges
 * @param array  $ipv6Ranges         Array of IPv6 ranges
 * @param string $title              Title for the PHP file
 * @param array  $sourcesDescription Array of source descriptions
 *
 * @return string PHP file content
 */
function generatePhpFile(array $ipv4Ranges, array $ipv6Ranges, string $title, array $sourcesDescription): string
{
    $php = "<?php\n\n";
    $php .= "/**\n";
    $php .= ' * ' . $title . "\n";
    $php .= " *\n";
    $php .= " * Generated by: generate_bot_ip_arrays.php\n";
    $php .= " *\n";
    $php .= " * Sources:\n";

    foreach ($sourcesDescription as $description) {
        $php .= ' *   - ' . $description . "\n";
    }

    $php .= " *\n";
    $php .= ' * Total IPv4 ranges: ' . count($ipv4Ranges) . "\n";
    $php .= ' * Total IPv6 ranges: ' . count($ipv6Ranges) . "\n";
    $php .= " */\n\n";
    $php .= "return [\n";
    $php .= "    'ipv4' => [\n";

    foreach ($ipv4Ranges as $range) {
        $sources = implode("', '", $range['sources']);
        $php .= "        ['start' => '{$range['start']}', 'end' => '{$range['end']}', 'cidr' => '{$range['cidr']}', 'sources' => ['$sources']],\n";
    }

    $php .= "    ],\n\n";
    $php .= "    'ipv6' => [\n";

    foreach ($ipv6Ranges as $range) {
        $sources = implode("', '", $range['sources']);
        $php .= "        ['cidr' => '{$range['cidr']}', 'prefix_length' => {$range['prefix_length']}, 'sources' => ['$sources']],\n";
    }

    $php .= "    ],\n";
    $php .= "];\n";

    return $php;
}

/* ─────────────────────────────
   Main Logic
   ───────────────────────────── */

$resourcesDir = __DIR__ . '/../../resources';
$outputDir    = __DIR__ . '/plugins/pageview-tracking';

// Configuration: bot sources
$bots = [
    'google' => [
        'output'  => $outputDir . '/google_ip_ranges.php',
        'title'   => 'Google IP Ranges',
        'sources' => [
            'googlebot' => $resourcesDir . '/googlebot.json',
        ],
        'sources_description' => [
            'developers.google.com/static/search/apis/ipranges/googlebot.json (Googlebot crawler)',
        ],
    ],
    'bing' => [
        'output'  => $outputDir . '/bing_ip_ranges.php',
        'title'   => 'Bing IP Ranges',
        'sources' => [
            'arin'    => $resourcesDir . '/whois.arin.net-rest-nets-q-microsoft.json',
            'bingbot' => $resourcesDir . '/bing.com-toolbox-bingbot.json',
        ],
        'sources_description' => [
            'ARIN whois registry (Microsoft)',
            'bing.com/toolbox/bingbot.json (Bingbot crawler)',
        ],
    ],
];

echo "Bot IP Range Generator\n";
echo str_repeat('=', 50) . "\n\n";

// Process each bot
foreach ($bots as $botName => $config) {
    echo 'Processing ' . ucfirst($botName) . "...\n";

    // Verify all input files exist
    foreach ($config['sources'] as $source => $file) {
        if (!file_exists($file)) {
            echo "  ⚠ Warning: Input file not found: $file (skipping)\n";
            unset($config['sources'][$source]);
        }
    }

    if (empty($config['sources'])) {
        echo "  ✗ No valid sources found for $botName, skipping\n\n";

        continue;
    }

    // Process this bot's sources
    $result = processBotSources($config['sources']);

    // Generate PHP file
    $output = generatePhpFile(
        $result['ipv4'],
        $result['ipv6'],
        $config['title'],
        $config['sources_description']
    );

    file_put_contents($config['output'], $output);

    echo '  ✓ IPv4: ' . count($result['ipv4']) . " ranges\n";
    echo '  ✓ IPv6: ' . count($result['ipv6']) . " ranges\n";
    echo '  ✓ Output: ' . basename($config['output']) . "\n";
    echo "\n";
}

echo str_repeat('=', 50) . "\n";
echo "✓ Complete!\n";
