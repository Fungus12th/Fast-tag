"""
FASTag DA-2 â€” Flask Web Server (app.py)
Central hub: serves the dashboard, exposes REST APIs for ingestion, stats, chaos mode,
and deduplication control.
"""

import json
import time
import threading
from datetime import datetime, timezone

from flask import Flask, request, jsonify, render_template

import config
from db import create_storage
from deduplicator import BatchDeduplicator

# â”€â”€â”€ App Initialization â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
app = Flask(__name__)

# Storage backend (Cassandra or in-memory)
storage = create_storage()

# Deduplication worker
dedup_worker = BatchDeduplicator(storage)

# Chaos mode state
chaos_state = {
    "active": False,
    "activated_at": None,
    "multiplier": config.CHAOS_MULTIPLIER,
}
chaos_lock = threading.Lock()


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# DASHBOARD ROUTE
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.route("/")
def index():
    """Serve the main dashboard page."""
    return render_template("index.html")

@app.route("/database")
def database():
    """Serve the database view page."""
    return render_template("database.html")



# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# INGESTION API
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.route("/api/ingest", methods=["POST"])
def ingest():
    """
    Receive a batch of RFID pings from a load generator.

    Expected JSON body:
    {
        "pings": [
            {
                "plaza_id": "PLAZA_NH48_GURUGRAM",
                "tag_id": "TAG_ABC123",
                "rssi_signal_strength": -42.5,
                "ping_timestamp": "2026-10-07T23:15:00Z",
                "lane_id": "LANE_3",
                "region": "NORTH"
            },
            ...
        ]
    }
    """
    data = request.get_json(silent=True)
    if not data or "pings" not in data:
        return jsonify({"error": "Request body must contain a 'pings' array"}), 400

    pings = data["pings"]
    if not isinstance(pings, list):
        return jsonify({"error": "'pings' must be an array"}), 400

    if len(pings) == 0:
        return jsonify({"error": "'pings' array is empty"}), 400

    count = storage.insert_pings(pings)
    return jsonify({
        "status":   "ok",
        "ingested": count,
        "total":    storage.get_total_ingested(),
    }), 201


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# LIVE STATS API
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.route("/api/stats", methods=["GET"])
def stats():
    """
    Get live aggregate stats for the dashboard hero counters.

    Response:
    {
        "total_raw_pings": 45000,
        "total_deduplicated_journeys": 842,
        "dedup_ratio": 93.2,
        "pings_per_second": 3450.0,
        "chaos_mode": false,
        "last_dedup_run": "2026-10-07T23:15:00Z"
    }
    """
    dedup_results = dedup_worker.get_results()
    with chaos_lock:
        chaos_active = chaos_state["active"]

    return jsonify({
        "total_raw_pings":              storage.get_total_ingested(),
        "total_deduplicated_journeys":  dedup_results["total_journeys"],
        "dedup_ratio":                  dedup_results["last_dedup_ratio"],
        "pings_per_second":             storage.get_throughput_pps(),
        "chaos_mode":                   chaos_active,
        "last_dedup_run":               dedup_results["last_run_at"],
        "last_raw_count":               dedup_results["last_raw_count"],
        "last_journey_count":           dedup_results["last_journey_count"],
    })


@app.route("/api/stats/plaza", methods=["GET"])
def plaza_stats():
    """
    Get per-plaza breakdown stats.

    Response:
    {
        "plazas": {
            "PLAZA_NH48_GURUGRAM": {
                "plaza_id": "PLAZA_NH48_GURUGRAM",
                "total_pings": 12000,
                "unique_tags": 230,
                "duplicates": 11770,
                "region": "NORTH"
            },
            ...
        }
    }
    """
    return jsonify({"plazas": storage.get_plaza_stats()})


@app.route("/api/stats/throughput", methods=["GET"])
def throughput_history():
    """
    Get throughput time-series data for the live chart.

    Query params:
        buckets (int): Number of 1-second buckets (default 30)

    Response:
    {
        "data": [
            {"timestamp": "...", "pps": 1200},
            ...
        ]
    }
    """
    buckets = request.args.get("buckets", 30, type=int)
    buckets = max(5, min(buckets, 120))  # Clamp
    return jsonify({"data": storage.get_throughput_history(buckets=buckets)})


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# DEDUPLICATION CONTROL API
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.route("/api/dedup/trigger", methods=["POST"])
def dedup_trigger():
    """Manually trigger a deduplication run. Returns the run results."""
    result = dedup_worker.trigger_now()
    return jsonify(result)


