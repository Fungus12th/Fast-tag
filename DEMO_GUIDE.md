# 🚗 FASTag Distributed Reconciliation & DDBMS — Live Demonstration Guide

A complete walkthrough for presenting the FASTag system in a viva, classroom, or multi-laptop demonstration setting.

---

## 🏗️ Architecture & Demo Credentials Quick Reference

### Multi-Tier Role-Based Access Control (RBAC)
Navigate to `http://<SERVER_IP>:5000/login`:

| Tier | Role | Demo Credentials | Scope & Capabilities |
| :--- | :--- | :--- | :--- |
| **Tier 1** | **Global Admin** | `admin` / `admin123` | Nationwide Live Operations Dashboard (`/dashboard`), Global Distributed SQL Console with DQP (`/sql_console`), 3NF Schema Inspector (`/sql_ledger`), DDBMS Architecture visualizer (`/ddbms`). |
| **Tier 2** | **City Station Officers** | `delhi` / `delhi123`<br>`mumbai` / `mumbai123`<br>`chennai` / `chennai123`<br>*(all 10 cities)* | Confined strictly to `/city/<city>`. Local Edge Node database (`data/nodes/<city>_node.db`), Edge RFID tag cache, outcome and revenue charts, and dedicated Local Node SQL Terminal. |
| **Tier 3** | **Vehicle Owners** | `ravi` / `ravi123`<br>`priya` / `priya123`<br>`amit` / `amit123`<br>*(10 owners)* | Confined strictly to `/portal/<username>`. Real-time prepaid wallet, instant top-ups, vehicle RFID asset management (lock/unlock tags), filterable journey audit trail, and CSV statement download. |

### Network Scale
- **10 Metros:** Delhi, Mumbai, Kolkata, Bengaluru, Chennai, Hyderabad, Ahmedabad, Surat, Pune, Jaipur
- **30 Toll Plazas:** 3 regional plazas per metro (Plazas 201–230)
- **10 Vehicle Owners & 30 Vehicles:** Standard Cars (1.0×), Commercial Buses (2.0×), Heavy Freight Trucks (3.0×)
- **10 Autonomous Regional Node Databases:** Stored at `data/nodes/<city>_node.db`

---

## 🖥️ Multi-Laptop Hardware Setup

### Laptop 1 (Central Master Hub)
Runs the Central Flask Server and Coordinator Database:
```bash
python app.py
```
*Access on local Wi-Fi / Hotspot:* `http://<LAPTOP_1_IP>:5000`

### Laptop 2 (Client / Edge Simulator 1 — North & West Metros)
```bash
python generator.py --server <LAPTOP_1_IP> --region DELHI,JAIPUR,MUMBAI --workers 3 --batch 200 --delay 0.1
```

### Laptop 3 (Client / Edge Simulator 2 — South & East Metros)
```bash
python generator.py --server <LAPTOP_1_IP> --region CHENNAI,BENGALURU,HYDERABAD,KOLKATA --workers 3 --batch 200 --delay 0.1
```

*(Single-machine alternative: run generator locally with `--region ALL`)*:
```bash
python generator.py --server 127.0.0.1 --region ALL --workers 3 --batch 200 --delay 0.1
```

---

## 🎬 The 6-Act Live Demonstration Script

### Act 1 — Nationwide Operations & Calm (§1 min)
1. Project the **Nationwide Live Operations Dashboard** at `http://<LAPTOP_1_IP>:5000/dashboard` (logged in as `admin`).
2. Point out:
   - Real-time Chart.js telemetry throughput line chart.
   - Interactive 10-city radar map of India.
   - Per-plaza sortable breakdown panel.
   - Real-time Server-Sent Events (SSE) telemetry feed.

### Act 2 — The Traffic Flood & Noise Reduction (§1.5 min)
1. Start the generator scripts on Laptop 2 and Laptop 3.
2. Watch the India map markers light up red and pulse with Gaussian traffic intensity.
3. Observe raw telemetry climbing to **2,000–5,000+ pings/sec**.
4. Show the **Deduplication Ratio Gauge**:
   - Vehicles idling at booths send 50–200 redundant scans.
   - Layer 2 sliding window filters **90–98% noise**, extracting winning crossings via maximum RSSI signal strength (closest to antenna).

