# FASTag DA-2 — Project Division into 3 Parts

---

## Part 1: Backend & Database Foundation
**Owner focus:** Server infrastructure, database, and API layer.

**Covers:**
- **Cassandra Setup** — Install and configure Cassandra on Laptop 1. Create the `FASTag_Telemetry` keyspace and `Raw_RFID_Pings` table with the partition-by-`plaza_id` + cluster-by-`ping_timestamp` schema.
- **Flask Web Server (`app.py`)** — Build the Flask backend that:
  - Serves the frontend dashboard (static files).
  - Exposes API endpoints for the dashboard to query live stats (total pings, deduplicated journeys, per-plaza breakdown, throughput rate).
  - Exposes a `/ingest` endpoint (or batch endpoint) that the load generators POST data to.
  - Exposes a `/chaos` signal endpoint so the dashboard's "Peak Traffic" button can broadcast to all connected generators.
- **Batch Deduplication Worker** — Implement the deduplication logic that:
  - Runs on a configurable interval (10–60 seconds).
  - Scans the recent time window in Cassandra, groups pings by `tag_id`, selects the row with the highest `rssi_signal_strength`.
  - Returns the massive reduction stats (e.g., "45,000 raw → 842 journeys") to the dashboard via API.
- **Cross-laptop network verification** — Confirm that Laptop 1's Flask server is reachable at `http://<Laptop_1_IP>:5000` from other laptops over the private hotspot.

**Maps to Plan Phases:** Phase 1 (backend portion), Phase 2, Phase 4.

---

## Part 2: Frontend Dashboard & Visualizations
**Owner focus:** Everything the audience *sees* — the full UI/UX.

**Covers:**
- **Dark-themed hacker-aesthetic HTML/CSS layout** — Structure the dashboard with all panels:
  - Hero counters (top) for "Total Raw Pings Ingested" and "Clean Deduplicated Journeys" — big, fast-spinning animated numbers.
  - Deduplication Ratio Gauge — donut/gauge chart showing noise reduction percentage in real-time.
  - Live Throughput Chart (center) — real-time Chart.js line chart for "Pings Per Second."
  - Per-Plaza Breakdown Panel — sidebar/table showing busiest plaza, most duplicates, most blocked tags.
  - Live Event Feed (bottom) — scrolling log of deduplicated vehicles with `tag_id`, `plaza_name`, `signal_strength`, timestamp.
- **India Toll Plaza Map** — SVG or Leaflet.js map of India with toll plaza dots that pulse/glow proportionally to incoming traffic. Each laptop's region lights up independently (North / South / West).
- **Interactive Controls:**
  - 🔴 **"Simulate Peak Traffic (Diwali Weekend)" button** — sends the chaos signal to the server, which broadcasts to all generators.
  - Configurable dedup interval slider/dropdown to trigger the batch worker.
- **Sound Effects (optional)** — accelerating "ping" sounds with ingestion rate; "ka-ching" on deduplication cycle completion.
- **JS polling/WebSocket layer** — Frontend JS that fetches live data from the Flask API endpoints and updates all charts, counters, and map in real-time.

**Maps to Plan Phases:** Phase 1 (frontend portion), Phase 5.

---

## Part 3: Load Generators & Demo Orchestration
**Owner focus:** Data simulation, multi-laptop coordination, and the live demo rehearsal.

**Covers:**
- **`generator.py` script** — Build the Python load generator that:
  - Uses **batching** (arrays of 500+ pings per request) to bypass network I/O limits and hit 10,000+ pings/sec across all laptops.
  - Simulates realistic RFID data — random `tag_id`s with purposeful duplicates and fluctuating `rssi_signal_strength` to mimic vehicles idling at a toll barrier.
  - Assigns each laptop a geographic **plaza region** (North / South / West) so the map lights up as each teammate joins.
  - Listens for the **Chaos Mode signal** from the server — when the "Peak Traffic" button is pressed, the generator 10x's its throughput immediately.
- **Multi-laptop deployment** — Ensure `generator.py` runs cleanly on Laptops 2 & 3 with only Python installed (no Cassandra needed). Configure the target server IP as a CLI argument or config variable.
- **Demo Rehearsal & Timing** — Own the full 6-act demo script:
  - Act 1 (The Calm) → Act 2 (First Wave — Laptop 1) → Act 3 (The Flood — Laptops 2 & 3 join) → Act 4 (The Filter — trigger dedup) → Act 5 (Chaos Test — 10x spike) → Act 6 (Kill Switch — kill Laptop 3, system survives).
  - Time the full run to fit the presentation slot.
  - Run the 3-laptop stress test on the private hotspot. Identify and fix any network/performance bottlenecks.

**Maps to Plan Phases:** Phase 3, Phase 6.

---

## Summary Table

| Part | Scope | Key Deliverables | Plan Phases |
|------|-------|-----------------|-------------|
| **1 — Backend & DB** | Server, database, APIs, dedup logic | `app.py`, Cassandra schema, dedup worker, API endpoints | 1 (backend), 2, 4 |
| **2 — Frontend & Viz** | Dashboard UI, charts, map, controls | HTML/CSS/JS dashboard, Chart.js graphs, India map, sound FX | 1 (frontend), 5 |
| **3 — Generators & Demo** | Data simulation, multi-laptop, rehearsal | `generator.py`, chaos mode, 3-laptop stress test, demo timing | 3, 6 |

> **Tip:** The three parts are designed to be **developed in parallel** with minimal blocking. Part 1 can expose mock API responses while Part 2 builds the UI, and Part 3 can test against the `/ingest` endpoint as soon as it's live. The integration point is the Flask API contract — agree on the JSON shapes early and everyone can work independently.
