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

// Get parameters
$date    = $_GET['date'] ?? '';
$domain  = $_GET['domain'] ?? '';
$page    = max(1, (int)($_GET['page'] ?? 1));
$perPage = 100;

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

// Pagination logic differs based on whether we're viewing single or all domains
$offset  = ($page - 1) * $perPage;
$results = [];

if ($domain) {
    // Single domain: Stream efficiently (already time-ordered in file)
    // Read one extra row to determine if there's a next page
    $currentIndex = 0;

    foreach ($files as $file) {
        if (!file_exists($file)) {
            continue;
        }

        $handle = fopen($file, 'r');
        while (($line = fgets($handle)) !== false) {
            if ($currentIndex >= $offset && count($results) <= $perPage) {
                $row = json_decode($line, true);
                if ($row) {
                    $results[] = $row;
                }
            }
            $currentIndex++;
            if (count($results) > $perPage) {
                break 2; // Got enough results + 1 extra to check for next page
            }
        }
        fclose($handle);
    }

    // Check if there's a next page, then remove the extra row
    $hasNext = count($results) > $perPage;
    if ($hasNext) {
        array_pop($results); // Remove the extra row
    }
    $hasPrev = $page > 1;
} else {
    // All domains: Load all pageviews and sort by timestamp for proper ordering
    $buffer = [];

    foreach ($files as $file) {
        if (!file_exists($file)) {
            continue;
        }

        // Extract domain from file path: /var/lib/pageview-tracking/raw/{domain}/{date}/pageview.jsonl
        if (preg_match('#/raw/([^/]+)/#', $file, $matches)) {
            $fileDomain = $matches[1];
        } else {
            $fileDomain = 'unknown';
        }

        $handle = fopen($file, 'r');
        while (($line = fgets($handle)) !== false) {
            $row = json_decode($line, true);
            if ($row && isset($row['ts_pv'])) {
                $row['domain'] = $fileDomain; // Add domain to row
                $buffer[]      = $row;
            }
        }
        fclose($handle);
    }

    // Sort by timestamp
    usort($buffer, fn ($a, $b) => ($a['ts_pv'] ?? 0) <=> ($b['ts_pv'] ?? 0));

    // Paginate
    $total   = count($buffer);
    $results = array_slice($buffer, $offset, $perPage);
    $hasNext = $offset + $perPage < $total;
    $hasPrev = $page > 1;
}

// Load metrics only for the pageviews we're displaying
$neededVids = array_column($results, 'vid');
$neededVids = array_flip($neededVids); // Convert to hash map for O(1) lookup

$metrics = [];
if ($domain) {
    $metricsFile = $raw_dir . '/' . $domain . '/' . $date . '/metrics.jsonl';
    if (file_exists($metricsFile)) {
        $handle = fopen($metricsFile, 'r');
        while (($line = fgets($handle)) !== false) {
            $m = json_decode($line, true);
            if ($m && isset($m['vid']) && isset($neededVids[$m['vid']])) {
                $metrics[$m['vid']] = $m;
            }
        }
        fclose($handle);
    }
} else {
    // Load metrics from all domains, but only for needed view IDs
    foreach (glob($raw_dir . '/*/' . $date . '/metrics.jsonl') as $metricsFile) {
        $handle = fopen($metricsFile, 'r');
        while (($line = fgets($handle)) !== false) {
            $m = json_decode($line, true);
            if ($m && isset($m['vid']) && isset($neededVids[$m['vid']])) {
                $metrics[$m['vid']] = $m;
            }
        }
        fclose($handle);
    }
}

// Build back URL
$backUrl = 'day.php?date=' . urlencode($date);

// Page title
$pageTitle = '📄 Individual Pageviews';
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
    </div>

    <div class="table-container">
        <table>
            <thead>
                <tr>
                    <th>Time (UTC)</th>
<?php if (!$domain): ?>
                    <th>Domain</th>
<?php endif; ?>
                    <th>URL</th>
                    <th>Referrer</th>
                    <th>IP</th>
                    <th>User Agent</th>
                    <th>Lang</th>
                    <th>TZ</th>
                    <th class="number">VW</th>
                    <th class="number">VH</th>
                    <th class="number">TTFB</th>
                    <th class="number">DCL</th>
                    <th class="number">Load</th>
                </tr>
            </thead>
            <tbody>
<?php foreach ($results as $row):
    $m = $metrics[$row['vid'] ?? ''] ?? null;
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
                </tr>
<?php endforeach; ?>
            </tbody>
        </table>
    </div>

    <div class="pagination">
<?php
    $baseUrl = '?date=' . urlencode($date) . ($domain ? '&domain=' . urlencode($domain) : '');
$firstUrl    = $baseUrl . '&page=1';
$prevUrl     = $baseUrl . '&page=' . ($page - 1);
$nextUrl     = $baseUrl . '&page=' . ($page + 1);
?>
        <a href="<?= $firstUrl ?>" class="<?= $hasPrev ? '' : 'disabled' ?>">⏮ First</a>
        <a href="<?= $prevUrl ?>" class="<?= $hasPrev ? '' : 'disabled' ?>">← Previous</a>
        <span style="margin: 0 15px;">Page <?= $page ?></span>
        <a href="<?= $nextUrl ?>" class="<?= $hasNext ? '' : 'disabled' ?>">Next →</a>
    </div>

</body>
</html>