### Act 3 — ACID Financial Ledger & Edge Cases (§2 min)
1. Open the **Vehicle Owner Portal** at `/portal/amit` (login `amit` / `amit123`):
   - Notice Amit Patel's low starting balance (₹75.00).
   - Show `Car3Amit` status is **BLOCKED**.
   - Review recent transactions: show how `Tag BLOCKED` and `Insufficient Balance` safely reject toll passages with ₹0.00 deduction, preserving non-negative wallet constraints (`current_balance >= 0.00`).
2. Demonstrate **Instant Wallet Top-Up**:
   - Click `+ Top Up ₹500` or enter a custom amount (e.g., ₹750) and click Top Up.
   - Show immediate atomic balance update via `BEGIN IMMEDIATE` transaction.
3. Demonstrate **RFID Tag Lock/Unlock**:
   - Click `Lock 🔒` on an active vehicle tag; show status toggle to `BLOCKED`.
4. Demonstrate **Statement Download**:
   - Click `📥 Download Statement (.CSV)` to show CSV audit export.

### Act 4 — Spatiotemporal Fraud Detection ("Impossible Travel") (§1 min)
1. In the transaction ledger, point out tagged entries:
   `FAILED: Suspected Tag Cloning: DELHI→CHENNAI in 0.2h`
2. Explain the security guard in `sql_ledger.py`:
   - If the same RFID tag is scanned in two different cities less than 2 hours apart, the system rejects the passage as a suspected cloned transponder and flags security.

### Act 5 — Distributed Database (DDBMS) Architecture (§2 min)
1. Navigate to `/ddbms` (DDBMS Architecture Visualizer):
   - **Horizontal Fragmentation ($\sigma$):** Table `Journeys` fragmented across 10 physical SQLite WAL databases (`data/nodes/<city>_node.db`).
   - **Vertical Fragmentation ($\pi$):** Edge stations store only `Edge_Tags_Cache` (registration, class, status) without banking balances or user PII.
   - Click **"Verify Lossless Join Reconstruction"** to demonstrate:
     $$\text{Full Profile} = \text{Edge\_Tags\_Cache} \bowtie_{\text{tag\_id}} \text{Central\_Financial\_Fragment}$$

### Act 6 — Global Distributed SQL Console & Predicate Pruning (§2 min)
1. Navigate to `/sql_console`:
   - Show the CodeMirror syntax-highlighted dark SQL terminal with schema browser.
   - Click preset query: **"🎯 Predicate Pruning (Chennai)"**:
     ```sql
     SELECT * FROM Journeys WHERE region = 'CHENNAI' LIMIT 20;
     ```
   - Target: `FEDERATED`. Click **Execute Query ⚡**.
   - Show the **Distributed Execution Plan (DQP)**:
     - 1 Active Node (`CHENNAI`)
     - 9 Pruned Nodes (pruned at coordinator, avoiding network broadcasts)
     - Distributed Scatter-Gather latency breakdown.
2. Review local query history in the collapsible drawer.

---

## ⏱️ Recommended Viva / Presentation Timing

| Act | Focus | Key Concept | Duration |
| :--- | :--- | :--- | :--- |
| **Act 1** | Dashboard & Ingestion | Polyglot Ingestion Tier | 1.0 min |
| **Act 2** | Traffic Flood & Dedup | Windowed RSSI Noise Reduction | 1.5 min |
| **Act 3** | Owner Portal & ACID | 3NF Schema, Non-negative Check, RBAC | 2.0 min |
| **Act 4** | Fraud Detection | Spatiotemporal Cloned Tag Alert | 1.0 min |
| **Act 5** | DDBMS Visualizer | Horizontal/Vertical Fragmentation & Lossless Join | 2.0 min |
| **Act 6** | Distributed Query (DQP) | Predicate Pushdown, Node Pruning, Parallel Scatter | 2.0 min |
| **Total** | | | **~9.5 mins** |
