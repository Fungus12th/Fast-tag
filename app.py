"""
FASTag DA-2 â€” Flask Web Server (app.py)
Central hub: serves the dashboard, exposes REST APIs for ingestion, stats, chaos mode,
and deduplication control.
"""

import os
import json
import time
import threading
from datetime import datetime, timezone

from flask import Flask, request, jsonify, render_template, session, redirect, url_for, Response

import config
import sql_ledger
from db import create_storage
from deduplicator import BatchDeduplicator

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(32).hex())

# Initialize 3NF SQL Financial Ledger database (SQLite zero-bloat)
sql_ledger.init_db()

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
# ─────────────────────────────────────────────────────────────────────────────
# MULTI-TIER AUTHENTICATION & ROUTE ACCESS CONTROLS
# ─────────────────────────────────────────────────────────────────────────────
def get_current_user():
    """Returns currently authenticated user session or None."""
    if "username" in session:
        return {
            "username": session.get("username"),
            "role": session.get("role", "user"),
            "full_name": session.get("full_name"),
            "city": session.get("city"),
            "user_id": session.get("user_id"),
        }
    return None

def redirect_for_role(role, username=None):
    """Returns appropriate redirect response based on role."""
    if role == "admin":
        return redirect("/dashboard")
    elif role == "city":
        return redirect(f"/city/{(username or '').lower()}")
    elif role == "user":
        return redirect(f"/portal/{(username or '').lower()}")
    return redirect("/login")


# ─────────────────────────────────────────────────────────────────────────────
# ROOT & LOGIN ROUTES (index.html is the Login Portal)
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    """
    Root entrypoint: index.html is the Login Portal.
    Redirects already authenticated sessions to their respective dashboards.
    """
    user = get_current_user()
    if user:
        return redirect_for_role(user["role"], user["username"])
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login_page():
    """Unified multi-tier login portal."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        account = sql_ledger.authenticate_account(username, password)
        if account:
            session.clear()
            session["username"] = account["username"]
            session["role"] = account["role"]
            session["full_name"] = account["full_name"]
            session["city"] = account.get("city")
            session["user_id"] = account.get("user_id")
            return redirect_for_role(account["role"], account["username"])
        return render_template("index.html", error="Invalid username or password.", username=username)
    
    user = get_current_user()
    if user:
        return redirect_for_role(user["role"], user["username"])
    return render_template("index.html")

@app.route("/logout")
def logout():
    """Log out of portal session and return to root login."""
    session.clear()
    return redirect("/")

@app.route("/portal")
def user_portal():
    """Redirect to user dashboard if logged in, else to login page."""
    user = get_current_user()
    if user:
        return redirect_for_role(user["role"], user["username"])
    return redirect("/")


# ─────────────────────────────────────────────────────────────────────────────
# TIER 1: VEHICLE OWNER PORTAL (Normal Users)
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/portal/<username>")
def user_dashboard(username):
    """
    Vehicle Owner Personal Dashboard.
    Normal users can ONLY view their own balance, vehicles, and journey history.
    """
    user = get_current_user()
    if not user:
        return redirect("/")
    
    # Restrict normal users so they can ONLY view their own portal
    if user["role"] == "user" and user["username"].lower() != username.lower():
        return redirect(f"/portal/{user['username']}")
    elif user["role"] == "city":
        return redirect(f"/city/{user['username']}")

    data = sql_ledger.get_user_dashboard_data(username)
    if not data:
        return "User not found in SQL database", 404
    return render_template("user_dashboard.html", user_data=data, owner=data)


# ─────────────────────────────────────────────────────────────────────────────
# TIER 2: REGIONAL / CITY STATION DASHBOARD (Local Database View)
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/city/<city_name>")
def city_dashboard(city_name):
    """
    City Regional Station Local Database View (e.g. /city/chennai).
    Displays only the local database, local plazas, and passage events for THAT city.
    """
    user = get_current_user()
    if not user:
        return redirect("/")
    
    # Restrict city officers to their own city (admin has global access)
    if user["role"] == "city" and user["username"].lower() != city_name.lower():
        return redirect(f"/city/{user['username']}")
    elif user["role"] == "user":
        return redirect(f"/portal/{user['username']}")

    data = sql_ledger.get_city_dashboard_data(city_name)
    if not data:
        return f"City region '{city_name}' not found", 404

    # Extract local recent raw pings for this city's plazas
    plaza_names = {p["plaza_name"] for p in data["plazas"]}
    recent_raw = [
        p for p in storage.get_recent_pings(300)
        if p.get("region") == data["city_key"] or p.get("plaza_id") in plaza_names
    ][:30]
    data["recent_raw_pings"] = recent_raw

    return render_template("city_dashboard.html", city=data)

@app.route("/api/city/<city_name>/data")
def api_city_data(city_name):
    """API for real-time live polling of city local database events."""
    data = sql_ledger.get_city_dashboard_data(city_name)
    if not data:
        return jsonify({"error": "City not found"}), 404

    plaza_names = {p["plaza_name"] for p in data["plazas"]}
    recent_raw = [
        p for p in storage.get_recent_pings(300)
        if p.get("region") == data["city_key"] or p.get("plaza_id") in plaza_names
    ][:30]
    data["recent_raw_pings"] = recent_raw
    return jsonify(data)

@app.route("/api/city/<city_name>/sql", methods=["POST"])
def api_city_sql(city_name):
    """Executes arbitrary read-only SQL strictly against this city's local node database."""
    user = get_current_user()
    if not user or (user["role"] == "user"):
        return jsonify({"success": False, "error": "Unauthorized"}), 403
    if user["role"] == "city" and user["username"].lower() != city_name.lower():
        return jsonify({"success": False, "error": f"Access denied: You are only authorized for {user['username']} node."}), 403

    payload = request.get_json(silent=True) or request.form
    query_str = (payload.get("query") or "").strip()
    if not query_str:
        return jsonify({"success": False, "error": "Empty query"}), 400

    import ddbms_manager
    res = ddbms_manager.execute_node_query(city_name, query_str)
    return jsonify(res)


