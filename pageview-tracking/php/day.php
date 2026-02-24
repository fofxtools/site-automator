<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Daily Statistics</title>
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
        .filter-bar {
            background: white;
            padding: 15px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            border-radius: 4px;
        }
        .filter-bar label {
            font-weight: 600;
            margin-right: 10px;
            color: #333;
        }
        .filter-bar select {
            padding: 8px 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
            background: white;
            cursor: pointer;
        }
        .filter-bar select:hover {
            border-color: #007bff;
        }
        .table-container {
            overflow-x: auto;
            background: white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
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
        .totals-row {
            background: #e7f3ff !important;
            font-weight: 600;
        }
        .totals-row:hover {
            background: #d0e8ff !important;
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
        .domain-group {
            border-top: 2px solid #007bff;
        }
        .footnote {
            color: #666;
            margin-top: 20px;
            font-size: 13px;
        }
        .hidden {
            display: none;
        }
        td a {
            color: #007bff;
            text-decoration: none;
        }
        td a:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>

<?php
$agg_dir = '/var/lib/pageview-tracking/agg/daily';

// Get date from query parameter (UTC)
$date = $_GET['date'] ?? gmdate('Y-m-d');

// Validate date format (YYYY-MM-DD)
if (!preg_match('/^\d{4}-\d{2}-\d{2}$/', $date)) {
    echo '<div class="error">Invalid date format. Expected YYYY-MM-DD.</div>';
    exit;
}

// Load JSON file
$file = $agg_dir . '/' . $date . '.json';

if (!file_exists($file)) {
    echo '<div class="error">No data found for date: ' . htmlspecialchars($date) . '</div>';
    echo '<p><a href="index.php" class="back-link">← Back to dates</a></p>';
    exit;
}

$data = json_decode(file_get_contents($file), true);

if (!$data) {
    echo '<div class="error">Failed to parse data file for date: ' . htmlspecialchars($date) . '</div>';
    echo '<p><a href="index.php" class="back-link">← Back to dates</a></p>';
    exit;
}

// Collect all rows for display
$rows    = [];
$domains = [];

foreach ($data['domains'] ?? [] as $domain => $domain_data) {
    $domains[] = $domain;

    foreach ($domain_data['groups'] ?? [] as $group) {
        $is_internal = $group['is_internal'] ?? 0;
        $type        = $is_internal ? 'Internal' : 'Homepage';

        // Extract bot signals
        $bots  = $group['bots'] ?? [];
        $gb_ua = $bots['gb_ua'] ?? 0;
        $gb_ip = $bots['gb_ip'] ?? 0;
        $g_ip  = $bots['g_ip'] ?? 0;
        $bb_ua = $bots['bb_ua'] ?? 0;
        $bb_ip = $bots['bb_ip'] ?? 0;
        $m_ip  = $bots['m_ip'] ?? 0;

        // Extract performance metrics
        $perf = $group['performance'] ?? [];
        $ttfb = $perf['ttfb'] ?? [];
        $dcl  = $perf['dcl'] ?? [];
        $load = $perf['load'] ?? [];

        $pageviews              = $group['pageviews'] ?? 0;
        $qualified_pageviews    = $group['qualified_pageviews'] ?? 0;
        $pageviews_with_metrics = $group['pageviews_with_metrics'] ?? 0;

        // Store row for display
        $rows[] = [
            'domain'                 => $domain,
            'type'                   => $type,
            'pageviews'              => $pageviews,
            'qualified_pageviews'    => $qualified_pageviews,
            'gb_ua'                  => $gb_ua,
            'gb_ip'                  => $gb_ip,
            'g_ip'                   => $g_ip,
            'bb_ua'                  => $bb_ua,
            'bb_ip'                  => $bb_ip,
            'm_ip'                   => $m_ip,
            'pageviews_with_metrics' => $pageviews_with_metrics,
            'avg_ttfb'               => $ttfb['avg'] ?? null,
            'median_ttfb'            => $ttfb['median'] ?? null,
            'p95_ttfb'               => $ttfb['p95'] ?? null,
            'avg_dcl'                => $dcl['avg'] ?? null,
            'median_dcl'             => $dcl['median'] ?? null,
            'p95_dcl'                => $dcl['p95'] ?? null,
            'avg_load'               => $load['avg'] ?? null,
            'median_load'            => $load['median'] ?? null,
            'p95_load'               => $load['p95'] ?? null,
            'ttfb_count'             => $ttfb['count'] ?? 0,
            'dcl_count'              => $dcl['count'] ?? 0,
            'load_count'             => $load['count'] ?? 0,
        ];
    }
}

// Helper function to format metric
function fmt_metric($value)
{
    return $value !== null ? number_format($value, 1) : '-';
}

// Helper function to render a row
function render_row($row, $date, $is_totals = false)
{
    $class       = $is_totals ? ' class="totals-row"' : '';
    $data_domain = !$is_totals ? ' data-domain="' . htmlspecialchars($row['domain']) . '"' : '';

    echo "<tr{$class}{$data_domain}>\n";

    // Domain column with link to views.php
    if ($is_totals) {
        $views_url = 'views.php?date=' . urlencode($date);
        echo '    <td><a href="' . $views_url . '">' . htmlspecialchars($row['domain']) . '</a></td>' . "\n";
    } else {
        $views_url = 'views.php?date=' . urlencode($date) . '&domain=' . urlencode($row['domain']);
        echo '    <td><a href="' . $views_url . '">' . htmlspecialchars($row['domain']) . '</a></td>' . "\n";
    }

    echo '    <td>' . htmlspecialchars($row['type']) . "</td>\n";
    echo '    <td class="number">' . number_format($row['qualified_pageviews']) . "</td>\n";
    echo '    <td class="number">' . number_format($row['gb_ua']) . "</td>\n";
    echo '    <td class="number">' . number_format($row['gb_ip']) . "</td>\n";
    echo '    <td class="number">' . number_format($row['g_ip']) . "</td>\n";
    echo '    <td class="number">' . number_format($row['bb_ua']) . "</td>\n";
    echo '    <td class="number">' . number_format($row['bb_ip']) . "</td>\n";
    echo '    <td class="number">' . number_format($row['m_ip']) . "</td>\n";
    echo '    <td class="number">' . number_format($row['pageviews_with_metrics']) . "</td>\n";
    echo '    <td class="number">' . fmt_metric($row['avg_ttfb']) . "</td>\n";
    echo '    <td class="number">' . fmt_metric($row['median_ttfb']) . ($is_totals && $row['median_ttfb'] !== null ? '*' : '') . "</td>\n";
    echo '    <td class="number">' . fmt_metric($row['p95_ttfb']) . ($is_totals && $row['p95_ttfb'] !== null ? '*' : '') . "</td>\n";
    echo '    <td class="number">' . fmt_metric($row['avg_dcl']) . "</td>\n";
    echo '    <td class="number">' . fmt_metric($row['median_dcl']) . ($is_totals && $row['median_dcl'] !== null ? '*' : '') . "</td>\n";
    echo '    <td class="number">' . fmt_metric($row['p95_dcl']) . ($is_totals && $row['p95_dcl'] !== null ? '*' : '') . "</td>\n";
    echo '    <td class="number">' . fmt_metric($row['avg_load']) . "</td>\n";
    echo '    <td class="number">' . fmt_metric($row['median_load']) . ($is_totals && $row['median_load'] !== null ? '*' : '') . "</td>\n";
    echo '    <td class="number">' . fmt_metric($row['p95_load']) . ($is_totals && $row['p95_load'] !== null ? '*' : '') . "</td>\n";
    echo "</tr>\n";
}

// Sort domains alphabetically
sort($domains);
?>

    <div class="header">
        <h1>📊 Statistics for <?= htmlspecialchars($date) ?></h1>
        <div>
            <a href="views.php?date=<?= urlencode($date) ?>" class="back-link">📄 View All Pageviews</a>
            <span style="margin: 0 10px;">|</span>
            <a href="views.php?date=<?= urlencode($date) ?>&qualified=1" class="back-link">📄 View Qualified Pageviews</a>
            <span style="margin: 0 10px;">|</span>
            <a href="index.php" class="back-link">← Back to dates</a>
        </div>
    </div>

    <div class="filter-bar">
        <label for="domainFilter">Filter by Domain:</label>
        <select id="domainFilter" onchange="filterByDomain()">
            <option value="all">All Domains</option>
<?php foreach ($domains as $domain): ?>
            <option value="<?= htmlspecialchars($domain) ?>"><?= htmlspecialchars($domain) ?></option>
<?php endforeach; ?>
        </select>
    </div>

    <div class="table-container">
        <table>
            <thead>
                <tr>
                    <th>Domain</th>
                    <th>Type</th>
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
            <tbody id="statsTable">
                <tr class="totals-row" id="totalsRow">
                    <td id="totalDomain">TOTAL</td>
                    <td>-</td>
                    <td class="number" id="totalQualifiedPageviews">-</td>
                    <td class="number" id="totalGbUa">-</td>
                    <td class="number" id="totalGbIp">-</td>
                    <td class="number" id="totalGIp">-</td>
                    <td class="number" id="totalBbUa">-</td>
                    <td class="number" id="totalBbIp">-</td>
                    <td class="number" id="totalMIp">-</td>
                    <td class="number" id="totalWithMetrics">-</td>
                    <td class="number" id="totalAvgTtfb">-</td>
                    <td class="number" id="totalMedTtfb">-</td>
                    <td class="number" id="totalP95Ttfb">-</td>
                    <td class="number" id="totalAvgDcl">-</td>
                    <td class="number" id="totalMedDcl">-</td>
                    <td class="number" id="totalP95Dcl">-</td>
                    <td class="number" id="totalAvgLoad">-</td>
                    <td class="number" id="totalMedLoad">-</td>
                    <td class="number" id="totalP95Load">-</td>
                </tr>
<?php
// Render all domain rows
$current_domain = null;
foreach ($rows as $row) {
    // Add visual separator between domains
    if ($current_domain !== null && $current_domain !== $row['domain']) {
        echo "<tr class=\"domain-group\" data-domain=\"separator\"><td colspan=\"19\"></td></tr>\n";
    }
    $current_domain = $row['domain'];

    render_row($row, $date);
}
?>
            </tbody>
        </table>
    </div>

    <div class="footnote">
        <strong>Bot Signals:</strong> GB UA = Googlebot User Agent, GB IP = Googlebot IP, G IP = Google IP, 
        BB UA = Bingbot User Agent, BB IP = Bingbot IP, M IP = Microsoft IP
        <br>
        <strong>Performance Metrics:</strong> TTFB = Time to First Byte, DCL = DOM Content Loaded, Load = Load Event End (all in milliseconds)
        <br>
        <em>* Median and P95 values in TOTALS row are weighted approximations</em>
    </div>

    <script>
        // Store all row data for recalculation
        const rowData = <?= json_encode($rows) ?>;
        
        function filterByDomain() {
            const selectedDomain = document.getElementById('domainFilter').value;
            const rows = document.querySelectorAll('#statsTable tr[data-domain]');
            
            // Show/hide rows based on filter
            rows.forEach(row => {
                const domain = row.getAttribute('data-domain');
                if (domain === 'separator') {
                    // Hide separators when filtering
                    row.style.display = selectedDomain === 'all' ? '' : 'none';
                } else if (selectedDomain === 'all' || domain === selectedDomain) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
            
            // Recalculate totals from visible rows
            recalculateTotals(selectedDomain);
        }
        
        function recalculateTotals(selectedDomain) {
            // Filter data based on selected domain
            const visibleRows = selectedDomain === 'all' 
                ? rowData 
                : rowData.filter(row => row.domain === selectedDomain);
            
            // Calculate totals
            let totals = {
                qualified_pageviews: 0,
                gb_ua: 0,
                gb_ip: 0,
                g_ip: 0,
                bb_ua: 0,
                bb_ip: 0,
                m_ip: 0,
                pageviews_with_metrics: 0,
                ttfb_sum: 0,
                ttfb_count: 0,
                ttfb_median_sum: 0,
                ttfb_median_count: 0,
                ttfb_p95_sum: 0,
                ttfb_p95_count: 0,
                dcl_sum: 0,
                dcl_count: 0,
                dcl_median_sum: 0,
                dcl_median_count: 0,
                dcl_p95_sum: 0,
                dcl_p95_count: 0,
                load_sum: 0,
                load_count: 0,
                load_median_sum: 0,
                load_median_count: 0,
                load_p95_sum: 0,
                load_p95_count: 0,
            };
            
            visibleRows.forEach(row => {
                totals.qualified_pageviews += row.qualified_pageviews;
                totals.gb_ua += row.gb_ua;
                totals.gb_ip += row.gb_ip;
                totals.g_ip += row.g_ip;
                totals.bb_ua += row.bb_ua;
                totals.bb_ip += row.bb_ip;
                totals.m_ip += row.m_ip;
                totals.pageviews_with_metrics += row.pageviews_with_metrics;
                
                // Weighted averages
                if (row.avg_ttfb !== null && row.ttfb_count > 0) {
                    totals.ttfb_sum += row.avg_ttfb * row.ttfb_count;
                    totals.ttfb_count += row.ttfb_count;
                }
                if (row.median_ttfb !== null && row.ttfb_count > 0) {
                    totals.ttfb_median_sum += row.median_ttfb * row.ttfb_count;
                    totals.ttfb_median_count += row.ttfb_count;
                }
                if (row.p95_ttfb !== null && row.ttfb_count > 0) {
                    totals.ttfb_p95_sum += row.p95_ttfb * row.ttfb_count;
                    totals.ttfb_p95_count += row.ttfb_count;
                }
                
                if (row.avg_dcl !== null && row.dcl_count > 0) {
                    totals.dcl_sum += row.avg_dcl * row.dcl_count;
                    totals.dcl_count += row.dcl_count;
                }
                if (row.median_dcl !== null && row.dcl_count > 0) {
                    totals.dcl_median_sum += row.median_dcl * row.dcl_count;
                    totals.dcl_median_count += row.dcl_count;
                }
                if (row.p95_dcl !== null && row.dcl_count > 0) {
                    totals.dcl_p95_sum += row.p95_dcl * row.dcl_count;
                    totals.dcl_p95_count += row.dcl_count;
                }
                
                if (row.avg_load !== null && row.load_count > 0) {
                    totals.load_sum += row.avg_load * row.load_count;
                    totals.load_count += row.load_count;
                }
                if (row.median_load !== null && row.load_count > 0) {
                    totals.load_median_sum += row.median_load * row.load_count;
                    totals.load_median_count += row.load_count;
                }
                if (row.p95_load !== null && row.load_count > 0) {
                    totals.load_p95_sum += row.p95_load * row.load_count;
                    totals.load_p95_count += row.load_count;
                }
            });
            
            // Helper to format numbers
            function fmt(value) {
                return value !== null && value !== undefined ? value.toLocaleString('en-US') : '-';
            }
            function fmtMetric(value) {
                return value !== null && value !== undefined ? value.toFixed(1) : '-';
            }
            
            // Update TOTALS row
            document.getElementById('totalDomain').textContent = selectedDomain === 'all' ? 'TOTAL' : selectedDomain.toUpperCase();
            document.getElementById('totalQualifiedPageviews').textContent = fmt(totals.qualified_pageviews);
            document.getElementById('totalGbUa').textContent = fmt(totals.gb_ua);
            document.getElementById('totalGbIp').textContent = fmt(totals.gb_ip);
            document.getElementById('totalGIp').textContent = fmt(totals.g_ip);
            document.getElementById('totalBbUa').textContent = fmt(totals.bb_ua);
            document.getElementById('totalBbIp').textContent = fmt(totals.bb_ip);
            document.getElementById('totalMIp').textContent = fmt(totals.m_ip);
            document.getElementById('totalWithMetrics').textContent = fmt(totals.pageviews_with_metrics);
            
            // Performance metrics
            const avgTtfb = totals.ttfb_count > 0 ? totals.ttfb_sum / totals.ttfb_count : null;
            const medTtfb = totals.ttfb_median_count > 0 ? totals.ttfb_median_sum / totals.ttfb_median_count : null;
            const p95Ttfb = totals.ttfb_p95_count > 0 ? totals.ttfb_p95_sum / totals.ttfb_p95_count : null;
            
            const avgDcl = totals.dcl_count > 0 ? totals.dcl_sum / totals.dcl_count : null;
            const medDcl = totals.dcl_median_count > 0 ? totals.dcl_median_sum / totals.dcl_median_count : null;
            const p95Dcl = totals.dcl_p95_count > 0 ? totals.dcl_p95_sum / totals.dcl_p95_count : null;
            
            const avgLoad = totals.load_count > 0 ? totals.load_sum / totals.load_count : null;
            const medLoad = totals.load_median_count > 0 ? totals.load_median_sum / totals.load_median_count : null;
            const p95Load = totals.load_p95_count > 0 ? totals.load_p95_sum / totals.load_p95_count : null;
            
            document.getElementById('totalAvgTtfb').textContent = fmtMetric(avgTtfb);
            document.getElementById('totalMedTtfb').textContent = fmtMetric(medTtfb) + (medTtfb !== null && selectedDomain === 'all' ? '*' : '');
            document.getElementById('totalP95Ttfb').textContent = fmtMetric(p95Ttfb) + (p95Ttfb !== null && selectedDomain === 'all' ? '*' : '');
            
            document.getElementById('totalAvgDcl').textContent = fmtMetric(avgDcl);
            document.getElementById('totalMedDcl').textContent = fmtMetric(medDcl) + (medDcl !== null && selectedDomain === 'all' ? '*' : '');
            document.getElementById('totalP95Dcl').textContent = fmtMetric(p95Dcl) + (p95Dcl !== null && selectedDomain === 'all' ? '*' : '');
            
            document.getElementById('totalAvgLoad').textContent = fmtMetric(avgLoad);
            document.getElementById('totalMedLoad').textContent = fmtMetric(medLoad) + (medLoad !== null && selectedDomain === 'all' ? '*' : '');
            document.getElementById('totalP95Load').textContent = fmtMetric(p95Load) + (p95Load !== null && selectedDomain === 'all' ? '*' : '');
        }
        
        // Initialize totals on page load
        recalculateTotals('all');
    </script>
</body>
</html>
