<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bot Verification Logs</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        h1 {
            color: #333;
            margin: 0;
        }
        .back-link {
            color: #007bff;
            text-decoration: none;
            font-size: 14px;
        }
        .back-link:hover {
            text-decoration: underline;
        }
        .table-container {
            overflow-x: auto;
            background: white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-top: 20px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }
        th, td {
            padding: 8px 6px;
            text-align: left;
            border-bottom: 1px solid #ddd;
            white-space: nowrap;
        }
        th {
            background: #007bff;
            color: white;
            font-weight: 600;
            font-size: 11px;
            position: sticky;
            top: 0;
        }
        th a {
            color: white;
            text-decoration: none;
            display: block;
        }
        th a:hover {
            text-decoration: underline;
        }
        .sort-indicator {
            margin-left: 4px;
        }
        tr:hover {
            background: #f8f9fa;
        }
        .totals-row {
            background: #e7f3ff !important;
            font-weight: 600;
        }
        .totals-row:hover {
            background: #d0e8ff !important;
        }
        a {
            color: #007bff;
            text-decoration: none;
        }
        a:hover {
            text-decoration: underline;
        }
        .number {
            text-align: right;
            font-variant-numeric: tabular-nums;
        }
        .error {
            background: #fff3cd;
            border: 1px solid #ffc107;
            padding: 15px;
            border-radius: 4px;
            color: #856404;
        }
        .unhealthy {
            color: #6c757d;
            font-size: 11px;
            font-weight: normal;
        }
    </style>
</head>
<body>

<?php
$logs_dir   = '/var/lib/pageview-tracking/logs';
$date       = $_GET['date'] ?? null;
$domain     = $_GET['domain'] ?? null;
$sort_by    = $_GET['sort'] ?? 'date';
$sort_order = $_GET['order'] ?? 'desc';

// Validate sort order
if (!in_array($sort_order, ['asc', 'desc'])) {
    $sort_order = 'desc';
}

// Helper function to generate sortable header
function sortable_header($label, $sort_key, $current_sort, $current_order, $base_params, $class = '')
{
    $new_order = ($current_sort === $sort_key && $current_order === 'asc') ? 'desc' : 'asc';
    $url       = '?' . ($base_params ? $base_params . '&' : '') . 'sort=' . urlencode($sort_key) . '&order=' . $new_order;
    $indicator = '';
    if ($current_sort === $sort_key) {
        $indicator = '<span class="sort-indicator">' . ($current_order === 'asc' ? '↑' : '↓') . '</span>';
    }
    $class_attr = $class ? ' class="' . $class . '"' : '';

    return "<th{$class_attr}><a href=\"{$url}\">{$label}{$indicator}</a></th>";
}

// Check if directory exists
if (!is_dir($logs_dir)) {
    echo '<h1>🤖 Bot Verification Logs</h1>';
    echo '<div class="error">Logs directory not found: ' . htmlspecialchars($logs_dir) . '</div>';
    echo '<p><a href="index.php">📊 Pageview Stats</a></p>';
    exit;
}

// Scan for JSON files
$files = glob($logs_dir . '/*.json');

if (empty($files)) {
    echo '<h1>🤖 Bot Verification Logs</h1>';
    echo '<div class="error">No log files found. Server logs have not been processed yet.</div>';
    echo '<p><a href="index.php">📊 Pageview Stats</a></p>';
    exit;
}