# ─────────────────────────────────────────────────────────────────────────────
# TIER 3: GLOBAL MASTER OPERATIONS DASHBOARD & ADMIN SUITE (Admin Only)
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/dashboard")
def admin_dashboard():
    """
    Master Nationwide Live Operations Dashboard (Admin Only).
    Shows nationwide ingestion, deduplication engine, and India Map across all 10 cities.
    """
    user = get_current_user()
    if not user or user["role"] != "admin":
        if user and user["role"] == "user":
            return redirect(f"/portal/{user['username']}")
        elif user and user["role"] == "city":
            return redirect(f"/city/{user['username']}")
        return redirect("/")
    return render_template("dashboard.html")

@app.route("/database")
def database():
    """Global raw database stream view (Admin Only)."""
    user = get_current_user()
    if not user or user["role"] != "admin":
        return redirect("/")
    return render_template("database.html")

@app.route("/batch_output")
def batch_output_page():
    """Batch output stream (Admin Only)."""
    user = get_current_user()
    if not user or user["role"] != "admin":
        return redirect("/")
    return render_template("batch_output.html")

@app.route("/summary")
def summary_page():
    """Plaza station summary (Admin Only)."""
    user = get_current_user()
    if not user or user["role"] != "admin":
        return redirect("/")
    return render_template("summary.html")

@app.route("/api/batch_output")
def api_batch_output():
    """Returns the latest deduplicated journeys from batch output."""
    import json
    import os
    if os.path.exists("batch_output.json"):
        with open("batch_output.json", "r") as f:
            try:
                data = json.load(f)
                return jsonify({"data": data[::-1][:100]})
            except Exception:
                return jsonify({"data": []})
    return jsonify({"data": []})

@app.route("/api/batch_summary")
def api_batch_summary():
    """Returns plaza-level aggregation from batch output."""
    import json
    import os
    if os.path.exists("batch_output.json"):
        with open("batch_output.json", "r") as f:
            try:
                data = json.load(f)
                summary = {}
                for j in data:
                    pid = j.get("plaza_id", "Unknown")
                    if pid not in summary:
                        summary[pid] = {
                            "region": j.get("region", "Unknown"),
                            "clean_journeys": 0,
                            "duplicates_filtered": 0
                        }
                    summary[pid]["clean_journeys"] += 1
                    summary[pid]["duplicates_filtered"] += max(0, j.get("duplicate_count", 1) - 1)
                
                result = [{"plaza_id": k, **v} for k, v in summary.items()]
                result.sort(key=lambda x: x["clean_journeys"], reverse=True)
                return jsonify({"data": result})
            except Exception:
                pass
    return jsonify({"data": []})

