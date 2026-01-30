<?php

declare(strict_types=1);

namespace FOfX\Utility\PageviewTracking;

require_once __DIR__ . '/track_common.php';

try {
    $config = get_tracking_config();
} catch (\Throwable $e) {
    conditional_error_log('track_pageview.php get_tracking_config() error: ' . $e->getMessage());
    http_response_code(500);
    exit;
}

// Exit gracefully if tracking is disabled
if (!$config['tracking_enabled']) {
    exit;
}

// Exclude Check
if (is_excluded($config['ip'] ?? '', $config['user_agent'] ?? '')) {
    http_response_code(204);
    exit;
}

// Required
if ($config['type'] === '' || $config['view_id'] === '' || $config['url'] === '') {
    http_response_code(400);
    exit;
}
if ($config['type'] !== 'pageview' && $config['type'] !== 'metrics') {
    http_response_code(400);
    exit;
}

// Skip tracking if domain is empty
if ($config['domain'] === '') {
    http_response_code(204);
    exit;
}

// Write to JSONL Files
if ($config['type'] === 'pageview') {
    // Build pageview log entry
    // Normalized $config['domain'] is not included in the log entry, as it is part of the log file path
    $logData = [
        'vid'   => $config['view_id'],
        'url'   => $config['url'],
        'ref'   => $config['referrer'],
        'lang'  => $config['language'],
        'tz'    => $config['timezone'],
        'ua'    => $config['user_agent'],
        'vw'    => $config['viewport_width'],
        'vh'    => $config['viewport_height'],
        'ts_pv' => $config['ts_pageview_ms'],
        'ip'    => $config['ip'],
        'int'   => $config['is_internal'],
    ];

    // Write to pageview.jsonl
    $dataRoot = $config['data_root'];
    $domain   = $config['domain'];
    $date     = $config['pageview_date'];

    $dir = "{$dataRoot}/raw/{$domain}/{$date}";
    if (!is_dir($dir) && !@mkdir($dir, 0755, true) && !is_dir($dir)) {
        // Directory creation failed, fail silently (tracking should not break page loads)
        http_response_code(204);
        exit;
    }

    $logFile  = "{$dir}/pageview.jsonl";
    $logEntry = json_encode($logData, JSON_UNESCAPED_SLASHES) . "\n";

    file_put_contents($logFile, $logEntry, FILE_APPEND | LOCK_EX);

    http_response_code(204);
    exit;
} elseif ($config['type'] === 'metrics') {
    // Build metrics log entry
    $logData = [
        'vid'  => $config['view_id'],
        'ts_m' => $config['ts_metrics_ms'],
        'ttfb' => $config['ttfb_ms'],
        'dcl'  => $config['dcl_ms'],
        'load' => $config['load_ms'],
    ];

    // Write to metrics.jsonl
    $dataRoot = $config['data_root'];
    $domain   = $config['domain'];
    $date     = $config['pageview_date'];

    $dir = "{$dataRoot}/raw/{$domain}/{$date}";
    if (!is_dir($dir) && !@mkdir($dir, 0755, true) && !is_dir($dir)) {
        // Directory creation failed, fail silently (tracking should not break page loads)
        http_response_code(204);
        exit;
    }

    $logFile  = "{$dir}/metrics.jsonl";
    $logEntry = json_encode($logData, JSON_UNESCAPED_SLASHES) . "\n";

    file_put_contents($logFile, $logEntry, FILE_APPEND | LOCK_EX);

    http_response_code(204);
    exit;
}
