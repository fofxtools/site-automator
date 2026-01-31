<?php

declare(strict_types=1);

namespace FOfX\Utility\PageviewTracking;

require_once __DIR__ . '/track_common.php';

try {
    $config = get_tracking_config();
} catch (\Throwable $e) {
    conditional_error_log('track_bots.php get_tracking_config() error: ' . $e->getMessage());

    // Use return instead of exit as this file is included via PHP and is not an HTTP entry point
    // Using exit would kill the HTTP request lifecycle
    return;
}

// Exit gracefully if tracking is disabled
if (!$config['tracking_enabled']) {
    return;
}

// Required
if ($config['url'] === '') {
    return;
}

// Skip tracking if domain is empty
if ($config['domain'] === '') {
    return;
}

// Get bot detection signals
$botSignals = get_bot_signals($config['ip'], $config['user_agent']);

// Skip logging if no bot detected
if (empty($botSignals)) {
    return;
}

// Build log entry
$logData = [
    'int' => $config['is_internal'],
    'bot' => $botSignals,
];

// Only include category if set
if ($config['category'] !== null) {
    $logData['cat'] = $config['category'];
}

// Write to JSONL file: {data_root}/raw/{domain}/{date}/bots.jsonl
$dataRoot = $config['data_root'];
$domain   = $config['domain'];
$date     = $config['pageview_date'];

$dir = "{$dataRoot}/raw/{$domain}/{$date}";
if (!is_dir($dir) && !@mkdir($dir, 0755, true) && !is_dir($dir)) {
    // Directory creation failed, fail silently (tracking should not break page loads)
    return;
}

$logFile  = "{$dir}/bots.jsonl";
$logEntry = json_encode($logData, JSON_UNESCAPED_SLASHES) . "\n";

file_put_contents($logFile, $logEntry, FILE_APPEND | LOCK_EX);