@app.route("/api/portal/<username>/history")
def user_history(username):
    """API returning live SQL ledger data for the user."""
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    if user.get("role") == "user" and user.get("username", "").lower() != username.lower():
        return jsonify({"error": "Forbidden: Cannot access another user's data"}), 403

    data = sql_ledger.get_user_dashboard_data(username)
    if not data:
        return jsonify({"data": [], "wallet": {"current_balance": 0.0}})
    return jsonify({
        "data": data.get("journeys", []),
        "wallet": data.get("wallet", {}),
        "vehicles": data.get("vehicles", []),
        "full_name": data.get("full_name")
    })

@app.route("/api/wallet/recharge", methods=["POST"])
def recharge_wallet_api():
    """Atomically adds funds to user wallet."""
    user = get_current_user()
    if not user:
        return jsonify({"error": "User not authenticated"}), 401

    payload = request.get_json(silent=True) or request.form
    target_user_id = payload.get("user_id")

    # Enforce ownership: normal users can only recharge their own wallet
    if user.get("role") != "admin":
        user_id = user.get("user_id")
    else:
        user_id = target_user_id or user.get("user_id")

    try:
        amount = float(payload.get("amount", 500.0))
        if amount <= 0:
            return jsonify({"error": "Invalid recharge amount: must be positive"}), 400
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid recharge amount"}), 400

    if not user_id:
        return jsonify({"error": "User not authenticated"}), 401

    new_balance = sql_ledger.recharge_wallet(int(user_id), amount)
    return jsonify({"success": True, "new_balance": new_balance})

