(function() {
    // Allow external config (e.g., WordPress) to override URL
    var trackUrl = (typeof PVT !== "undefined" && PVT.trackUrl) ? PVT.trackUrl : "track_pageview.php";

    function makeViewId() {
        // Use the built-in crypto UUID if available
        if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
            return crypto.randomUUID();
        }

        // Fallback: UUID-shaped Math.random() (safe on all browsers)
        return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function(c) {
            var r = Math.random() * 16 | 0;
            var v = (c === "x") ? r : ((r & 0x3) | 0x8);
            return v.toString(16);
        });
    }

    var viewId = makeViewId();
    var sentPageview = false;

    function send(path, obj) {
        var requestBody = JSON.stringify(obj);
        if (navigator.sendBeacon) {
            navigator.sendBeacon(path, new Blob([requestBody], {
                type: "application/json"
            }));
        } else {
            fetch(path, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: requestBody,
                keepalive: true
            }).catch(function() {});
        }
    }

    // Pageview on first real visibility
    function sendPageview() {
        if (sentPageview) return;
        sentPageview = true;
        send(trackUrl, {
            type: "pageview",
            view_id: viewId,
            url: location.href,
            referrer: document.referrer || "",
            language: navigator.language || "",
            timezone: (Intl.DateTimeFormat().resolvedOptions().timeZone || ""),
            viewport_width: innerWidth,
            viewport_height: innerHeight,
            ts_pageview_ms: Date.now()
        });
    }

    var isPrerender = (document.prerendering === true);
    if (document.visibilityState === "visible" && !isPrerender) sendPageview();
    else document.addEventListener("visibilitychange", function() {
        if (document.visibilityState === "visible") sendPageview();
    }, {
        once: true
    });

    // Metrics on load (Navigation Timing v2, fallback to legacy)
    // Defer one tick so loadEventEnd is populated
    window.addEventListener("load", function() {
        setTimeout(function() {
            var nav = performance.getEntriesByType && performance.getEntriesByType("navigation")[0];
            var t = performance.timing;
            var metrics = nav ? {
                ttfb_ms: nav.responseStart - nav.startTime,
                dom_content_loaded_ms: nav.domContentLoadedEventEnd - nav.startTime,
                load_event_end_ms: nav.loadEventEnd - nav.startTime
            } : (t && t.loadEventEnd ? {
                ttfb_ms: t.responseStart - t.navigationStart,
                dom_content_loaded_ms: t.domContentLoadedEventEnd - t.navigationStart,
                load_event_end_ms: t.loadEventEnd - t.navigationStart
            } : null);

            if (metrics) {
                // Dispatch custom event for display purposes
                window.dispatchEvent(new CustomEvent("trackingMetricsReady", {
                    detail: metrics
                }));

                send(trackUrl, {
                    type: "metrics",
                    view_id: viewId,
                    url: location.href,
                    ts_metrics_ms: Date.now(),
                    // Flatten for simpler server inserts
                    ttfb_ms: metrics.ttfb_ms,
                    dom_content_loaded_ms: metrics.dom_content_loaded_ms,
                    load_event_end_ms: metrics.load_event_end_ms
                });
            }
        }, 0);
    }, {
        once: true
    });

    // Safety net: send pageview if page closes before visible
    addEventListener("pagehide", function() {
        if (!sentPageview) sendPageview();
    }, {
        once: true
    });
})();