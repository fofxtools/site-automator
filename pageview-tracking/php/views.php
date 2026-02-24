<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Individual Pageviews</title>
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
        .info-bar {
            background: white;
            padding: 15px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            border-radius: 4px;
        }
        .table-container {
            overflow-x: auto;
            background: white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
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
        .number {
            text-align: right;
            font-variant-numeric: tabular-nums;
        }
        .url-cell {
            max-width: 300px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .pagination {
            margin-top: 20px;
            text-align: center;
            padding: 15px;
            background: white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .pagination a {
            color: #007bff;
            text-decoration: none;
            padding: 8px 12px;
            margin: 0 5px;
            border: 1px solid #007bff;
            border-radius: 4px;
        }
        .pagination a:hover {
            background: #007bff;
            color: white;
        }
        .pagination a.disabled {
            color: #ccc;
            border-color: #ccc;
            pointer-events: none;
        }
        .error {
            background: #fff3cd;
            border: 1px solid #ffc107;
            padding: 15px;
            border-radius: 4px;
            color: #856404;
        }
    </style>
</head>
<body>

<?php
$raw_dir = '/var/lib/pageview-tracking/raw';

// Helper function to check if a pageview is qualified
function is_pageview_qualified($row, $engagement)
{
    $e = $engagement[$row['vid'] ?? ''] ?? null;
    if (!$e) {
        return false;
    }

    $time_on_page  = $e['t_pg'] ?? 0;
    $scroll_depth  = $e['scr_d'] ?? 0;
    $scroll_events = $e['scr_e'] ?? 0;
    $vw            = $row['vw'] ?? 0;
    $vh            = $row['vh'] ?? 0;

    if ($vw == 800 && $vh == 600) {
        return false;
    } elseif ($time_on_page < 5000) {
        return false;
    } elseif ($scroll_events / ($time_on_page / 1000) > 10) {
        // Unreasonable human scroll speed
        return false;
    } elseif ($scroll_depth == 100 && $scroll_events <= 2) {
        // Classic scripted scroll bot pattern
        return false;
    } elseif ($scroll_events >= 2) {
        // Otherwise: basic engagement = qualified
        return true;
    } else {
        return false;
    }
}

// Get parameters
$date           = $_GET['date'] ?? '';
$domain         = $_GET['domain'] ?? '';
$page           = max(1, (int)($_GET['page'] ?? 1));
$perPage        = 100;
$qualified_only = isset($_GET['qualified']);
$sort_by        = $_GET['sort'] ?? 'ts_pv';
$sort_order     = $_GET['order'] ?? 'asc';

// Validate sort parameters
$valid_sorts = ['ts_pv', 'ttfb', 'dcl', 'load', 't_pg', 'scr_d', 'scr_e', 'qualified', 'url', 'ref', 'ip', 'ua', 'lang', 'tz', 'vw', 'vh', 'domain'];
if (!in_array($sort_by, $valid_sorts)) {
    $sort_by = 'ts_pv';
}
if (!in_array($sort_order, ['asc', 'desc'])) {
    $sort_order = 'asc';
}

// Validate date format
if (!preg_match('/^\d{4}-\d{2}-\d{2}$/', $date)) {
    echo '<div class="error">Invalid date format. Expected YYYY-MM-DD.</div>';
    echo '<p><a href="index.php" class="back-link">← Back to dates</a></p>';
    exit;
}

// Build file list
if ($domain) {
    $files = [$raw_dir . '/' . $domain . '/' . $date . '/pageview.jsonl'];
} else {
    $files = glob($raw_dir . '/*/' . $date . '/pageview.jsonl');
}

if (empty($files)) {
    echo '<div class="error">No pageview data found for date: ' . htmlspecialchars($date) . '</div>';
    echo '<p><a href="day.php?date=' . htmlspecialchars($date) . '" class="back-link">← Back to daily stats</a></p>';
    exit;
}

// Load all pageviews into buffer (needed for sorting)
$offset = ($page - 1) * $perPage;
$buffer = [];

foreach ($files as $file) {
    if (!file_exists($file)) {
        continue;
    }

    // Extract domain from file path if viewing all domains
    if (!$domain && preg_match('#/raw/([^/]+)/#', $file, $matches)) {
        $fileDomain = $matches[1];
    } else {
        $fileDomain = $domain ?: 'unknown';
    }

    $handle = fopen($file, 'r');
    while (($line = fgets($handle)) !== false) {
        $row = json_decode($line, true);
        if ($row && isset($row['ts_pv'])) {
            if (!$domain) {
                $row['domain'] = $fileDomain; // Add domain to row for all-domains view
            }
            $buffer[] = $row;
        }
    }
    fclose($handle);
}

// Load all metrics for sorting
$metrics = [];
if ($domain) {
    $metricsFile = $raw_dir . '/' . $domain . '/' . $date . '/metrics.jsonl';
    if (file_exists($metricsFile)) {
        $handle = fopen($metricsFile, 'r');
        while (($line = fgets($handle)) !== false) {
            $m = json_decode($line, true);
            if ($m && isset($m['vid'])) {
                $metrics[$m['vid']] = $m;
            }
        }
        fclose($handle);
    }
} else {
    foreach (glob($raw_dir . '/*/' . $date . '/metrics.jsonl') as $metricsFile) {
        $handle = fopen($metricsFile, 'r');
        while (($line = fgets($handle)) !== false) {
            $m = json_decode($line, true);
            if ($m && isset($m['vid'])) {
                $metrics[$m['vid']] = $m;
            }
        }
        fclose($handle);
    }
}

// Load all engagement for sorting
$engagement = [];
if ($domain) {
    $engagementFile = $raw_dir . '/' . $domain . '/' . $date . '/engagement.jsonl';
    if (file_exists($engagementFile)) {
        $handle = fopen($engagementFile, 'r');
        while (($line = fgets($handle)) !== false) {
            $e = json_decode($line, true);
            if ($e && isset($e['vid'])) {
                $engagement[$e['vid']] = $e;
            }
        }
        fclose($handle);
    }
} else {
    foreach (glob($raw_dir . '/*/' . $date . '/engagement.jsonl') as $engagementFile) {
        $handle = fopen($engagementFile, 'r');
        while (($line = fgets($handle)) !== false) {
            $e = json_decode($line, true);
            if ($e && isset($e['vid'])) {
                $engagement[$e['vid']] = $e;
            }
        }
        fclose($handle);
    }
}

// Sort buffer before pagination
usort($buffer, function ($a, $b) use ($sort_by, $sort_order, $metrics, $engagement) {
    // Numeric sorts
    if ($sort_by === 'ts_pv') {
        $val_a = $a['ts_pv'] ?? 0;
        $val_b = $b['ts_pv'] ?? 0;
    } elseif ($sort_by === 'ttfb') {
        $val_a = $metrics[$a['vid'] ?? '']['ttfb'] ?? 0;
        $val_b = $metrics[$b['vid'] ?? '']['ttfb'] ?? 0;
    } elseif ($sort_by === 'dcl') {
        $val_a = $metrics[$a['vid'] ?? '']['dcl'] ?? 0;
        $val_b = $metrics[$b['vid'] ?? '']['dcl'] ?? 0;
    } elseif ($sort_by === 'load') {
        $val_a = $metrics[$a['vid'] ?? '']['load'] ?? 0;
        $val_b = $metrics[$b['vid'] ?? '']['load'] ?? 0;
    } elseif ($sort_by === 't_pg') {
        $val_a = $engagement[$a['vid'] ?? '']['t_pg'] ?? 0;
        $val_b = $engagement[$b['vid'] ?? '']['t_pg'] ?? 0;
    } elseif ($sort_by === 'scr_d') {
        $val_a = $engagement[$a['vid'] ?? '']['scr_d'] ?? 0;
        $val_b = $engagement[$b['vid'] ?? '']['scr_d'] ?? 0;
    } elseif ($sort_by === 'scr_e') {
        $val_a = $engagement[$a['vid'] ?? '']['scr_e'] ?? 0;
        $val_b = $engagement[$b['vid'] ?? '']['scr_e'] ?? 0;
    } elseif ($sort_by === 'vw') {
        $val_a = $a['vw'] ?? 0;
        $val_b = $b['vw'] ?? 0;
    } elseif ($sort_by === 'vh') {
        $val_a = $a['vh'] ?? 0;
        $val_b = $b['vh'] ?? 0;
    } elseif ($sort_by === 'qualified') {
        // Use helper function to calculate qualified status
        $val_a = is_pageview_qualified($a, $engagement) ? 1 : 0;
        $val_b = is_pageview_qualified($b, $engagement) ? 1 : 0;
        // String sorts
    } elseif ($sort_by === 'url') {
        $val_a = $a['url'] ?? '';
        $val_b = $b['url'] ?? '';
    } elseif ($sort_by === 'ref') {
        $val_a = $a['ref'] ?? '';
        $val_b = $b['ref'] ?? '';
    } elseif ($sort_by === 'ip') {
        $val_a = $a['ip'] ?? '';
        $val_b = $b['ip'] ?? '';
    } elseif ($sort_by === 'ua') {
        $val_a = $a['ua'] ?? '';
        $val_b = $b['ua'] ?? '';
    } elseif ($sort_by === 'lang') {
        $val_a = $a['lang'] ?? '';
        $val_b = $b['lang'] ?? '';
    } elseif ($sort_by === 'tz') {
        $val_a = $a['tz'] ?? '';
        $val_b = $b['tz'] ?? '';
    } elseif ($sort_by === 'domain') {
        $val_a = $a['domain'] ?? '';
        $val_b = $b['domain'] ?? '';
    } else {
        $val_a = 0;
        $val_b = 0;
    }

    $cmp = $val_a <=> $val_b;

    return $sort_order === 'desc' ? -$cmp : $cmp;
});

// Filter for qualified pageviews BEFORE pagination (if requested)
if ($qualified_only) {
    $buffer = array_filter($buffer, function ($row) use ($engagement) {
        return is_pageview_qualified($row, $engagement);
    });
    // Re-index array after filtering
    $buffer = array_values($buffer);
}

// Count qualified pageviews for info display
if ($qualified_only) {
    // In qualified-only mode, all rows in buffer are qualified
    $qualified_count = count($buffer);
} else {
    // Count qualified rows in the full buffer
    $qualified_count = 0;
    foreach ($buffer as $row) {
        if (is_pageview_qualified($row, $engagement)) {
            $qualified_count++;
        }
    }
}

// Paginate AFTER filtering
$total   = count($buffer);
$results = array_slice($buffer, $offset, $perPage);
$hasNext = $offset + $perPage < $total;
$hasPrev = $page > 1;

// Build back URL
$backUrl = 'day.php?date=' . urlencode($date);

// Page title
$pageTitle = '📄 Individual Pageviews';
if ($qualified_only) {
    $pageTitle = '📄 Qualified Pageviews';
}
if ($domain) {
    $pageTitle .= ' (' . htmlspecialchars($domain) . ')';
}
?>

    <div class="header">
        <h1><?= $pageTitle ?></h1>
        <a href="<?= $backUrl ?>" class="back-link">← Back to daily stats</a>
    </div>

    <div class="info-bar">
        <strong>Date:</strong> <?= htmlspecialchars($date) ?>
        <?php if ($domain): ?>
            | <strong>Domain:</strong> <?= htmlspecialchars($domain) ?>
        <?php else: ?>
            | <strong>All Domains</strong>
        <?php endif; ?>
        | <strong>Page:</strong> <?= $page ?>
        | <strong>Showing:</strong> <?= count($results) ?> pageviews
        <?php if ($qualified_only): ?>
            | <strong>Filter:</strong> Qualified Only
        <?php else: ?>
            | <strong>Qualified:</strong> <?= $qualified_count ?> of <?= $total ?>
        <?php endif; ?>
    </div>

    <div class="table-container">
        <table>
            <thead>
                <tr>
<?php
// Helper function to generate sortable header
function sortable_header($label, $sort_key, $current_sort, $current_order, $base_params, $class = '')
{
    $new_order = ($current_sort === $sort_key && $current_order === 'asc') ? 'desc' : 'asc';
    $url       = '?' . $base_params . '&sort=' . urlencode($sort_key) . '&order=' . $new_order;
    $indicator = '';
    if ($current_sort === $sort_key) {
        $indicator = '<span class="sort-indicator">' . ($current_order === 'asc' ? '↑' : '↓') . '</span>';
    }
    $class_attr = $class ? ' class="' . $class . '"' : '';

    return "<th{$class_attr}><a href=\"{$url}\">{$label}{$indicator}</a></th>";
}

// Build base params for sort URLs (no page parameter - always reset to page 1)
$base_params = 'date=' . urlencode($date);
if ($domain) {
    $base_params .= '&domain=' . urlencode($domain);
}
if ($qualified_only) {
    $base_params .= '&qualified=1';
}

echo sortable_header('Time (UTC)', 'ts_pv', $sort_by, $sort_order, $base_params);
if (!$domain) {
    echo sortable_header('Domain', 'domain', $sort_by, $sort_order, $base_params);
}
echo sortable_header('URL', 'url', $sort_by, $sort_order, $base_params);
echo sortable_header('Referrer', 'ref', $sort_by, $sort_order, $base_params);
echo sortable_header('IP', 'ip', $sort_by, $sort_order, $base_params);
echo sortable_header('User Agent', 'ua', $sort_by, $sort_order, $base_params);
echo sortable_header('Lang', 'lang', $sort_by, $sort_order, $base_params);
echo sortable_header('TZ', 'tz', $sort_by, $sort_order, $base_params);
echo sortable_header('VW', 'vw', $sort_by, $sort_order, $base_params, 'number');
echo sortable_header('VH', 'vh', $sort_by, $sort_order, $base_params, 'number');
echo sortable_header('TTFB', 'ttfb', $sort_by, $sort_order, $base_params, 'number');
echo sortable_header('DCL', 'dcl', $sort_by, $sort_order, $base_params, 'number');
echo sortable_header('Load', 'load', $sort_by, $sort_order, $base_params, 'number');
echo sortable_header('Time on Page', 't_pg', $sort_by, $sort_order, $base_params, 'number');
echo sortable_header('Scroll (%)', 'scr_d', $sort_by, $sort_order, $base_params, 'number');
echo sortable_header('Scroll Events', 'scr_e', $sort_by, $sort_order, $base_params, 'number');
echo sortable_header('Qualified', 'qualified', $sort_by, $sort_order, $base_params);
?>
                </tr>
            </thead>
            <tbody>
<?php foreach ($results as $row):
    $m = $metrics[$row['vid'] ?? ''] ?? null;
    $e = $engagement[$row['vid'] ?? ''] ?? null;

    // Extract engagement data
    $time_on_page  = $e ? ($e['t_pg'] ?? 0) : 0;
    $scroll_depth  = $e ? ($e['scr_d'] ?? 0) : 0;
    $scroll_events = $e ? ($e['scr_e'] ?? 0) : 0;

    // Check if qualified using helper function
    $is_qualified = is_pageview_qualified($row, $engagement);
    ?>
                <tr>
                    <td><?= isset($row['ts_pv']) ? date('H:i:s', $row['ts_pv'] / 1000) : '-' ?></td>
<?php if (!$domain): ?>
                    <td><?= htmlspecialchars($row['domain'] ?? '-') ?></td>
<?php endif; ?>
                    <td class="url-cell" title="<?= htmlspecialchars($row['url'] ?? '') ?>">
                        <?= htmlspecialchars($row['url'] ?? '-') ?>
                    </td>
                    <td class="url-cell" title="<?= htmlspecialchars($row['ref'] ?? '') ?>">
                        <?= htmlspecialchars($row['ref'] ?? '-') ?>
                    </td>
                    <td><?= htmlspecialchars($row['ip'] ?? '-') ?></td>
                    <td class="url-cell" title="<?= htmlspecialchars($row['ua'] ?? '') ?>">
                        <?= htmlspecialchars(substr($row['ua'] ?? '-', 0, 50)) ?><?= strlen($row['ua'] ?? '') > 50 ? '...' : '' ?>
                    </td>
                    <td><?= htmlspecialchars($row['lang'] ?? '-') ?></td>
                    <td><?= htmlspecialchars($row['tz'] ?? '-') ?></td>
                    <td class="number"><?= $row['vw'] ?? '-' ?></td>
                    <td class="number"><?= $row['vh'] ?? '-' ?></td>
                    <td class="number"><?= $m && isset($m['ttfb']) ? number_format($m['ttfb'], 1) : '-' ?></td>
                    <td class="number"><?= $m && isset($m['dcl']) ? number_format($m['dcl'], 1) : '-' ?></td>
                    <td class="number"><?= $m && isset($m['load']) ? number_format($m['load'], 1) : '-' ?></td>
                    <td class="number"><?= $time_on_page > 0 ? number_format($time_on_page, 1) : '-' ?></td>
                    <td class="number"><?= $scroll_depth > 0 ? number_format($scroll_depth, 1) : '-' ?></td>
                    <td class="number"><?= $scroll_events > 0 ? $scroll_events : '-' ?></td>
                    <td><?= $e ? ($is_qualified ? 'Y' : 'N') : '-' ?></td>
                </tr>
<?php endforeach; ?>
            </tbody>
        </table>
    </div>

    <div class="pagination">
<?php
    $baseUrl = '?date=' . urlencode($date) . ($domain ? '&domain=' . urlencode($domain) : '');
if ($qualified_only) {
    $baseUrl .= '&qualified=1';
}
if ($sort_by !== 'ts_pv') {
    $baseUrl .= '&sort=' . urlencode($sort_by);
}
if ($sort_order !== 'asc') {
    $baseUrl .= '&order=' . urlencode($sort_order);
}
$firstUrl = $baseUrl . '&page=1';
$prevUrl  = $baseUrl . '&page=' . ($page - 1);
$nextUrl  = $baseUrl . '&page=' . ($page + 1);
?>
        <a href="<?= $firstUrl ?>" class="<?= $hasPrev ? '' : 'disabled' ?>">⏮ First</a>
        <a href="<?= $prevUrl ?>" class="<?= $hasPrev ? '' : 'disabled' ?>">← Previous</a>
        <span style="margin: 0 15px;">Page <?= $page ?></span>
        <a href="<?= $nextUrl ?>" class="<?= $hasNext ? '' : 'disabled' ?>">Next →</a>
    </div>

</body>
</html>