@app.route("/api/dedup/config", methods=["GET"])
def dedup_config_get():
    """Get current dedup worker configuration."""
    return jsonify({
        "interval_seconds": dedup_worker.get_interval(),
        "time_window_seconds": config.DEDUP_TIME_WINDOW_SECONDS,
    })


@app.route("/api/dedup/config", methods=["PUT"])
def dedup_config_set():
    """
    Update dedup worker configuration.

    Expected JSON body:
    {
        "interval_seconds": 15
    }
    """
    data = request.get_json(silent=True)
    if not data or "interval_seconds" not in data:
        return jsonify({"error": "Provide 'interval_seconds'"}), 400
    try:
        interval = int(data["interval_seconds"])
    except ValueError:
        return jsonify({"error": "'interval_seconds' must be an integer"}), 400
    dedup_worker.set_interval(interval)
    return jsonify({
        "status": "ok",
        "interval_seconds": dedup_worker.get_interval(),
    })


@app.route("/api/dedup/results", methods=["GET"])
def dedup_results():
    """Get the latest dedup run results including recent journeys for the event feed."""
    return jsonify(dedup_worker.get_results())


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# CHAOS MODE API
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.route("/api/chaos", methods=["POST"])
def chaos_toggle():
    """
    Toggle chaos mode on/off. Generators poll /api/chaos/status to check.

    Optional JSON body:
    {
        "active": true    // explicit set; omit to toggle
    }
    """
    data = request.get_json(silent=True) or {}
    with chaos_lock:
        if "active" in data:
            chaos_state["active"] = bool(data["active"])
        else:
            chaos_state["active"] = not chaos_state["active"]
        chaos_state["activated_at"] = (
            datetime.now(timezone.utc).isoformat() if chaos_state["active"] else None
        )
        chaos_state["multiplier"] = config.CHAOS_MULTIPLIER
        state = dict(chaos_state)

    action = "ACTIVATED" if state["active"] else "DEACTIVATED"
    print(f"[CHAOS] Chaos mode {action} (Ã-{state['multiplier']})")
    return jsonify({"status": "ok", **state})


@app.route("/api/chaos/status", methods=["GET"])
def chaos_status():
    """
    Check chaos mode status. Generators poll this endpoint.

    Response:
    {
        "active": true,
        "multiplier": 10,
        "activated_at": "2026-10-07T23:20:00Z"
    }
    """
    with chaos_lock:
        return jsonify(dict(chaos_state))


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# HEALTH CHECK
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.route("/api/database/tail", methods=["GET"])
def database_tail():
    pings = storage.get_recent_pings(window_seconds=60)[:100]
    return jsonify({"data": pings})

@app.route("/api/health", methods=["GET"])
def health():
    """Health check endpoint for network verification."""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "storage_backend": type(storage).__name__,
        "total_pings_ingested": storage.get_total_ingested(),
        "dedup_worker_running": dedup_worker.is_running(),
    })


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# STARTUP
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
if __name__ == "__main__":
    print("=" * 60)
    print("  FASTag DA-2 â€” High-Frequency Ingestion & Deduplication")
    print("=" * 60)
    print(f"  Server:   http://{config.SERVER_HOST}:{config.SERVER_PORT}")
    print(f"  Storage:  {type(storage).__name__}")
    print(f"  Dedup:    every {config.DEDUP_INTERVAL_SECONDS}s")
    print("=" * 60)

    # Start the background dedup worker
    if config.DEDUP_AUTO_START:
        dedup_worker.start()

    # Run Flask (threaded=True for handling concurrent requests)
    app.run(
        host=config.SERVER_HOST,
        port=config.SERVER_PORT,
        debug=config.DEBUG_MODE,
        threaded=True,
        use_reloader=False,  # Avoid double-starting the dedup worker
    )

