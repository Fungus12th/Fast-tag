# 🚗 FASTag Distributed Toll Reconciliation Ledger & DDBMS

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Architecture: DDBMS](https://img.shields.io/badge/Architecture-DDBMS%20%7C%203NF%20ACID-0284c7.svg)](#-distributed-database-management-system-ddbms)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![UI: Sky/Ice Blue SaaS](https://img.shields.io/badge/UI-Sky%2FIce%20Blue%20Vanilla%20SaaS-0ea5e9.svg)](#-user-interface--screens)

A production-grade, distributed IoT ingestion, stream deduplication, and ACID relational financial ledger system modeling India’s **National Electronic Toll Collection (NETC FASTag)** infrastructure. 

The system transitions millions of noisy, high-frequency radio sensor telemetry pings into verifiable banking transactions, architected as a full **Distributed Database Management System (DDBMS)** with autonomous regional edge nodes, horizontal and vertical fragmentation, and federated query processing.

---

## 🏗️ 4-Layer Architecture Overview

```
                       HIGH-FREQUENCY IoT SENSORS (RFID PINGS)
           [ Delhi ]   [ Mumbai ]   [ Chennai ]   [ Bengaluru ]   [ Kolkata ] ...
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ LAYER 1: INGESTION TIER (NoSQL / In-Memory Ring Buffers)                    │
│ • Lock-protected deque ring buffer (100k cap) / Cassandra cluster fallback  │
│ • Sustained ingestion: 1,800–2,500+ pings/sec with sub-millisecond writes   │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ LAYER 2: STREAM DEDUPLICATION ENGINE (Windowed Spatial/Temporal Grouping)  │
│ • 10-second sliding time window aggregation                                │
│ • Filters 98–99% sensor noise; extracts winning ping via max RSSI (dBm)     │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ LAYER 3: 3NF RELATIONAL ACID LEDGER (Central Coordinator Master)            │
│ • SQLite WAL Mode: fastag_ledger.db                                         │
│ • BEGIN IMMEDIATE atomic transaction boundaries with CHECK balance guards   │
│ • Dynamic vehicle multipliers (Car 1.0x, Bus 2.0x, Truck 3.0x)             │
│ • Spatiotemporal fraud detection ("Impossible Travel" / Cloned Tag Alert)   │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │ (2PC Replicate / Scatter)
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ LAYER 4: DISTRIBUTED DATABASE MANAGEMENT SYSTEM (DDBMS CORE)                │
│ • 10 Physical Regional Edge Node DBs: data/nodes/<city>_node.db             │
│ • Primary Horizontal Fragmentation: σ(region='CITY')(Journeys)              │
│ • Vertical Fragmentation: Edge Operational Fragment vs Central Financial    │
│ • Distributed Query Processor (DQP): Predicate pushdown & node pruning      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🌐 Distributed Database Management System (DDBMS)

### 1. Primary Horizontal Fragmentation ($\sigma$)
The logical relations `Journeys` and `Toll_Plazas` are partitioned across **10 physical regional node databases** in `data/nodes/<city>_node.db`:
$$\text{Journeys}_{\text{City}_i} = \sigma_{\text{region} = \text{City}_i}(\text{Journeys})$$
- **Disjointness Guaranteed:** $\text{Journeys}_i \cap \text{Journeys}_j = \emptyset$ (for $i \neq j$).
- **Completeness Guaranteed:** $\text{Journeys} = \bigcup_{i=1}^{10} \text{Journeys}_{\text{City}_i}$.

### 2. Vertical Fragmentation ($\pi$) & Lossless Join
To simulate edge-computing security and latency requirements, vehicle profiles are decomposed into:
- **Operational Edge Fragment (`Edge_Tags_Cache`)**:
  $$\pi_{\text{tag\_id, registration\_no, vehicle\_class, status, home\_region}}(\text{Vehicles} \bowtie \text{RFID\_Tags})$$
  Replicated on local regional nodes (`data/nodes/<city>_node.db`) to enable sub-millisecond RFID gate verification without exposing user personal data or bank balances at highway booths.
- **Central Financial Fragment**:
  $$\pi_{\text{user\_id, full\_name, phone\_number, current\_balance}}(\text{Users} \bowtie \text{Wallet\_Ledgers})$$
  Maintained strictly on the Central Coordinator node (`fastag_ledger.db`).
- **Lossless Join Reconstruction ($\bowtie$)**:
  $$\text{Full\_Vehicle\_Profile} = \text{Edge\_Tags\_Cache} \bowtie_{\text{tag\_id}} \text{Central\_Financial\_Fragment}$$

### 3. Distributed Query Processor (DQP)
The query engine parses global SQL and executes:
1. **Query Decomposition & Localization:** Translates logical queries into local fragment operations (`Journeys` $\to$ `Journeys_Local`).
2. **Predicate Pushdown & Node Pruning:** Automatically identifies selection predicates (e.g. `WHERE region = 'CHENNAI'`), prunes non-matching nodes, and targets the specific edge node directly.
3. **Parallel Asynchronous Scatter:** Broadcasts subqueries across regional WAL databases concurrently via a thread pool.
4. **Distributed Gather & Merge:** Unions fragments and renders a transparent **Distributed Execution Plan** showing node latencies and pruning statistics.

---

## 🔐 Multi-Tier Role-Based Access Control (RBAC)

The application provides a unified login portal at `/login` with strict role segregation:

| Role | Demo Credentials | Scope & Accessible Views |
| :--- | :--- | :--- |
| **Global Admin** | `admin` / `admin123` | Master operations across all 10 cities, Global SQL Console with DQP, 3NF Ledger Inspector, DDBMS Architecture visualizer. |
| **City Station Officers** | `chennai` / `chennai123`<br>`mumbai` / `mumbai123`<br>`delhi` / `delhi123`<br>*(10 cities available)* | Confined strictly to `/city/<city_name>`. Dedicated **Local Node SQL Query Terminal** directly bound to `data/nodes/<city>_node.db`. Barred from accessing other cities. |
| **Vehicle Owners** | `priya` / `priya123`<br>`ravi` / `ravi123`<br>`amit` / `amit123`<br>*(10 owners available)* | Confined strictly to `/portal/<username>`. Personal wallet balance, RFID asset management, vehicle class badges, and personal journey history. Zero admin access. |

---

## 🚀 Quickstart Guide

### 1. Prerequisites
- Python 3.10+
- Linux, macOS, or Windows WSL

### 2. Setup Virtual Environment & Dependencies
```bash
git clone https://github.com/Fungus12th/Fast-tag.git
cd Fast-tag

python3 -m venv .venv
source .venv/bin/activate
pip install flask cassandra-driver requests jinja2
```

### 3. Start the Ingestion & DDBMS Server
```bash
# Starts server on port 5000 (or pass FASTAG_PORT=5001)
python app.py
```
*On first boot, the database automatically initializes the seed data: 10 vehicle owners, 30 mixed-class vehicles, 30 RFID tags, 30 toll plazas across 10 cities, and all 10 regional edge databases.*

### 4. Start the Traffic Load Generator
In a separate terminal window:
```bash
source .venv/bin/activate

# Stream high-frequency RFID pings across all 10 Indian cities
python generator.py --server 127.0.0.1 --port 5000 --region ALL --workers 2 --batch 200 --delay 0.3
```

---

## 🖥️ User Interface & Screens

- **Live Nationwide Dashboard (`/dashboard`):** Real-time throughput graph (Chart.js), deduplication noise reduction gauge, interactive 10-city India Toll Plaza radar map canvas with pulse rings, and sortable per-plaza metrics.
- **DDBMS Architecture Visualizer (`/ddbms`):** Live topology map cards (Coordinator $\leftrightarrow$ 10 Regional Nodes), horizontal fragmentation catalog table, interactive Lossless Join Reconstructor widget, and 4-phase DQP breakdown.
- **Global SQL Console (`/sql_console`):** Target Node Selector (`COORDINATOR` vs `FEDERATED` vs 10 individual edge nodes), Viva-ready analytical presets, dark slate editor, and real-time visual Distributed Execution Plan (DQP) visualizer.
- **City Station Node (`/city/<city_name>`):** Local station metrics, local plaza breakdown, Vertical Edge Fragment table (`Edge_Tags_Cache`), and embedded interactive Local Node SQL Query Terminal.
- **Vehicle Owner Portal (`/portal/<username>`):** Sky/Ice blue gradient wallet card with atomic instant top-up buttons, vehicle RFID asset chips, and real-time transaction ledger.
- **3NF SQL Ledger (`/sql_ledger`):** Interactive segmented tab inspector across all 6 relational tables (`Users`, `Wallet_Ledgers`, `Vehicles`, `RFID_Tags`, `Toll_Plazas`, `Journeys`).

---

## 📚 Deep-Dive Technical Documentation

For complete mathematical models, schema normalization proofs, and core code implementations:
- [📖 **Backend Architecture Deep Dive** (`docs/BACKEND_ARCHITECTURE.md`)](docs/BACKEND_ARCHITECTURE.md)
- [🎨 **Frontend Architecture Deep Dive** (`docs/FRONTEND_ARCHITECTURE.md`)](docs/FRONTEND_ARCHITECTURE.md)

---

## 🛡️ License

This project is licensed under the [MIT License](LICENSE).
