<?php

/**
 * Convert ARIN XML to JSON format
 *
 * Extracts IP ranges from ARIN whois XML files and outputs in JSON format
 * matching the structure of gstatic.com JSON files (prefixes array with ipv4Prefix/ipv6Prefix)
 *
 * Processes:
 *   - microsoft
 *
 * Input:  ../../resources/whois.arin.net-rest-nets-q-{company}.xml
 * Output: ../../resources/whois.arin.net-rest-nets-q-{company}.json
 */

$resourcesDir = __DIR__ . '/../../resources';
$companies    = ['microsoft'];

echo "ARIN XML to JSON Converter\n";
echo str_repeat('=', 50) . "\n\n";

foreach ($companies as $company) {
    echo "Processing {$company}...\n";

    $xmlFile    = $resourcesDir . "/whois.arin.net-rest-nets-q-{$company}.xml";
    $outputFile = $resourcesDir . "/whois.arin.net-rest-nets-q-{$company}.json";

    // Validate input file exists
    if (!file_exists($xmlFile)) {
        echo "  ⚠ Skipping: XML file not found\n\n";

        continue;
    }

    // Load and parse XML
    $xml = @simplexml_load_file($xmlFile);
    if ($xml === false) {
        echo "  ✗ Error: Failed to load XML file\n\n";

        continue;
    }

    // Register namespace
    $xml->registerXPathNamespace('ns', 'https://www.arin.net/whoisrws/core/v1');

    // Get all netBlock elements
    $netBlocks = $xml->xpath('//ns:netBlock');

    if (empty($netBlocks)) {
        echo "  ✗ Error: No netBlock elements found in XML\n\n";

        continue;
    }

    $ipv4Cidrs = [];
    $ipv6Cidrs = [];

    foreach ($netBlocks as $netBlock) {
        $startAddress = (string)$netBlock->startAddress;
        $cidrLength   = (string)$netBlock->cidrLength;

        if (!empty($startAddress) && !empty($cidrLength)) {
            $cidr = $startAddress . '/' . $cidrLength;

            // Separate IPv4 and IPv6
            if (filter_var($startAddress, FILTER_VALIDATE_IP, FILTER_FLAG_IPV4)) {
                $ipv4Cidrs[] = $cidr;
            } elseif (filter_var($startAddress, FILTER_VALIDATE_IP, FILTER_FLAG_IPV6)) {
                $ipv6Cidrs[] = $cidr;
            }
        }
    }

    // Sort and deduplicate
    $ipv4Cidrs = array_unique($ipv4Cidrs);
    $ipv6Cidrs = array_unique($ipv6Cidrs);
    sort($ipv4Cidrs, SORT_STRING);
    sort($ipv6Cidrs, SORT_STRING);

    // Build prefixes array in Google's JSON format
    $prefixes = [];

    // Add IPv4 prefixes
    foreach ($ipv4Cidrs as $cidr) {
        $prefixes[] = ['ipv4Prefix' => $cidr];
    }

    // Add IPv6 prefixes
    foreach ($ipv6Cidrs as $cidr) {
        $prefixes[] = ['ipv6Prefix' => $cidr];
    }

    // Create JSON structure matching gstatic.com format
    $output = [
        'prefixes' => $prefixes,
    ];

    // Write JSON output with pretty formatting
    file_put_contents($outputFile, json_encode($output, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n");

    echo '  ✓ IPv4: ' . count($ipv4Cidrs) . " ranges\n";
    echo '  ✓ IPv6: ' . count($ipv6Cidrs) . " ranges\n";
    echo '  ✓ Total: ' . count($prefixes) . " prefixes\n";
    echo '  ✓ Output: ' . basename($outputFile) . "\n";
    echo "\n";
}

echo str_repeat('=', 50) . "\n";
echo "✓ Conversion complete!\n";
