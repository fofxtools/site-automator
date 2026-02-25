<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pageview Statistics</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }
        h1 {
            color: #333;
            border-bottom: 3px solid #007bff;
            padding-bottom: 10px;
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
        tr:hover {
            background: #f8f9fa;
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
    </style>
</head>
<body>
    <h1>📊 Pageview Statistics</h1>

<?php
$agg_dir = '/var/lib/pageview-tracking/agg/daily';

// Check if directory exists
if (!is_dir($agg_dir)) {
    echo '<div class="error">Data directory not found: ' . htmlspecialchars($agg_dir) . '</div>';
    exit;
}

// Scan for JSON files
$files = glob($agg_dir . '/*.json');

if (empty($files)) {
    echo '<div class="error">No data files found in ' . htmlspecialchars($agg_dir) . '</div>';
    exit;
}

// Parse dates and load data
$dates = [];
foreach ($files as $file) {
    $date = basename($file, '.json');
    $data = json_decode(file_get_contents($file), true);

    if (!$data) {
        continue;
    }

    // Calculate totals for this date
    $total_pageviews              = 0;
    $total_qualified_pageviews    = 0;
    $total_pageviews_with_metrics = 0;
    $domain_count                 = count($data['domains'] ?? []);

    // Bot signal totals (in MySQL column order)
    $bot_totals = [
        'gb_ua' => 0,  // googlebot_ua_pageviews
        'gb_ip' => 0,  // googlebot_ip_pageviews
        'g_ip'  => 0,  // google_ip_pageviews
        'bb_ua' => 0,  // bingbot_ua_pageviews
        'bb_ip' => 0,  // bingbot_ip_pageviews
        'm_ip'  => 0,  // microsoft_ip_pageviews
    ];

    // Performance metrics - weighted averages
    $perf_totals = [
        'ttfb_sum'          => 0,
        'ttfb_count'        => 0,
        'ttfb_median_sum'   => 0,
        'ttfb_median_count' => 0,
        'ttfb_p95_sum'      => 0,
        'ttfb_p95_count'    => 0,
        'dcl_sum'           => 0,
        'dcl_count'         => 0,
        'dcl_median_sum'    => 0,
        'dcl_median_count'  => 0,
        'dcl_p95_sum'       => 0,
        'dcl_p95_count'     => 0,
        'load_sum'          => 0,
        'load_count'        => 0,
        'load_median_sum'   => 0,
        'load_median_count' => 0,
        'load_p95_sum'      => 0,
        'load_p95_count'    => 0,
    ];

    foreach ($data['domains'] ?? [] as $domain_data) {
        foreach ($domain_data['groups'] ?? [] as $group) {
            $total_pageviews += $group['pageviews'] ?? 0;
            $total_qualified_pageviews += $group['qualified_pageviews'] ?? 0;
            $total_pageviews_with_metrics += $group['pageviews_with_metrics'] ?? 0;

            // Sum bot signals
            foreach ($group['bots'] ?? [] as $signal => $count) {
                if (isset($bot_totals[$signal])) {
                    $bot_totals[$signal] += $count;
                }
            }

            // Weighted average for performance metrics
            $perf = $group['performance'] ?? [];

            // TTFB
            if (isset($perf['ttfb']['avg'])) {
                $perf_totals['ttfb_sum'] += $perf['ttfb']['avg'] * $perf['ttfb']['count'];
                $perf_totals['ttfb_count'] += $perf['ttfb']['count'];
            }
            if (isset($perf['ttfb']['median'])) {
                $perf_totals['ttfb_median_sum'] += $perf['ttfb']['median'] * $perf['ttfb']['count'];
                $perf_totals['ttfb_median_count'] += $perf['ttfb']['count'];
            }
            if (isset($perf['ttfb']['p95'])) {
                $perf_totals['ttfb_p95_sum'] += $perf['ttfb']['p95'] * $perf['ttfb']['count'];
                $perf_totals['ttfb_p95_count'] += $perf['ttfb']['count'];
            }

            // DCL
            if (isset($perf['dcl']['avg'])) {
                $perf_totals['dcl_sum'] += $perf['dcl']['avg'] * $perf['dcl']['count'];
                $perf_totals['dcl_count'] += $perf['dcl']['count'];
            }
            if (isset($perf['dcl']['median'])) {
                $perf_totals['dcl_median_sum'] += $perf['dcl']['median'] * $perf['dcl']['count'];
                $perf_totals['dcl_median_count'] += $perf['dcl']['count'];
            }
            if (isset($perf['dcl']['p95'])) {
                $perf_totals['dcl_p95_sum'] += $perf['dcl']['p95'] * $perf['dcl']['count'];
                $perf_totals['dcl_p95_count'] += $perf['dcl']['count'];
            }

            // Load
            if (isset($perf['load']['avg'])) {
                $perf_totals['load_sum'] += $perf['load']['avg'] * $perf['load']['count'];
                $perf_totals['load_count'] += $perf['load']['count'];
            }
            if (isset($perf['load']['median'])) {
                $perf_totals['load_median_sum'] += $perf['load']['median'] * $perf['load']['count'];
                $perf_totals['load_median_count'] += $perf['load']['count'];
            }
            if (isset($perf['load']['p95'])) {
                $perf_totals['load_p95_sum'] += $perf['load']['p95'] * $perf['load']['count'];
                $perf_totals['load_p95_count'] += $perf['load']['count'];
            }
        }
    }

    // Calculate weighted averages
    $dates[] = [
        'date'                   => $date,
        'domains'                => $domain_count,
        'pageviews'              => $total_pageviews,
        'qualified_pageviews'    => $total_qualified_pageviews,
        'gb_ua'                  => $bot_totals['gb_ua'],
        'gb_ip'                  => $bot_totals['gb_ip'],
        'g_ip'                   => $bot_totals['g_ip'],
        'bb_ua'                  => $bot_totals['bb_ua'],
        'bb_ip'                  => $bot_totals['bb_ip'],
        'm_ip'                   => $bot_totals['m_ip'],
        'pageviews_with_metrics' => $total_pageviews_with_metrics,
        'avg_ttfb'               => $perf_totals['ttfb_count'] > 0 ? $perf_totals['ttfb_sum'] / $perf_totals['ttfb_count'] : null,
        'median_ttfb'            => $perf_totals['ttfb_median_count'] > 0 ? $perf_totals['ttfb_median_sum'] / $perf_totals['ttfb_median_count'] : null,
        'p95_ttfb'               => $perf_totals['ttfb_p95_count'] > 0 ? $perf_totals['ttfb_p95_sum'] / $perf_totals['ttfb_p95_count'] : null,
        'avg_dcl'                => $perf_totals['dcl_count'] > 0 ? $perf_totals['dcl_sum'] / $perf_totals['dcl_count'] : null,
        'median_dcl'             => $perf_totals['dcl_median_count'] > 0 ? $perf_totals['dcl_median_sum'] / $perf_totals['dcl_median_count'] : null,
        'p95_dcl'                => $perf_totals['dcl_p95_count'] > 0 ? $perf_totals['dcl_p95_sum'] / $perf_totals['dcl_p95_count'] : null,
        'avg_load'               => $perf_totals['load_count'] > 0 ? $perf_totals['load_sum'] / $perf_totals['load_count'] : null,
        'median_load'            => $perf_totals['load_median_count'] > 0 ? $perf_totals['load_median_sum'] / $perf_totals['load_median_count'] : null,
        'p95_load'               => $perf_totals['load_p95_count'] > 0 ? $perf_totals['load_p95_sum'] / $perf_totals['load_p95_count'] : null,
    ];
}

// Sort by date descending (newest first)
usort($dates, function ($a, $b) {
    return strcmp($b['date'], $a['date']);
});

// Helper function to format metric
function fmt_metric($value)
{
    return $value !== null ? number_format($value, 1) : '-';
}

// Display table
?>
    <div class="table-container">
        <table>
            <thead>
                <tr>
                    <th>Date</th>
                    <th class="number">Domains</th>
                    <th class="number">Qualified Pageviews</th>
                    <th class="number">GB UA</th>
                    <th class="number">GB IP</th>
                    <th class="number">G IP</th>
                    <th class="number">BB UA</th>
                    <th class="number">BB IP</th>
                    <th class="number">M IP</th>
                    <th class="number">w/ Metrics</th>
                    <th class="number">Avg TTFB</th>
                    <th class="number">Med TTFB</th>
                    <th class="number">P95 TTFB</th>
                    <th class="number">Avg DCL</th>
                    <th class="number">Med DCL</th>
                    <th class="number">P95 DCL</th>
                    <th class="number">Avg Load</th>
                    <th class="number">Med Load</th>
                    <th class="number">P95 Load</th>
                </tr>
            </thead>
            <tbody>
<?php foreach ($dates as $row): ?>
                <tr>
                    <td>
                        <a href="day.php?date=<?= htmlspecialchars($row['date']) ?>">
                            <?= htmlspecialchars($row['date']) ?>
                        </a>
                    </td>
                    <td class="number"><?= $row['domains'] ?></td>
                    <td class="number"><?= number_format($row['qualified_pageviews']) ?></td>
                    <td class="number"><?= number_format($row['gb_ua']) ?></td>
                    <td class="number"><?= number_format($row['gb_ip']) ?></td>
                    <td class="number"><?= number_format($row['g_ip']) ?></td>
                    <td class="number"><?= number_format($row['bb_ua']) ?></td>
                    <td class="number"><?= number_format($row['bb_ip']) ?></td>
                    <td class="number"><?= number_format($row['m_ip']) ?></td>
                    <td class="number"><?= number_format($row['pageviews_with_metrics']) ?></td>
                    <td class="number"><?= fmt_metric($row['avg_ttfb']) ?></td>
                    <td class="number"><?= fmt_metric($row['median_ttfb']) ?></td>
                    <td class="number"><?= fmt_metric($row['p95_ttfb']) ?></td>
                    <td class="number"><?= fmt_metric($row['avg_dcl']) ?></td>
                    <td class="number"><?= fmt_metric($row['median_dcl']) ?></td>
                    <td class="number"><?= fmt_metric($row['p95_dcl']) ?></td>
                    <td class="number"><?= fmt_metric($row['avg_load']) ?></td>
                    <td class="number"><?= fmt_metric($row['median_load']) ?></td>
                    <td class="number"><?= fmt_metric($row['p95_load']) ?></td>
                </tr>
<?php endforeach; ?>
            </tbody>
        </table>
    </div>

    <p style="color: #666; margin-top: 20px; font-size: 13px;">
        Click a date to view detailed statistics. | <a href="logs.php">🤖 Bot Logs</a>
        <br>
        <strong>Bot Signals:</strong> GB UA = Googlebot User Agent, GB IP = Googlebot IP, G IP = Google IP,
        BB UA = Bingbot User Agent, BB IP = Bingbot IP, M IP = Microsoft IP
        <br>
        <strong>Performance Metrics:</strong> TTFB = Time to First Byte, DCL = DOM Content Loaded, Load = Load Event End (all in milliseconds)
        <br>
        <em>Note: Median and P95 values are weighted approximations (*)</em>
    </p>
</body>
</html>
