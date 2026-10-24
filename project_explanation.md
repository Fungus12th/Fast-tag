# FASTag High-Frequency Ingestion, Deduplication & ACID Reconciliation Ledger

> **Document Purpose:** Complete architectural, schema, algorithmic, and programmatic specification of the FASTag Polyglot Persistence system. Designed for human evaluation (viva/presentation) and as structured system context for AI agents to understand, parse, and scaffold new capabilities.

---

## 1. Executive Summary & Problem Formulation

### 1.1 The Core Problem
In real-world electronic toll collection (e.g., India's National Electronic Toll Collection / FASTag network), vehicles idling at a toll barrier are scanned multiple times per second by overhead RFID readers.
* **Volume:** Network-wide peak throughput comfortably exceeds **10,000+ sensor pings/second**.
* **Noise:** A vehicle waiting 10 seconds at a boom barrier generates 50–200 duplicate pings with fluctuating Radio Signal Strength Indicators (RSSI: -25 dBm to -65 dBm).
* **The Conflict:** High-velocity write workloads require append-only, lock-free NoSQL ingestion stores. Conversely, financial billing requires strict **ACID transactional integrity**, non-negative balance constraints, and 3NF referential guarantees. A single relational database engine would suffer lock contention, deadlock, or crash under this raw IoT write velocity.

### 1.2 The Polyglot Persistence Solution
This project implements a **Three-Layer Polyglot Persistence Architecture**:
1. **Layer 1: High-Speed Ingestion (NoSQL / Edge Stream):** Absorbs raw telemetry at wire speed, partitioned by `plaza_id`.
2. **Layer 2: Reconciliation & Batch ETL (Deduplication Engine):** Periodically extracts recent time windows, eliminates redundant reads, and identifies the physical crossing event by selecting the strongest RSSI reading.
3. **Layer 3: Financial Ledger Core (Strict 3NF ACID Relational SQL):** Executes atomic wallet deductions and appends immutable audit records into relational storage (`fastag_ledger.db`), enforcing zero negative balances and handling suspended/blocked tags safely.

```
+-----------------------------------------------------------------------------------------+
|                                LAYER 1: INGESTION (EDGE)                                |
|  Delhi Edge (Place1..4)      Chennai Edge (Place1..3)      Mumbai Edge (Place1..4)      |
|  [generator.py]              [generator.py]                [generator.py]               |
|            \                         |                         /                        |
|             \                        |                        /                         |
|              +-----------------------+-----------------------+                          |
|                                      | Batched HTTP POSTs (500+ pings/req)              |
|                                      v                                                  |
|                        Flask API Ingest (/api/ingest)                                   |
|                        Raw Storage: Cassandra / Memory buffer                           |
+-----------------------------------------------------------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------------------+
|                                LAYER 2: RECONCILIATION                                  |
|  [deduplicator.py - BatchDeduplicator]                                                   |
|  • Sliding time-window analysis (30s–60s)                                               |
|  • Group by (tag_id, plaza_id)                                                          |
|  • Filter algorithm: Max RSSI signal strength (closest to antenna)                      |
|  • Noise reduction: ~90–95% duplicate elimination                                        |
+-----------------------------------------------------------------------------------------+
                                       |
                                       v Clean Journeys (1 per physical passage)
+-----------------------------------------------------------------------------------------+
|                             LAYER 3: ACID FINANCIAL LEDGER                              |
|  [sql_ledger.py - fastag_ledger.db (SQLite WAL Mode, Foreign Keys = ON)]                |
|  • Atomic Stored Procedure: Process_Toll_Batch(tag_id, plaza_id, timestamp)             |
|  • 3NF Relational Tables:                                                               |
|    - Users (user_id PK, username UNIQUE, full_name, phone_number)                       |
|    - Wallet_Ledgers (ledger_id PK, user_id FK, current_balance CHECK >= 0.00)           |
|    - Vehicles (registration_no PK, user_id FK, vehicle_class)                           |
|    - RFID_Tags (tag_id PK, registration_no FK, status CHECK ACTIVE/BLOCKED)             |
|    - Toll_Plazas (plaza_id PK, plaza_name, highway_name, base_toll_rate)                 |
|    - Journeys (journey_id PK, tag_id FK, plaza_id FK, deducted_amount, payment_status)   |
|  • UI & Access:                                                                         |
|    - Main Live Dashboard (/)                                                            |
|    - Owner Portal & Login (/login, /portal/<username>)                                  |
|    - 3NF Schema Inspector (/sql_ledger)                                                 |
|    - Global Database SQL Terminal Console (/sql_console)                                |
+-----------------------------------------------------------------------------------------+
```

---

## 2. Relational Database Schema & Data Models (Layer 3)

The financial ledger satisfies **Third Normal Form (3NF)**:
* **1NF:** All attributes hold atomic, indivisible values.
* **2NF:** Every non-key attribute depends entirely on the primary key (no composite partial dependencies).
* **3NF:** No transitive dependencies exist. Toll rates reside solely in `Toll_Plazas`; wallet balances reside solely in `Wallet_Ledgers`.

### 2.1 Complete SQL DDL Specification
```sql
-- 1. Identity & Credentials
CREATE TABLE Users (
    user_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    username      VARCHAR(50) UNIQUE NOT NULL,
    password      VARCHAR(100) NOT NULL,
    full_name     VARCHAR(100) NOT NULL,
    phone_number  VARCHAR(15) UNIQUE NOT NULL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Financial Balance (ACID protected, strictly non-negative)
CREATE TABLE Wallet_Ledgers (
    ledger_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER UNIQUE NOT NULL,
    current_balance DECIMAL(10,2) NOT NULL CHECK (current_balance >= 0.00),
    last_updated    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE CASCADE
);

-- 3. Vehicle Asset
CREATE TABLE Vehicles (
    registration_no VARCHAR(20) PRIMARY KEY,
    user_id         INTEGER NOT NULL,
    vehicle_class   VARCHAR(10) NOT NULL,   -- e.g., 'Car', 'Truck', 'Bus'
    FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE CASCADE
);

-- 4. Physical FASTag Transponder Bonded to Vehicle
CREATE TABLE RFID_Tags (
    tag_id          VARCHAR(50) PRIMARY KEY,
    registration_no VARCHAR(20) UNIQUE NOT NULL,
    status          VARCHAR(15) NOT NULL CHECK (status IN ('ACTIVE','BLOCKED','REPLACED')),
    issued_date     DATE NOT NULL,
    FOREIGN KEY (registration_no) REFERENCES Vehicles(registration_no) ON DELETE CASCADE
);

-- 5. Toll Plaza Master Data & Pricing
CREATE TABLE Toll_Plazas (
    plaza_id       INTEGER PRIMARY KEY,
    plaza_name     VARCHAR(100) UNIQUE NOT NULL,
    highway_name   VARCHAR(50) NOT NULL,
    base_toll_rate DECIMAL(8,2) NOT NULL
);

-- 6. Immutable Financial Transaction & Audit Log
CREATE TABLE Journeys (
    journey_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    tag_id          VARCHAR(50) NOT NULL,
    plaza_id        INTEGER NOT NULL,
    timestamp       TIMESTAMP NOT NULL,
    deducted_amount DECIMAL(8,2) NOT NULL,
    payment_status  VARCHAR(15) NOT NULL CHECK (payment_status IN ('SUCCESS','PENDING','FAILED')),
    failure_reason  VARCHAR(100),
    FOREIGN KEY (tag_id)   REFERENCES RFID_Tags(tag_id),
    FOREIGN KEY (plaza_id) REFERENCES Toll_Plazas(plaza_id)
);
```

---

## 3. Atomic Transaction Logic: `Process_Toll_Batch`

Reconciliation between clean sensor events and money deduction is performed via an atomic transaction function defined in `sql_ledger.py`:

```python
def process_toll_batch(tag_id: str, plaza_ref: str, timestamp_str: str) -> dict:
    # 1. Lookup Plaza toll rate
    SELECT plaza_id, base_toll_rate FROM Toll_Plazas WHERE plaza_id = ? OR plaza_name = ?;
    
    # 2. Join Tag -> Vehicle -> User -> Wallet to verify status and balance
    SELECT u.user_id, w.current_balance, t.status
    FROM RFID_Tags t
    JOIN Vehicles v ON t.registration_no = v.registration_no
    JOIN Users u ON v.user_id = u.user_id
    JOIN Wallet_Ledgers w ON u.user_id = w.user_id
    WHERE t.tag_id = ?;

    # 3. Decision Tree:
    IF status != 'ACTIVE':
        # Safe Failure Edge Case: Tag is BLOCKED or suspended
        INSERT INTO Journeys VALUES (DEFAULT, tag_id, plaza_id, timestamp, 0.00, 'FAILED', 'Tag BLOCKED');
        # Wallet is NOT touched
        RETURN {"status": "FAILED", "reason": "RFID Tag is BLOCKED"}

    ELIF current_balance < toll_rate:
        # Safe Failure Edge Case: Insufficient wallet balance
        INSERT INTO Journeys VALUES (DEFAULT, tag_id, plaza_id, timestamp, 0.00, 'FAILED', 'Insufficient Balance');
        # Wallet is NOT touched
        RETURN {"status": "FAILED", "reason": "Insufficient Wallet Balance"}

    ELSE:
        # SUCCESS PATH: Single Atomic Transaction
        BEGIN IMMEDIATE TRANSACTION;
            UPDATE Wallet_Ledgers
            SET current_balance = current_balance - toll_rate,
                last_updated = CURRENT_TIMESTAMP
            WHERE user_id = user_id;

            INSERT INTO Journeys VALUES (DEFAULT, tag_id, plaza_id, timestamp, toll_rate, 'SUCCESS', NULL);
        COMMIT;
        RETURN {"status": "SUCCESS", "deducted": toll_rate}
```

### 3.1 Handled Edge Cases
* **Blocked RFID Tag:** Tag `Car3Amit` is explicitly seeded with `status = 'BLOCKED'`. When scanned at any toll plaza, it is refused safely: a `FAILED` record is logged into `Journeys`, but no money is debited.
* **Insufficient Balance:** If an account balance falls below the plaza rate (e.g. `Place1Mumbai` = ₹120.00 vs ₹85.00 balance), the transaction is refused before the balance can breach the `CHECK (current_balance >= 0.00)` barrier.
* **Idempotency:** Repeated raw pings from the same passage are filtered at Layer 2 before triggering the transaction logic.

---

## 4. Default Seed Data (The 3 Owners & 9 Vehicles)

To enable predictable demonstration and testing, the system is seeded with exactly 3 owners and 9 vehicles:

| User | Username / Password | Phone Number | Initial Balance | Vehicles & FASTag IDs | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Ravi Kumar** | `ravi` / `ravi123` | `+91-9876543210` | ₹1,500.00 | `Car1Ravi`, `Car2Ravi`, `Car3Ravi` | All `ACTIVE` |
| **Priya Sharma** | `priya` / `priya123` | `+91-9812345678` | ₹1,200.00 | `Car1Priya`, `Car2Priya`, `Car3Priya` | All `ACTIVE` |
| **Amit Patel** | `amit` / `amit123` | `+91-9900112233` | ₹85.00 | `Car1Amit` (ACTIVE), `Car2Amit` (ACTIVE), `Car3Amit` (**BLOCKED**) | Edge case test |

### Toll Plazas Registry:
* **Delhi Region:** `Place1Delhi` (NH-44, ₹95), `Place2Delhi` (Delhi-Meerut Expy, ₹85), `Place3Delhi` (NH-48, ₹105), `Place4Delhi` (Kundli-Manesar Expy, ₹115)
* **Chennai Region:** `Place1Chennai` (GST Road, ₹75), `Place2Chennai` (OMR IT Corridor, ₹65), `Place3Chennai` (NH-16, ₹90)
* **Mumbai Region:** `Place1Mumbai` (Mumbai-Pune Expy, ₹120), `Place2Mumbai` (Eastern Freeway, ₹80), `Place3Mumbai` (Bandra-Worli Sealink, ₹95), `Place4Mumbai` (NH-66, ₹110)

---

## 5. Codebase Manifest & Key Files

| File | Role / Responsibility |
| :--- | :--- |
| `app.py` | Central Flask server. Hosts REST endpoints (`/api/ingest`, `/api/stats`, `/api/chaos`, `/api/sql/execute`), session authentication, and HTML page routes. |
| `sql_ledger.py` | SQLite 3NF relational layer. Creates the 6 tables, seeds demo accounts, executes atomic transactions (`process_toll_batch`), and executes arbitrary SQL queries for the console. |
| `deduplicator.py` | Sliding-window batch deduplicator (`BatchDeduplicator`). Gathers raw pings, identifies maximum RSSI signals, and forwards clean journeys to `sql_ledger.process_toll_batch`. |
| `generator.py` | Multi-threaded client-side load generator. Supports batched HTTP POSTs, regional plaza targeting (`--region DELHI/CHENNAI/MUMBAI`), and time-bucketed "chaos logic" (vehicles taking breaks). |
| `owners.py` | Mapping dictionary defining the 3 owners and 9 vehicle tag IDs. |
| `config.py` | Server, Cassandra, deduplication window, and throughput configuration parameters. |
| `db.py` | Polyglot storage abstraction layer. Automatically selects Apache Cassandra when available or falls back to high-throughput In-Memory storage. |
| `templates/index.html` | High-aesthetic live operations dashboard (dark/emerald theme, throughput charts, India toll map, dedup ratio gauge). |
| `templates/login.html` | Owner Portal login page with username/password inputs and 1-click test credentials buttons. |
| `templates/user_dashboard.html` | Authenticated owner dashboard showing live wallet balance, top-up/recharge buttons, asset status, and immutable journey table. |
| `templates/sql_ledger.html` | Relational 3NF database visualizer with tabs for all 6 tables, primary/foreign key badges, and live record inspection. |
| `templates/sql_console.html` | Interactive web-based SQL Query Terminal allowing arbitrary query execution, execution timing in milliseconds, schema viewer, and 1-click preset queries. |

---

## 6. API Route Reference

### Ingestion & Telemetry
* `POST /api/ingest`: Accepts array of raw pings `{"pings": [{tag_id, plaza_id, rssi_signal_strength, ping_timestamp, lane_id, region}]}`.
* `GET /api/stats`: Returns live ingestion count, pings/sec, clean journeys, deduplication ratio, and top active plazas.
* `GET /api/chaos/status`: Returns chaos multiplier status.
* `POST /api/chaos/trigger`: Activates 10x throughput chaos mode for stress-testing.

### Deduplication & Database
* `POST /api/dedup/trigger`: Manually runs the deduplication worker immediately.
* `GET /api/database/tail`: Streams the most recent raw NoSQL pings ingested.

### Authentication & Owner Portal
* `GET /login` / `POST /login`: Session-based authentication verifying credentials via `sql_ledger.authenticate_user`.
* `GET /logout`: Clears session and redirects to login.
* `GET /portal/<username>`: Renders user profile, vehicle list, wallet balance, and recent toll deductions.
* `GET /api/portal/<username>/history`: Returns real-time JSON of user wallet and journey log for dashboard polling.
* `POST /api/wallet/recharge`: Atomically credits funds (`{"user_id": 1, "amount": 500}`) to a wallet ledger.

### Global SQL Database Console
* `GET /sql_ledger`: Renders interactive visual tables for all 6 3NF schema tables.
* `GET /api/sql_ledger`: Returns raw JSON of all 6 relational tables.
* `GET /sql_console`: Renders interactive SQL Query Terminal.
* `POST /api/sql/execute`: Executes arbitrary raw SQL query against `fastag_ledger.db` and returns execution time, columns, and rows.
* `GET /api/sql/schema`: Returns metadata (table names, column types, primary keys, and live row counts).

---

## 7. Distributed Multi-Laptop Execution Setup

The system is designed to run across multiple physical machines on the same local Wi-Fi or mobile hotspot:

### 1. Machine 1 (Central Hub / Boss Server)
Runs the central Flask backend and hosts the global database:
```bash
./.venv/bin/python app.py
```
*Accessible on local network via:* `http://<MACHINE_1_IP>:5000`

Optionally generates local Delhi regional traffic:
```bash
./.venv/bin/python generator.py --server 127.0.0.1 --region DELHI --workers 2
```

### 2. Machine 2 (Client / Edge Simulator - Mumbai)
```bash
./.venv/bin/python generator.py --server <MACHINE_1_IP> --region MUMBAI --workers 2
```

### 3. Machine 3 (Client / Edge Simulator - Chennai)
```bash
./.venv/bin/python generator.py --server <MACHINE_1_IP> --region CHENNAI --workers 2
```

All 3 machines stream independent regional telemetry into Machine 1, which performs deduplication and updates the centralized SQL ledger in real time.

---

## 8. AI Prompting Blueprint (System Context for LLMs)

When feeding this project to an AI assistant or prompting an LLM to generate extensions, use the following structured prompt block:

```markdown
You are an expert distributed systems and database engineer acting as a co-developer for the FASTag Polyglot Persistence Project.

Core Architecture Constraints:
1. Three Layers:
   - Layer 1: High-throughput raw IoT ingestion (generator.py -> app.py).
   - Layer 2: Time-window batch deduplication selecting the highest RSSI ping (deduplicator.py).
   - Layer 3: ACID relational financial ledger in strict 3NF (sql_ledger.py, fastag_ledger.db).
2. Schema Invariants:
   - Exactly 6 relational tables: Users, Wallet_Ledgers, Vehicles, RFID_Tags, Toll_Plazas, Journeys.
   - Wallet balance must NEVER be negative (enforced by CHECK (current_balance >= 0.00)).
   - Blocked tags (e.g., Car3Amit) and insufficient funds must trigger safe failure (Journey logged as 'FAILED', wallet balance left untouched).
   - All monetary amounts are in INR (DECIMAL(10,2) or DECIMAL(8,2)).
3. Multi-Node Simulation:
   - Edge sensors are partitioned by region (DELHI, MUMBAI, CHENNAI).
   - Exactly 9 fixed demo vehicles across 3 owners (Ravi, Priya, Amit).
   - Generators run asynchronously on edge nodes while committing to the central database.

When designing or modifying code for this repository:
- Maintain full compatibility with the existing SQLite WAL database and Flask REST routes.
- Preserve 3NF normalization; never introduce redundant financial fields.
- Ensure all database writes pass through atomic transaction boundaries.
```


---

## 9. Scaled Architecture v2 (10 Users, 30 Vehicles, 10 Metros & Security Hardening)

### 9.1 Network-Scale Expansion
* **10 Account Holders:** Ravi Kumar, Priya Sharma, Amit Patel, Sneha Reddy, Vikram Singh, Ananya Das, Rohan Mehta, Kavita Joshi, Arjun Nair, Meera Iyer.
* **30 Vehicles & FASTags:** Exactly 3 vehicles per user with realistic class distribution:
  * Standard Passenger (`Car`): 1.0× base toll.
  * Commercial Passenger (`Bus`): 2.0× base toll.
  * Heavy Freight (`Truck`): 3.0× base toll.
* **30 Plazas Across 10 Indian Metros:**
  * **New Delhi:** `Place1Delhi` (NH-44), `Place2Delhi` (Delhi-Meerut Expy), `Place3Delhi` (NH-48)
  * **Kolkata:** `Place1Kolkata` (NH-16), `Place2Kolkata` (NH-19), `Place3Kolkata` (Kolkata-Durgapur Expy)
  * **Mumbai:** `Place1Mumbai` (Mumbai-Pune Expy), `Place2Mumbai` (Eastern Freeway), `Place3Mumbai` (Bandra-Worli)
  * **Bengaluru:** `Place1Bengaluru` (NICE Road), `Place2Bengaluru` (NH-44 South), `Place3Bengaluru` (Bengaluru-Mysuru Expy)
  * **Chennai:** `Place1Chennai` (Grand Southern Trunk), `Place2Chennai` (OMR IT Corridor), `Place3Chennai` (NH-16 East)
  * **Hyderabad:** `Place1Hyderabad` (ORR), `Place2Hyderabad` (NH-65), `Place3Hyderabad` (Hyderabad-Vijayawada)
  * **Ahmedabad:** `Place1Ahmedabad` (NH-48 West), `Place2Ahmedabad` (Ahmedabad-Vadodara Expy), `Place3Ahmedabad` (SG Highway)
  * **Surat:** `Place1Surat` (NH-48 Surat), `Place2Surat` (Diamond Bridge Expy), `Place3Surat` (Surat-Hazira Road)
  * **Pune:** `Place1Pune` (NH-48 Pune), `Place2Pune` (Pune-Satara NH), `Place3Pune` (Pune-Bengaluru Expy)
  * **Jaipur:** `Place1Jaipur` (Delhi-Jaipur Expy), `Place2Jaipur` (NH-48 Jaipur), `Place3Jaipur` (Jaipur Ring Road)

### 9.2 Reliability & Security Features
1. **Dynamic Vehicle Class Pricing:**
   `toll_rate = base_toll_rate * {"Car": 1.0, "Bus": 2.0, "Truck": 3.0}[vehicle_class]`
   Enforces equitable road pricing without breaking 3NF normalization.
2. **Spatiotemporal Fraud Detection ("Impossible Travel"):**
   During `Process_Toll_Batch`, the database checks the vehicle's last recorded passage. If the same tag appears in a different city within less than 2.0 hours (e.g., Delhi to Chennai in 10 seconds), the transaction is immediately rejected and recorded as:
   `FAILED (Suspected Tag Cloning: {LastCity}→{CurrentCity} in {Gap}h)`
3. **Database Concurrency & Idempotency Hardening:**
   * `BEGIN IMMEDIATE` is acquired before reading the wallet balance, eliminating race conditions across parallel batch deduplication runs.
   * `idx_journey_idempotent` unique index on `Journeys(tag_id, plaza_id, timestamp)` with `INSERT OR IGNORE` guarantees that network retries or duplicated worker executions never double-charge an account.
4. **SQL Console Read-Only Sandbox:**
   The web query terminal (`/sql_console`) enforces a whitelist guard (`SELECT`, `PRAGMA`, `EXPLAIN`, `WITH`), protecting the live database from destructive DDL/DML operations (`DROP`, `DELETE`, `UPDATE`) during public demonstrations.
