# FASTag DA-2: High-Frequency Ingestion & Deduplication Demo

## 1. Overview
The goal for DA-2 is to build a "bombastic" live demonstration of the **NoSQL Ingestion and Batch Deduplication** layers of the FASTag architecture. This proves the system can handle massive IoT traffic (10,000+ pings/sec) and filter out duplicates before the data ever touches the strict SQL financial ledger (which will be implemented in DA-3).

## 2. Hardware & Network Setup
To avoid university Wi-Fi throttling and TCP overhead bottlenecks, the demo will run on a **Private Mobile Hotspot** (no internet required, just local routing).

### Laptop 1 (The "Boss" Server)
* **Role:** The central hub receiving all traffic and serving the UI.
* **Runs:**
  1. **Cassandra Database:** Background service holding the data.
  2. **Flask Web Server (`app.py`):** Serves the dashboard and queries the DB.
  3. **Load Generator (`generator.py`):** Injects massive data locally.
* **Display:** Browser open to `http://localhost:5000` (projected to the class).

### Laptops 2 & 3 (The "Minion" Clients)
* **Role:** Traffic injectors and secondary displays.
* **Runs:**
  1. **Load Generator (`generator.py`):** Injects massive data over Wi-Fi.
* **Display:** Browser open to `http://<Laptop_1_IP>:5000` to watch the live dashboard.

> **Note:** Laptops 2 & 3 do NOT need Cassandra installed. They only need Python and the `generator.py` script.

## 3. Architecture Components

### A. The NoSQL Database (Cassandra)
* **Keyspace:** `FASTag_Telemetry`
* **Table:** `Raw_RFID_Pings`
* **Schema Design:** Partitioned by `plaza_id` (distributes load) and clustered by `ping_timestamp` (fast time-window queries).

### B. The Load Generators (`generator.py`)
* **Language:** Python
* **Strategy:** Uses **Batching** (sending arrays of 500+ pings at once) instead of individual requests to bypass network I/O limits.
* **Data Simulation:** Purposely generates duplicate `tag_id` scans with fluctuating `rssi_signal_strength` to mimic vehicles idling at a toll barrier.
* **Plaza Assignment:** Each laptop simulates a different geographic region (North, South, West) so the live map lights up as each teammate starts their script.
* **Chaos Mode:** The generator listens for a signal from the server. When the "Peak Traffic" button is pressed on the dashboard, all generators 10x their throughput simultaneously.

### C. The Web Dashboard (HTML/CSS/JS + Chart.js)
* **Design:** Dark-themed, hacker-aesthetic interface.
* **Served by:** Flask on Laptop 1, accessible by all laptops via `http://<Laptop_1_IP>:5000`.
* **Features:**
  * **Hero Counters (Top):** Massive, fast-spinning numbers for "Total Raw Pings Ingested" and "Clean Deduplicated Journeys."
  * **Deduplication Ratio Gauge:** A donut/gauge chart showing noise reduction in real-time (e.g., "93.2% duplicates filtered — only 6.8% real journeys"). This is the single most impressive stat.
  * **Live Throughput Chart (Center):** A real-time line chart (Chart.js) showing "Pings Per Second." As each laptop joins, the graph visibly spikes higher.
  * **India Toll Plaza Map:** An SVG/canvas map of India with toll plazas marked as dots. Dots pulse and glow proportionally to incoming traffic. Each laptop lights up a different region.
  * **Per-Plaza Breakdown Panel:** A sidebar/bottom table showing stats per toll plaza — busiest plaza, most duplicates, most blocked tags. Proves Cassandra's partition-by-`plaza_id` design works in practice.
  * **Live Event Feed (Bottom):** A scrolling log of "winning" deduplicated vehicles showing `tag_id`, `plaza_name`, `signal_strength`, and timestamp.
  * **🔴 "Simulate Peak Traffic" Button:** A big red button that tells all connected generators to 10x throughput simultaneously. Click it mid-demo, graphs spike violently, system handles it. Very dramatic.
  * **Sound Effects (Optional):** Subtle "ping" sounds that accelerate with ingestion rate. A "ka-ching" cash register sound when the batch worker completes a deduplication cycle. Sounds silly, but makes a live demo unforgettable.

### D. The Batch Worker / Deduplicator
* **Role:** Runs every 10-60 seconds (configurable from the dashboard).
* **Logic:** Scans the recent time window in Cassandra, groups by `tag_id`, and selects the row with the highest `rssi_signal_strength` (closest to antenna).
* **Output:** Displays the massive reduction (e.g., "45,000 raw pings → 842 billable journeys") directly on the dashboard. Journeys are held in temporary memory only — no permanent SQL storage yet (that's DA-3).

## 4. Demo Script (The "Show")

### Act 1: The Calm
* Open the dashboard on the projector. Everything is at zero. Explain the architecture briefly.

### Act 2: The First Wave
* Laptop 1 starts its generator. The map lights up in one region. The throughput chart starts climbing. The ping counter starts spinning.

### Act 3: The Flood
* Laptops 2 and 3 start their generators. Two more regions light up on the map. The throughput graph spikes dramatically. The audience watches the raw ping counter accelerate.

### Act 4: The Filter
* Trigger the Batch Worker from the dashboard. The deduplication gauge fills up — "94% noise eliminated." The journey count is a fraction of the raw pings. This is the payoff.

### Act 5: The Chaos Test
* Hit the "Simulate Peak Traffic (Diwali Weekend)" button. All generators go to 10x. The graphs spike violently. The system holds. The professor is impressed.

### Act 6: The Kill Switch (Fault Tolerance)
* Deliberately close the terminal on Laptop 3. One region on the map goes dark. The system keeps running perfectly with the remaining two. This demonstrates horizontal scalability and fault tolerance.

## 5. Execution Plan (Build Phases)
1. **Phase 1: UI & Backend Mockup.** Build the Flask server and HTML dashboard with simulated/fake data to nail the UI aesthetics and verify cross-laptop network access over the hotspot.
2. **Phase 2: Database Setup.** Install and configure Cassandra on Laptop 1; create the `FASTag_Telemetry` keyspace and `Raw_RFID_Pings` table.
3. **Phase 3: Load Generators.** Build `generator.py` with batching logic, plaza-region assignment, and chaos-mode listener.
4. **Phase 4: Deduplication Logic.** Implement the batch worker query that filters noise and hook real Cassandra data into the dashboard.
5. **Phase 5: Polish.** Add the map visualization, sound effects, and per-plaza breakdown panel.
6. **Phase 6: Rehearsal.** Run the full 3-laptop stress test on the private hotspot. Time the demo to fit your presentation slot.

## 6. Tech Stack Summary
| Component         | Technology                        |
| ----------------- | --------------------------------- |
| NoSQL Database    | Apache Cassandra                  |
| Backend Server    | Python + Flask                    |
| Frontend UI       | HTML/CSS/JS + Chart.js            |
| Load Generator    | Python (cassandra-driver library) |
| Network           | Mobile Hotspot (private LAN)      |
| Map Visualization | SVG or Leaflet.js (lightweight)   |
