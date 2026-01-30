<?php

/**
 * Plugin Name: Pageview Tracking
 * Plugin URI: https://github.com/fofxtools/site-automator
 * Description: Tracks pageviews and bot traffic using JavaScript beacons and server-side PHP tracking.
 * Version: 1.0.0
 * Author: FOfX
 * Author URI: https://github.com/fofxtools/site-automator
 * License: MIT
 */

// Prevent direct access
if (!defined('ABSPATH')) {
    exit;
}

/**
 * Enqueue the JavaScript tracking script
 */
function pvt_enqueue_tracking_script()
{
    // Only load on frontend
    if (is_admin()) {
        return;
    }

    $script_path = plugin_dir_path(__FILE__) . 'track_pageview.js';
    if (!file_exists($script_path)) {
        return;
    }

    wp_enqueue_script(
        'pageview-tracking',
        plugin_dir_url(__FILE__) . 'track_pageview.js',
        [],
        filemtime($script_path),
        true // Load in footer
    );

    // Pass the correct track_pageview.php URL to JavaScript
    wp_localize_script(
        'pageview-tracking',
        'PVT',
        [
            'trackUrl' => plugin_dir_url(__FILE__) . 'track_pageview.php',
        ]
    );
}
add_action('wp_enqueue_scripts', 'pvt_enqueue_tracking_script');

/**
 * Track bot pageviews using server-side PHP
 */
function pvt_track_bot_pageview()
{
    // Only track on frontend
    if (is_admin()) {
        return;
    }

    $bot_tracking_path = __DIR__ . '/track_bots.php';
    if (file_exists($bot_tracking_path)) {
        require_once $bot_tracking_path;
    }
}
add_action('wp', 'pvt_track_bot_pageview');
