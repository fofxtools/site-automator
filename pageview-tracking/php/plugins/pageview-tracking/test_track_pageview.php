<?php
require_once __DIR__ . '/track_bots.php';
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pageview Tracking Test</title>
    <script src="track_pageview.js"></script>
</head>
<body>
    <h1>Pageview Tracking Test</h1>
    <p>This page tests the hybrid pageview tracking script with:</p>
    <ul>
        <li>Pageview tracking on first real visibility</li>
        <li>Performance metrics on page load</li>
        <li>Modern Navigation Timing API with legacy fallback</li>
    </ul>
    <p>Page loaded at: <span id="loadTime"></span></p>

    <h2>Performance Metrics</h2>
    <ul>
        <li>TTFB: <span id="ttfb">calculating...</span></li>
        <li>DOM Content Loaded: <span id="dcl">calculating...</span></li>
        <li>Load Event End: <span id="load">calculating...</span></li>
    </ul>

    <script>
    document.getElementById('loadTime').textContent = new Date().toLocaleTimeString();

    // Listen for metrics from track_pageview.js
    window.addEventListener('trackingMetricsReady', function(e) {
        var metrics = e.detail;
        document.getElementById('ttfb').textContent = Math.round(metrics.ttfb_ms) + 'ms';
        document.getElementById('dcl').textContent = Math.round(metrics.dom_content_loaded_ms) + 'ms';
        document.getElementById('load').textContent = Math.round(metrics.load_event_end_ms) + 'ms';
    });
    </script>
</body>
</html>