if ($domain) {
    // VIEW 3: Domain view - single domain across all dates
    echo '<div class="header">';
    echo '<h1>🤖 Bot Logs - ' . htmlspecialchars($domain) . '</h1>';
    echo '<a href="logs.php" class="back-link">← Back to Overview</a>';
    echo '</div>';

    // Parse all files and collect data for this domain
    $domain_data = [];
    $found       = false;

    foreach ($files as $file) {
        $date_str = basename($file, '.json');
        $data     = json_decode(file_get_contents($file), true);

        if (!$data || !isset($data['bots'][$domain])) {
            continue;
        }

        $found = true;
        $bots  = $data['bots'][$domain];

        $gb_home_h = $bots['googlebot']['homepage']['healthy'] ?? 0;
        $gb_home_u = $bots['googlebot']['homepage']['not_healthy'] ?? 0;
        $gb_int_h  = $bots['googlebot']['internal']['healthy'] ?? 0;
        $gb_int_u  = $bots['googlebot']['internal']['not_healthy'] ?? 0;
        $bb_home_h = $bots['bingbot']['homepage']['healthy'] ?? 0;
        $bb_home_u = $bots['bingbot']['homepage']['not_healthy'] ?? 0;
        $bb_int_h  = $bots['bingbot']['internal']['healthy'] ?? 0;
        $bb_int_u  = $bots['bingbot']['internal']['not_healthy'] ?? 0;

        $domain_data[] = [
            'date'      => $date_str,
            'gb_home_h' => $gb_home_h,
            'gb_home_u' => $gb_home_u,
            'gb_int_h'  => $gb_int_h,
            'gb_int_u'  => $gb_int_u,
            'bb_home_h' => $bb_home_h,
            'bb_home_u' => $bb_home_u,
            'bb_int_h'  => $bb_int_h,
            'bb_int_u'  => $bb_int_u,
        ];
    }

    if (!$found) {
        echo '<div class="error">No data found for domain: ' . htmlspecialchars($domain) . '</div>';
        exit;
    }

    // Validate sort key for domain view
    $valid_sorts_domain = ['date', 'gb_home', 'gb_internal', 'gb_total', 'bb_home', 'bb_internal', 'bb_total'];
    if (!in_array($sort_by, $valid_sorts_domain)) {
        $sort_by = 'date';
    }

    // Sort data
    usort($domain_data, function ($a, $b) use ($sort_by, $sort_order) {
        if ($sort_by === 'date') {
            $val_a = $a['date'];
            $val_b = $b['date'];
        } elseif ($sort_by === 'gb_home') {
            $val_a = $a['gb_home_h'] + $a['gb_home_u'];
            $val_b = $b['gb_home_h'] + $b['gb_home_u'];
        } elseif ($sort_by === 'gb_internal') {
            $val_a = $a['gb_int_h'] + $a['gb_int_u'];
            $val_b = $b['gb_int_h'] + $b['gb_int_u'];
        } elseif ($sort_by === 'gb_total') {
            $val_a = $a['gb_home_h'] + $a['gb_home_u'] + $a['gb_int_h'] + $a['gb_int_u'];
            $val_b = $b['gb_home_h'] + $b['gb_home_u'] + $b['gb_int_h'] + $b['gb_int_u'];
        } elseif ($sort_by === 'bb_home') {
            $val_a = $a['bb_home_h'] + $a['bb_home_u'];
            $val_b = $b['bb_home_h'] + $b['bb_home_u'];
        } elseif ($sort_by === 'bb_internal') {
            $val_a = $a['bb_int_h'] + $a['bb_int_u'];
            $val_b = $b['bb_int_h'] + $b['bb_int_u'];
        } elseif ($sort_by === 'bb_total') {
            $val_a = $a['bb_home_h'] + $a['bb_home_u'] + $a['bb_int_h'] + $a['bb_int_u'];
            $val_b = $b['bb_home_h'] + $b['bb_home_u'] + $b['bb_int_h'] + $b['bb_int_u'];
        } else {
            $val_a = $a['date'];
            $val_b = $b['date'];
        }

        $cmp = $val_a <=> $val_b;

        return $sort_order === 'desc' ? -$cmp : $cmp;
    });

    // Build base params for sort URLs
    $base_params = 'domain=' . urlencode($domain);

    echo '<div class="table-container">';
    echo '<table>';
    echo '<thead><tr>';
    echo sortable_header('Date', 'date', $sort_by, $sort_order, $base_params);
    echo sortable_header('GB Home', 'gb_home', $sort_by, $sort_order, $base_params, 'number');
    echo sortable_header('GB Internal', 'gb_internal', $sort_by, $sort_order, $base_params, 'number');
    echo sortable_header('GB Total', 'gb_total', $sort_by, $sort_order, $base_params, 'number');
    echo sortable_header('BB Home', 'bb_home', $sort_by, $sort_order, $base_params, 'number');
    echo sortable_header('BB Internal', 'bb_internal', $sort_by, $sort_order, $base_params, 'number');
    echo sortable_header('BB Total', 'bb_total', $sort_by, $sort_order, $base_params, 'number');
    echo '</tr></thead>';
    echo '<tbody>';

    foreach ($domain_data as $row) {
        echo '<tr>';
        echo '<td><a href="logs.php?date=' . urlencode($row['date']) . '">' . htmlspecialchars($row['date']) . '</a></td>';

        // Googlebot Home
        echo '<td class="number">' . number_format($row['gb_home_h']);
        if ($row['gb_home_u'] > 0) {
            echo ' <span class="unhealthy">+' . number_format($row['gb_home_u']) . '✗</span>';
        }
        echo '</td>';

        // Googlebot Internal
        echo '<td class="number">' . number_format($row['gb_int_h']);
        if ($row['gb_int_u'] > 0) {
            echo ' <span class="unhealthy">+' . number_format($row['gb_int_u']) . '✗</span>';
        }
        echo '</td>';

        // Googlebot Total
        $gb_total_h = $row['gb_home_h'] + $row['gb_int_h'];
        $gb_total_u = $row['gb_home_u'] + $row['gb_int_u'];
        echo '<td class="number">' . number_format($gb_total_h);
        if ($gb_total_u > 0) {
            echo ' <span class="unhealthy">+' . number_format($gb_total_u) . '✗</span>';
        }
        echo '</td>';

        // Bingbot Home
        echo '<td class="number">' . number_format($row['bb_home_h']);
        if ($row['bb_home_u'] > 0) {
            echo ' <span class="unhealthy">+' . number_format($row['bb_home_u']) . '✗</span>';
        }
        echo '</td>';

        // Bingbot Internal
        echo '<td class="number">' . number_format($row['bb_int_h']);
        if ($row['bb_int_u'] > 0) {
            echo ' <span class="unhealthy">+' . number_format($row['bb_int_u']) . '✗</span>';
        }
        echo '</td>';

        // Bingbot Total
        $bb_total_h = $row['bb_home_h'] + $row['bb_int_h'];
        $bb_total_u = $row['bb_home_u'] + $row['bb_int_u'];
        echo '<td class="number">' . number_format($bb_total_h);
        if ($bb_total_u > 0) {
            echo ' <span class="unhealthy">+' . number_format($bb_total_u) . '✗</span>';
        }
        echo '</td>';

        echo '</tr>';
    }

    echo '</tbody></table>';
    echo '</div>';

    echo '<p style="color: #666; margin-top: 20px; font-size: 13px;">';
    echo 'Bot verification logs for <strong>' . htmlspecialchars($domain) . '</strong> across all dates. ';
    echo 'Unhealthy requests <span class="unhealthy">+N✗</span> indicate non-200 status codes.';
    echo '<br><a href="index.php">📊 Pageview Stats</a>';
    echo '</p>';
} elseif ($date) {
    // VIEW 2: Detail view for specific date

    // Validate date format to prevent path traversal
    if (!preg_match('/^\d{4}-\d{2}-\d{2}$/', $date)) {
        echo '<div class="header">';
        echo '<h1>🤖 Bot Logs</h1>';
        echo '<a href="logs.php" class="back-link">← Back to Overview</a>';
        echo '</div>';
        echo '<div class="error">Invalid date format. Expected YYYY-MM-DD.</div>';
        exit;
    }

    $file = $logs_dir . '/' . $date . '.json';

    if (!file_exists($file)) {
        echo '<div class="header">';
        echo '<h1>🤖 Bot Logs - ' . htmlspecialchars($date) . '</h1>';
        echo '<a href="logs.php" class="back-link">← Back to Overview</a>';
        echo '</div>';
        echo '<div class="error">No data found for date: ' . htmlspecialchars($date) . '</div>';
        exit;
    }

    $data = json_decode(file_get_contents($file), true);

    if (!$data || !isset($data['bots'])) {
        echo '<div class="header">';
        echo '<h1>🤖 Bot Logs - ' . htmlspecialchars($date) . '</h1>';
        echo '<a href="logs.php" class="back-link">← Back to Overview</a>';
        echo '</div>';
        echo '<div class="error">Invalid data format in file</div>';
        exit;
    }

    // Display detail view
    echo '<div class="header">';
    echo '<h1>🤖 Bot Logs - ' . htmlspecialchars($date) . '</h1>';
    echo '<a href="logs.php" class="back-link">← Back to Overview</a>';
    echo '</div>';

    // Calculate totals
    $totals = [
        'gb_home_healthy'       => 0,
        'gb_home_unhealthy'     => 0,
        'gb_internal_healthy'   => 0,
        'gb_internal_unhealthy' => 0,
        'bb_home_healthy'       => 0,
        'bb_home_unhealthy'     => 0,
        'bb_internal_healthy'   => 0,
        'bb_internal_unhealthy' => 0,
    ];

    foreach ($data['bots'] as $domain => $bots) {
        if (isset($bots['googlebot'])) {
            $gb_h_h = $bots['googlebot']['homepage']['healthy'] ?? 0;
            $gb_h_u = $bots['googlebot']['homepage']['not_healthy'] ?? 0;
            $gb_i_h = $bots['googlebot']['internal']['healthy'] ?? 0;
            $gb_i_u = $bots['googlebot']['internal']['not_healthy'] ?? 0;

            $totals['gb_home_healthy'] += $gb_h_h;
            $totals['gb_home_unhealthy'] += $gb_h_u;
            $totals['gb_internal_healthy'] += $gb_i_h;
            $totals['gb_internal_unhealthy'] += $gb_i_u;
            $totals['gb_total_healthy'] += $gb_h_h + $gb_i_h;
            $totals['gb_total_unhealthy'] += $gb_h_u + $gb_i_u;
        }
        if (isset($bots['bingbot'])) {
            $bb_h_h = $bots['bingbot']['homepage']['healthy'] ?? 0;
            $bb_h_u = $bots['bingbot']['homepage']['not_healthy'] ?? 0;
            $bb_i_h = $bots['bingbot']['internal']['healthy'] ?? 0;
            $bb_i_u = $bots['bingbot']['internal']['not_healthy'] ?? 0;

            $totals['bb_home_healthy'] += $bb_h_h;
            $totals['bb_home_unhealthy'] += $bb_h_u;
            $totals['bb_internal_healthy'] += $bb_i_h;
            $totals['bb_internal_unhealthy'] += $bb_i_u;
            $totals['bb_total_healthy'] += $bb_h_h + $bb_i_h;
            $totals['bb_total_unhealthy'] += $bb_h_u + $bb_i_u;
        }
    }

    // Validate sort key for date view
    $valid_sorts_date = ['domain', 'gb_home', 'gb_internal', 'gb_total', 'bb_home', 'bb_internal', 'bb_total'];
    if (!in_array($sort_by, $valid_sorts_date)) {
        $sort_by = 'domain';
    }

    // Prepare domain data for sorting
    $domain_rows = [];
    foreach ($data['bots'] as $domain => $bots) {
        $gb_home_h = $bots['googlebot']['homepage']['healthy'] ?? 0;
        $gb_home_u = $bots['googlebot']['homepage']['not_healthy'] ?? 0;
        $gb_int_h  = $bots['googlebot']['internal']['healthy'] ?? 0;
        $gb_int_u  = $bots['googlebot']['internal']['not_healthy'] ?? 0;
        $bb_home_h = $bots['bingbot']['homepage']['healthy'] ?? 0;
        $bb_home_u = $bots['bingbot']['homepage']['not_healthy'] ?? 0;
        $bb_int_h  = $bots['bingbot']['internal']['healthy'] ?? 0;
        $bb_int_u  = $bots['bingbot']['internal']['not_healthy'] ?? 0;

        $domain_rows[] = [
            'domain'    => $domain,
            'bots'      => $bots,
            'gb_home_h' => $gb_home_h,
            'gb_home_u' => $gb_home_u,
            'gb_int_h'  => $gb_int_h,
            'gb_int_u'  => $gb_int_u,
            'bb_home_h' => $bb_home_h,
            'bb_home_u' => $bb_home_u,
            'bb_int_h'  => $bb_int_h,
            'bb_int_u'  => $bb_int_u,
        ];
    }

    // Sort domain rows
    usort($domain_rows, function ($a, $b) use ($sort_by, $sort_order) {
        if ($sort_by === 'domain') {
            $val_a = $a['domain'];
            $val_b = $b['domain'];
        } elseif ($sort_by === 'gb_home') {
            $val_a = $a['gb_home_h'] + $a['gb_home_u'];
            $val_b = $b['gb_home_h'] + $b['gb_home_u'];
        } elseif ($sort_by === 'gb_internal') {
            $val_a = $a['gb_int_h'] + $a['gb_int_u'];
            $val_b = $b['gb_int_h'] + $b['gb_int_u'];
        } elseif ($sort_by === 'gb_total') {
            $val_a = $a['gb_home_h'] + $a['gb_home_u'] + $a['gb_int_h'] + $a['gb_int_u'];
            $val_b = $b['gb_home_h'] + $b['gb_home_u'] + $b['gb_int_h'] + $b['gb_int_u'];
        } elseif ($sort_by === 'bb_home') {
            $val_a = $a['bb_home_h'] + $a['bb_home_u'];
            $val_b = $b['bb_home_h'] + $b['bb_home_u'];
        } elseif ($sort_by === 'bb_internal') {
            $val_a = $a['bb_int_h'] + $a['bb_int_u'];
            $val_b = $b['bb_int_h'] + $b['bb_int_u'];
        } elseif ($sort_by === 'bb_total') {
            $val_a = $a['bb_home_h'] + $a['bb_home_u'] + $a['bb_int_h'] + $a['bb_int_u'];
            $val_b = $b['bb_home_h'] + $b['bb_home_u'] + $b['bb_int_h'] + $b['bb_int_u'];
        } else {
            $val_a = $a['domain'];
            $val_b = $b['domain'];
        }

        $cmp = $val_a <=> $val_b;

        return $sort_order === 'desc' ? -$cmp : $cmp;
    });

    // Build base params for sort URLs
    $base_params = 'date=' . urlencode($date);

    echo '<div class="table-container">';
    echo '<table>';
    echo '<thead><tr>';
    echo sortable_header('Domain', 'domain', $sort_by, $sort_order, $base_params);
    echo sortable_header('GB Home', 'gb_home', $sort_by, $sort_order, $base_params, 'number');
    echo sortable_header('GB Internal', 'gb_internal', $sort_by, $sort_order, $base_params, 'number');
    echo sortable_header('GB Total', 'gb_total', $sort_by, $sort_order, $base_params, 'number');
    echo sortable_header('BB Home', 'bb_home', $sort_by, $sort_order, $base_params, 'number');
    echo sortable_header('BB Internal', 'bb_internal', $sort_by, $sort_order, $base_params, 'number');
    echo sortable_header('BB Total', 'bb_total', $sort_by, $sort_order, $base_params, 'number');
    echo '</tr></thead>';
    echo '<tbody>';

    foreach ($domain_rows as $row) {
        $domain = $row['domain'];
        $bots   = $row['bots'];

        echo '<tr>';
        echo '<td><a href="logs.php?domain=' . urlencode($domain) . '">' . htmlspecialchars($domain) . '</a></td>';

        // Googlebot Home
        $gb_home_h = $bots['googlebot']['homepage']['healthy'] ?? 0;
        $gb_home_u = $bots['googlebot']['homepage']['not_healthy'] ?? 0;
        echo '<td class="number">' . $gb_home_h;
        if ($gb_home_u > 0) {
            echo ' <span class="unhealthy">+' . $gb_home_u . '✗</span>';
        }
        echo '</td>';

        // Googlebot Internal
        $gb_int_h = $bots['googlebot']['internal']['healthy'] ?? 0;
        $gb_int_u = $bots['googlebot']['internal']['not_healthy'] ?? 0;
        echo '<td class="number">' . $gb_int_h;
        if ($gb_int_u > 0) {
            echo ' <span class="unhealthy">+' . $gb_int_u . '✗</span>';
        }
        echo '</td>';

        // Googlebot Total
        $gb_total_h = $gb_home_h + $gb_int_h;
        $gb_total_u = $gb_home_u + $gb_int_u;
        echo '<td class="number">' . $gb_total_h;
        if ($gb_total_u > 0) {
            echo ' <span class="unhealthy">+' . $gb_total_u . '✗</span>';
        }
        echo '</td>';

        // Bingbot Home
        $bb_home_h = $bots['bingbot']['homepage']['healthy'] ?? 0;
        $bb_home_u = $bots['bingbot']['homepage']['not_healthy'] ?? 0;
        echo '<td class="number">' . $bb_home_h;
        if ($bb_home_u > 0) {
            echo ' <span class="unhealthy">+' . $bb_home_u . '✗</span>';
        }
        echo '</td>';

        // Bingbot Internal
        $bb_int_h = $bots['bingbot']['internal']['healthy'] ?? 0;
        $bb_int_u = $bots['bingbot']['internal']['not_healthy'] ?? 0;
        echo '<td class="number">' . $bb_int_h;
        if ($bb_int_u > 0) {
            echo ' <span class="unhealthy">+' . $bb_int_u . '✗</span>';
        }
        echo '</td>';

        // Bingbot Total
        $bb_total_h = $bb_home_h + $bb_int_h;
        $bb_total_u = $bb_home_u + $bb_int_u;
        echo '<td class="number">' . $bb_total_h;
        if ($bb_total_u > 0) {
            echo ' <span class="unhealthy">+' . $bb_total_u . '✗</span>';
        }
        echo '</td>';

        echo '</tr>';
    }

    // Totals row
    echo '<tr class="totals-row">';
    echo '<td><strong>TOTAL</strong></td>';
    echo '<td class="number"><strong>' . $totals['gb_home_healthy'];
    if ($totals['gb_home_unhealthy'] > 0) {
        echo ' <span class="unhealthy">+' . $totals['gb_home_unhealthy'] . '✗</span>';
    }
    echo '</strong></td>';
    echo '<td class="number"><strong>' . $totals['gb_internal_healthy'];
    if ($totals['gb_internal_unhealthy'] > 0) {
        echo ' <span class="unhealthy">+' . $totals['gb_internal_unhealthy'] . '✗</span>';
    }
    echo '</strong></td>';
    echo '<td class="number"><strong>' . $totals['gb_total_healthy'];
    if ($totals['gb_total_unhealthy'] > 0) {
        echo ' <span class="unhealthy">+' . $totals['gb_total_unhealthy'] . '✗</span>';
    }
    echo '</strong></td>';
    echo '<td class="number"><strong>' . $totals['bb_home_healthy'];
    if ($totals['bb_home_unhealthy'] > 0) {
        echo ' <span class="unhealthy">+' . $totals['bb_home_unhealthy'] . '✗</span>';
    }
    echo '</strong></td>';
    echo '<td class="number"><strong>' . $totals['bb_internal_healthy'];
    if ($totals['bb_internal_unhealthy'] > 0) {
        echo ' <span class="unhealthy">+' . $totals['bb_internal_unhealthy'] . '✗</span>';
    }
    echo '</strong></td>';
    echo '<td class="number"><strong>' . $totals['bb_total_healthy'];
    if ($totals['bb_total_unhealthy'] > 0) {
        echo ' <span class="unhealthy">+' . $totals['bb_total_unhealthy'] . '✗</span>';
    }
    echo '</strong></td>';
    echo '</tr>';

    echo '</tbody></table>';
    echo '</div>';

    echo '<p style="color: #666; margin-top: 20px; font-size: 13px;">';
    echo 'Verified bot requests (User Agent + IP match). ';
    echo 'Unhealthy requests <span class="unhealthy">+N✗</span> indicate non-200 status codes.';
    echo '<br><a href="index.php">📊 Pageview Stats</a>';
    echo '</p>';
} else {
    // VIEW 1: Overview of all dates
    echo '<h1>🤖 Bot Verification Logs</h1>';

    // Parse all files and aggregate
    $dates_data = [];

    foreach ($files as $file) {
        $date_str = basename($file, '.json');
        $data     = json_decode(file_get_contents($file), true);

        if (!$data || !isset($data['bots'])) {
            continue;
        }

        $domain_count = count($data['bots']);
        $gb_home_h    = 0;
        $gb_home_u    = 0;
        $gb_int_h     = 0;
        $gb_int_u     = 0;
        $bb_home_h    = 0;
        $bb_home_u    = 0;
        $bb_int_h     = 0;
        $bb_int_u     = 0;

        foreach ($data['bots'] as $domain => $bots) {
            if (isset($bots['googlebot'])) {
                $gb_home_h += ($bots['googlebot']['homepage']['healthy'] ?? 0);
                $gb_home_u += ($bots['googlebot']['homepage']['not_healthy'] ?? 0);
                $gb_int_h += ($bots['googlebot']['internal']['healthy'] ?? 0);
                $gb_int_u += ($bots['googlebot']['internal']['not_healthy'] ?? 0);
            }
            if (isset($bots['bingbot'])) {
                $bb_home_h += ($bots['bingbot']['homepage']['healthy'] ?? 0);
                $bb_home_u += ($bots['bingbot']['homepage']['not_healthy'] ?? 0);
                $bb_int_h += ($bots['bingbot']['internal']['healthy'] ?? 0);
                $bb_int_u += ($bots['bingbot']['internal']['not_healthy'] ?? 0);
            }
        }

        $dates_data[] = [
            'date'      => $date_str,
            'domains'   => $domain_count,
            'gb_home_h' => $gb_home_h,
            'gb_home_u' => $gb_home_u,
            'gb_int_h'  => $gb_int_h,
            'gb_int_u'  => $gb_int_u,
            'bb_home_h' => $bb_home_h,
            'bb_home_u' => $bb_home_u,
            'bb_int_h'  => $bb_int_h,
            'bb_int_u'  => $bb_int_u,
        ];
    }

    // Validate sort key for overview
    $valid_sorts_overview = ['date', 'domains', 'gb_home', 'gb_internal', 'gb_total', 'bb_home', 'bb_internal', 'bb_total'];
    if (!in_array($sort_by, $valid_sorts_overview)) {
        $sort_by = 'date';
    }

    // Sort data
    usort($dates_data, function ($a, $b) use ($sort_by, $sort_order) {
        if ($sort_by === 'date') {
            $val_a = $a['date'];
            $val_b = $b['date'];
        } elseif ($sort_by === 'domains') {
            $val_a = $a['domains'];
            $val_b = $b['domains'];
        } elseif ($sort_by === 'gb_home') {
            $val_a = $a['gb_home_h'] + $a['gb_home_u'];
            $val_b = $b['gb_home_h'] + $b['gb_home_u'];
        } elseif ($sort_by === 'gb_internal') {
            $val_a = $a['gb_int_h'] + $a['gb_int_u'];
            $val_b = $b['gb_int_h'] + $b['gb_int_u'];
        } elseif ($sort_by === 'gb_total') {
            $val_a = $a['gb_home_h'] + $a['gb_home_u'] + $a['gb_int_h'] + $a['gb_int_u'];
            $val_b = $b['gb_home_h'] + $b['gb_home_u'] + $b['gb_int_h'] + $b['gb_int_u'];
        } elseif ($sort_by === 'bb_home') {
            $val_a = $a['bb_home_h'] + $a['bb_home_u'];
            $val_b = $b['bb_home_h'] + $b['bb_home_u'];
        } elseif ($sort_by === 'bb_internal') {
            $val_a = $a['bb_int_h'] + $a['bb_int_u'];
            $val_b = $b['bb_int_h'] + $b['bb_int_u'];
        } elseif ($sort_by === 'bb_total') {
            $val_a = $a['bb_home_h'] + $a['bb_home_u'] + $a['bb_int_h'] + $a['bb_int_u'];
            $val_b = $b['bb_home_h'] + $b['bb_home_u'] + $b['bb_int_h'] + $b['bb_int_u'];
        } else {
            $val_a = $a['date'];
            $val_b = $b['date'];
        }

        $cmp = $val_a <=> $val_b;

        return $sort_order === 'desc' ? -$cmp : $cmp;
    });

    // Build base params for sort URLs (empty for overview)
    $base_params = '';

    echo '<div class="table-container">';
    echo '<table>';
    echo '<thead><tr>';
    echo sortable_header('Date', 'date', $sort_by, $sort_order, $base_params);
    echo sortable_header('Domains', 'domains', $sort_by, $sort_order, $base_params, 'number');
    echo sortable_header('GB Home', 'gb_home', $sort_by, $sort_order, $base_params, 'number');
    echo sortable_header('GB Internal', 'gb_internal', $sort_by, $sort_order, $base_params, 'number');
    echo sortable_header('GB Total', 'gb_total', $sort_by, $sort_order, $base_params, 'number');
    echo sortable_header('BB Home', 'bb_home', $sort_by, $sort_order, $base_params, 'number');
    echo sortable_header('BB Internal', 'bb_internal', $sort_by, $sort_order, $base_params, 'number');
    echo sortable_header('BB Total', 'bb_total', $sort_by, $sort_order, $base_params, 'number');
    echo '</tr></thead>';
    echo '<tbody>';

    foreach ($dates_data as $row) {
        echo '<tr>';
        echo '<td><a href="logs.php?date=' . urlencode($row['date']) . '">' . htmlspecialchars($row['date']) . '</a></td>';
        echo '<td class="number">' . number_format($row['domains']) . '</td>';

        // Googlebot Home
        echo '<td class="number">' . number_format($row['gb_home_h']);
        if ($row['gb_home_u'] > 0) {
            echo ' <span class="unhealthy">+' . number_format($row['gb_home_u']) . '✗</span>';
        }
        echo '</td>';

        // Googlebot Internal
        echo '<td class="number">' . number_format($row['gb_int_h']);
        if ($row['gb_int_u'] > 0) {
            echo ' <span class="unhealthy">+' . number_format($row['gb_int_u']) . '✗</span>';
        }
        echo '</td>';

        // Googlebot Total
        $gb_total_h = $row['gb_home_h'] + $row['gb_int_h'];
        $gb_total_u = $row['gb_home_u'] + $row['gb_int_u'];
        echo '<td class="number">' . number_format($gb_total_h);
        if ($gb_total_u > 0) {
            echo ' <span class="unhealthy">+' . number_format($gb_total_u) . '✗</span>';
        }
        echo '</td>';

        // Bingbot Home
        echo '<td class="number">' . number_format($row['bb_home_h']);
        if ($row['bb_home_u'] > 0) {
            echo ' <span class="unhealthy">+' . number_format($row['bb_home_u']) . '✗</span>';
        }
        echo '</td>';

        // Bingbot Internal
        echo '<td class="number">' . number_format($row['bb_int_h']);
        if ($row['bb_int_u'] > 0) {
            echo ' <span class="unhealthy">+' . number_format($row['bb_int_u']) . '✗</span>';
        }
        echo '</td>';

        // Bingbot Total
        $bb_total_h = $row['bb_home_h'] + $row['bb_int_h'];
        $bb_total_u = $row['bb_home_u'] + $row['bb_int_u'];
        echo '<td class="number">' . number_format($bb_total_h);
        if ($bb_total_u > 0) {
            echo ' <span class="unhealthy">+' . number_format($bb_total_u) . '✗</span>';
        }
        echo '</td>';

        echo '</tr>';
    }

    echo '</tbody></table>';
    echo '</div>';

    echo '<p style="color: #666; margin-top: 20px; font-size: 13px;">';
    echo 'Click a date to view per-domain bot verification details. ';
    echo 'Counts include all verified bot requests (User Agent + IP match).';
    echo '<br><a href="index.php">📊 Pageview Stats</a>';
    echo '</p>';
}
?>

</body>
</html>