@app.route("/api/portal/<username>/export")
def export_user_statement(username):
    """Exports transaction statement as CSV for an owner (Task 6.2)."""
    user = get_current_user()
    if not user:
        return redirect("/")
    if user.get("role") == "user" and user.get("username", "").lower() != username.lower():
        return jsonify({"error": "Forbidden"}), 403

    data = sql_ledger.get_user_dashboard_data(username)
    if not data:
        return jsonify({"error": "User not found"}), 404

    import csv
    import io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Journey ID", "Timestamp", "Tag ID", "Plaza", "Highway", "Deducted (INR)", "Status", "Failure Reason"])
    for j in data.get("journeys", []):
        writer.writerow([
            j.get("journey_id"),
            j.get("timestamp"),
            j.get("tag_id"),
            j.get("plaza_name"),
            j.get("highway_name"),
            f"{j.get('deducted_amount', 0):.2f}",
            j.get("payment_status"),
            j.get("failure_reason") or ""
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=FASTag_Statement_{username}.csv"}
    )

@app.route("/api/tag/toggle", methods=["POST"])
def toggle_tag_api():
    """Toggles RFID tag between ACTIVE and BLOCKED (Task 6.3)."""
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    payload = request.get_json(silent=True) or request.form
    tag_id = payload.get("tag_id")
    if not tag_id:
        return jsonify({"error": "Missing tag_id"}), 400

    user_id = user.get("user_id") if user.get("role") != "admin" else None
    result = sql_ledger.toggle_rfid_tag_status(user_id, tag_id)
    return jsonify(result), (200 if result.get("success") else 400)

@app.route("/api/stream")
def sse_stats_stream():
    """Server-Sent Events (SSE) streaming live telemetry stats (Task 3.6)."""
    def event_stream():
        while True:
            try:
                dedup_results = dedup_worker.get_results()
                with chaos_lock:
                    chaos_active = chaos_state["active"]
                payload = {
                    "total_raw_pings": storage.get_total_ingested(),
                    "total_deduplicated_journeys": dedup_results["total_journeys"],
                    "dedup_ratio": dedup_results["last_dedup_ratio"],
                    "pings_per_second": storage.get_throughput_pps(),
                    "chaos_mode": chaos_active,
                    "last_dedup_run": dedup_results["last_run_at"],
                    "last_raw_count": dedup_results["last_raw_count"],
                    "last_journey_count": dedup_results["last_journey_count"],
                }
                yield f"data: {json.dumps(payload)}\n\n"
            except Exception:
                pass
            time.sleep(0.5)

    return Response(event_stream(), mimetype="text/event-stream")

@app.route("/sql_ledger")
def sql_ledger_view():
    """Inspect all 6 relational tables and ACID transactions live (Admin Only)."""
    user = get_current_user()
    if not user or user["role"] != "admin":
        return redirect("/")
    tables_data = sql_ledger.get_all_tables_data()
    return render_template("sql_ledger.html", tables=tables_data)

@app.route("/api/sql_ledger")
def api_sql_ledger():
    """Returns raw JSON of all 6 relational tables for live polling."""
    return jsonify(sql_ledger.get_all_tables_data())

@app.route("/sql_console")
def sql_console_view():
    """Interactive SQL query execution terminal for the central global database (Admin Only)."""
    user = get_current_user()
    if not user or user["role"] != "admin":
        return redirect("/")
    schema_info = sql_ledger.get_schema_info()
    return render_template("sql_console.html", schema=schema_info)

@app.route("/api/sql/execute", methods=["POST"])
def api_sql_execute():
    """Execute arbitrary SQL queries against the global database (Admin Only)."""
    user = get_current_user()
    if not user or user.get("role") != "admin":
        return jsonify({"success": False, "error": "Unauthorized: Admin access required."}), 403
    payload = request.get_json(silent=True) or request.form
    query_str = payload.get("query", "").strip()
    result = sql_ledger.execute_raw_query(query_str)
    return jsonify(result)

@app.route("/api/sql/schema")
def api_sql_schema():
    """Returns live schema metadata and row counts for all tables."""
    return jsonify(sql_ledger.get_schema_info())

@app.route("/ddbms")
def ddbms_view():
    """DDBMS Architecture, Fragmentation Catalog & 2PC Visualizer (Admin & City Engineers)."""
    user = get_current_user()
    if not user or user["role"] == "user":
        return redirect("/")
    import ddbms_manager
    catalog = ddbms_manager.get_ddbms_catalog()
    return render_template("ddbms_architecture.html", catalog=catalog, user=user)

@app.route("/error_log")
def error_log_view():
    """Security & Operational Alert Log (Admin & City Engineers)."""
    user = get_current_user()
    if not user or user["role"] == "user":
        return redirect("/")
    logs = sql_ledger.get_security_error_logs(limit=100)
    return render_template("error_log.html", logs=logs, user=user)

@app.route("/api/error_log")
def api_error_log():
    """Returns live JSON of failed journeys and security alerts for real-time polling."""
    alert_type = request.args.get("type")
    try:
        limit = int(request.args.get("limit", 100))
    except (ValueError, TypeError):
        limit = 100
    logs = sql_ledger.get_security_error_logs(limit=limit, alert_type=alert_type)
    return jsonify(logs)

@app.route("/api/ddbms/catalog")
def api_ddbms_catalog():
    """Returns live distributed fragmentation catalog metadata."""
    import ddbms_manager
    return jsonify(ddbms_manager.get_ddbms_catalog())

@app.route("/api/ddbms/query", methods=["POST"])
def api_ddbms_query():
    """
    Executes a federated or targeted distributed query with transparent execution plan.
    Target can be 'FEDERATED' (Scatter-Gather) or a specific node (e.g. 'CHENNAI').
    """
    user = get_current_user()
    if not user or user["role"] == "user":
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    payload = request.get_json(silent=True) or request.form
    query_str = (payload.get("query") or "").strip()
    target = (payload.get("target") or "FEDERATED").strip().upper()

    if not query_str:
        return jsonify({"success": False, "error": "Empty query"}), 400

    import ddbms_manager
    if target == "COORDINATOR":
        # Run on central coordinator master database
        res = sql_ledger.execute_raw_query(query_str)
        res["execution_plan"] = {
            "strategy": "Coordinator Master Scan (Single Site)",
            "active_nodes": ["COORDINATOR_MASTER_01"],
            "pruned_nodes": list(ddbms_manager.CITIES_METADATA.keys()),
            "steps": [
                {"step": 1, "phase": "Coordinator Execution", "detail": "Executed directly on central SQLite WAL database (fastag_ledger.db)."}
            ]
        }
        return jsonify(res)
    else:
        res = ddbms_manager.execute_distributed_federated_query(query_str, target=target)
        return jsonify(res)

@app.route("/api/ddbms/reconstruct", methods=["GET"])
def api_ddbms_reconstruct():
    """Demonstrates vertical fragmentation reconstruction via lossless join."""
    import ddbms_manager
    limit = int(request.args.get("limit", 15))
    return jsonify(ddbms_manager.demonstrate_vertical_reconstruction(limit=limit))





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

    # Wipe previous batch output on startup to keep data fresh
    import os
    if os.path.exists("batch_output.json"):
        try:
            os.remove("batch_output.json")
        except OSError:
            pass

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

