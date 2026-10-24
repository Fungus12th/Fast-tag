# FASTag Project — Implementation Plan v2

> **Purpose:** This is a step-by-step implementation plan for AI coding agents (Flash 3.8, OpenCode, etc.) to execute against the FASTag codebase. Each task includes the exact file to modify, what to change, and acceptance criteria. Execute tasks in order — later tasks depend on earlier ones.

> **CRITICAL RULES FOR IMPLEMENTING AGENTS:**
> - Read `project_explanation.md` in the repo root FIRST for full architectural context.
> - NEVER delete or overwrite existing comments/docstrings unrelated to your changes.
> - ALL monetary amounts are in INR, stored as `DECIMAL(10,2)` or `DECIMAL(8,2)`.
> - ALL database writes MUST go through atomic transaction boundaries.
> - The SQLite database file is `fastag_ledger.db` in the repo root.
> - Templates use Jinja2 (Flask). JS template literals (backticks) inside HTML templates MUST be escaped or placed in `<script>` blocks carefully.
> - After completing all tasks, run `python3 app.py` and verify every route loads without errors.

---

## TASK 1: Scale Up Seed Data — 10 Owners, 30 Cars, 10 Cities

### 1A. Update `owners.py`

Replace the current 3-owner dictionary with 10 owners, each owning 3 cars. Use this exact data:

```python
OWNER_DATA = {
    "owner1":  {"name": "Ravi Kumar",       "username": "ravi",     "cars": ["Car1Ravi",    "Car2Ravi",    "Car3Ravi"]},
    "owner2":  {"name": "Priya Sharma",     "username": "priya",    "cars": ["Car1Priya",   "Car2Priya",   "Car3Priya"]},
    "owner3":  {"name": "Amit Patel",       "username": "amit",     "cars": ["Car1Amit",    "Car2Amit",    "Car3Amit"]},
    "owner4":  {"name": "Sneha Reddy",      "username": "sneha",    "cars": ["Car1Sneha",   "Car2Sneha",   "Car3Sneha"]},
    "owner5":  {"name": "Vikram Singh",     "username": "vikram",   "cars": ["Car1Vikram",  "Car2Vikram",  "Car3Vikram"]},
    "owner6":  {"name": "Ananya Das",       "username": "ananya",   "cars": ["Car1Ananya",  "Car2Ananya",  "Car3Ananya"]},
    "owner7":  {"name": "Rohan Mehta",      "username": "rohan",    "cars": ["Car1Rohan",   "Car2Rohan",   "Car3Rohan"]},
    "owner8":  {"name": "Kavita Joshi",     "username": "kavita",   "cars": ["Car1Kavita",  "Car2Kavita",  "Car3Kavita"]},
    "owner9":  {"name": "Arjun Nair",       "username": "arjun",    "cars": ["Car1Arjun",   "Car2Arjun",   "Car3Arjun"]},
    "owner10": {"name": "Meera Iyer",       "username": "meera",    "cars": ["Car1Meera",   "Car2Meera",   "Car3Meera"]},
}

ALL_CARS = []
for info in OWNER_DATA.values():
    ALL_CARS.extend(info["cars"])
```

**Acceptance:** `len(ALL_CARS)` must equal 30.

---

### 1B. Update `sql_ledger.py` → `_seed_default_data()`

Replace the existing 3-user seed block with 10 users. Use these exact values:

**Users table** (user_id, username, password, full_name, phone_number):
| user_id | username | password | full_name | phone_number |
|---------|----------|----------|-----------|--------------|
| 1 | ravi | ravi123 | Ravi Kumar | +91-9876543210 |
| 2 | priya | priya123 | Priya Sharma | +91-9812345678 |
| 3 | amit | amit123 | Amit Patel | +91-9900112233 |
| 4 | sneha | sneha123 | Sneha Reddy | +91-9988776655 |
| 5 | vikram | vikram123 | Vikram Singh | +91-9871234567 |
| 6 | ananya | ananya123 | Ananya Das | +91-9865432100 |
| 7 | rohan | rohan123 | Rohan Mehta | +91-9823456789 |
| 8 | kavita | kavita123 | Kavita Joshi | +91-9845678901 |
| 9 | arjun | arjun123 | Arjun Nair | +91-9867890123 |
| 10 | meera | meera123 | Meera Iyer | +91-9889012345 |

**Wallet_Ledgers** (initial balances — deliberately varied for demo edge cases):
| user_id | current_balance | Notes |
|---------|----------------|-------|
| 1 | 2500.00 | Healthy |
| 2 | 1800.00 | Healthy |
| 3 | 75.00 | Low balance — will trigger FAILED after 1 cheap toll |
| 4 | 3000.00 | Healthy |
| 5 | 1200.00 | Mid-range |
| 6 | 500.00 | Will run out after a few tolls |
| 7 | 4000.00 | High balance |
| 8 | 150.00 | Low — edge case territory |
| 9 | 2200.00 | Healthy |
| 10 | 900.00 | Mid-range |

**Vehicles** (registration_no, user_id, vehicle_class):
- Each user gets 3 vehicles. **Mix vehicle classes** for realistic pricing:
  - Car1{Name}: `vehicle_class = "Car"`
  - Car2{Name}: `vehicle_class = "Car"` (for users 1-5), `vehicle_class = "Bus"` (for users 6-10)
  - Car3{Name}: `vehicle_class = "Car"` (for users 1-3,6-8), `vehicle_class = "Truck"` (for users 4,5,9,10)

Use registration number format:
- Ravi: `TN-01-AB-1001`, `TN-01-AB-1002`, `TN-01-AB-1003`
- Priya: `DL-03-CD-2001`, `DL-03-CD-2002`, `DL-03-CD-2003`
- Amit: `MH-02-EF-3001`, `MH-02-EF-3002`, `MH-02-EF-3003`
- Sneha: `KA-05-GH-4001`, `KA-05-GH-4002`, `KA-05-GH-4003`
- Vikram: `RJ-14-JK-5001`, `RJ-14-JK-5002`, `RJ-14-JK-5003`
- Ananya: `WB-06-LM-6001`, `WB-06-LM-6002`, `WB-06-LM-6003`
- Rohan: `GJ-01-NP-7001`, `GJ-01-NP-7002`, `GJ-01-NP-7003`
- Kavita: `GJ-05-QR-8001`, `GJ-05-QR-8002`, `GJ-05-QR-8003`
- Arjun: `KL-01-ST-9001`, `KL-01-ST-9002`, `KL-01-ST-9003`
- Meera: `AP-09-UV-0001`, `AP-09-UV-0002`, `AP-09-UV-0003`

**RFID_Tags**: Same `CarX{Name}` tag IDs as in `owners.py`. Set ALL tags to `status = 'ACTIVE'` EXCEPT:
- `Car3Amit` → `'BLOCKED'` (existing edge case — blocked tag)
- `Car3Kavita` → `'BLOCKED'` (second blocked tag for variety)

---

### 1C. Update `sql_ledger.py` → `_seed_default_data()` — Toll Plazas

Replace the existing plaza list with plazas across **10 cities** (3-4 plazas per city). Use plaza_id starting from 201:

| plaza_id | plaza_name | highway_name | base_toll_rate | City |
|----------|-----------|--------------|---------------|------|
| 201 | Place1Delhi | NH-44 | 95.00 | New Delhi |
| 202 | Place2Delhi | Delhi-Meerut Expy | 85.00 | New Delhi |
| 203 | Place3Delhi | NH-48 | 105.00 | New Delhi |
| 204 | Place1Kolkata | NH-16 | 70.00 | Kolkata |
| 205 | Place2Kolkata | NH-19 | 80.00 | Kolkata |
| 206 | Place3Kolkata | Kolkata-Durgapur Expy | 90.00 | Kolkata |
| 207 | Place1Mumbai | Mumbai-Pune Expy | 120.00 | Mumbai |
| 208 | Place2Mumbai | Eastern Freeway | 80.00 | Mumbai |
| 209 | Place3Mumbai | Bandra-Worli Sealink | 95.00 | Mumbai |
| 210 | Place1Bengaluru | NICE Road | 85.00 | Bengaluru |
| 211 | Place2Bengaluru | NH-44 South | 75.00 | Bengaluru |
| 212 | Place3Bengaluru | Bengaluru-Mysuru Expy | 110.00 | Bengaluru |
| 213 | Place1Chennai | Grand Southern Trunk | 75.00 | Chennai |
| 214 | Place2Chennai | OMR IT Corridor | 65.00 | Chennai |
| 215 | Place3Chennai | NH-16 East | 90.00 | Chennai |
| 216 | Place1Hyderabad | ORR Hyderabad | 60.00 | Hyderabad |
| 217 | Place2Hyderabad | NH-65 | 85.00 | Hyderabad |
| 218 | Place3Hyderabad | Hyderabad-Vijayawada | 100.00 | Hyderabad |
| 219 | Place1Ahmedabad | NH-48 West | 70.00 | Ahmedabad |
| 220 | Place2Ahmedabad | Ahmedabad-Vadodara Expy | 95.00 | Ahmedabad |
| 221 | Place3Ahmedabad | SG Highway | 55.00 | Ahmedabad |
| 222 | Place1Surat | NH-48 Surat | 65.00 | Surat |
| 223 | Place2Surat | Diamond Bridge Expy | 75.00 | Surat |
| 224 | Place3Surat | Surat-Hazira Road | 60.00 | Surat |
| 225 | Place1Pune | NH-48 Pune | 90.00 | Pune |
| 226 | Place2Pune | Pune-Satara NH | 80.00 | Pune |
| 227 | Place3Pune | Pune-Bengaluru Expy | 105.00 | Pune |
| 228 | Place1Jaipur | Delhi-Jaipur Expy | 100.00 | Jaipur |
| 229 | Place2Jaipur | NH-48 Jaipur | 85.00 | Jaipur |
| 230 | Place3Jaipur | Jaipur Ring Road | 60.00 | Jaipur |

---

### 1D. Update `generator.py` → `PLAZA_REGISTRY`

Replace the existing `PLAZA_REGISTRY` dictionary with:

```python
PLAZA_REGISTRY = {
    "DELHI":      ["Place1Delhi", "Place2Delhi", "Place3Delhi"],
    "KOLKATA":    ["Place1Kolkata", "Place2Kolkata", "Place3Kolkata"],
    "MUMBAI":     ["Place1Mumbai", "Place2Mumbai", "Place3Mumbai"],
    "BENGALURU":  ["Place1Bengaluru", "Place2Bengaluru", "Place3Bengaluru"],
    "CHENNAI":    ["Place1Chennai", "Place2Chennai", "Place3Chennai"],
    "HYDERABAD":  ["Place1Hyderabad", "Place2Hyderabad", "Place3Hyderabad"],
    "AHMEDABAD":  ["Place1Ahmedabad", "Place2Ahmedabad", "Place3Ahmedabad"],
    "SURAT":      ["Place1Surat", "Place2Surat", "Place3Surat"],
    "PUNE":       ["Place1Pune", "Place2Pune", "Place3Pune"],
    "JAIPUR":     ["Place1Jaipur", "Place2Jaipur", "Place3Jaipur"],
}
```

Also update the `argparse` `--region` choices to include ALL new city names plus `"ALL"`.

### 1E. Update `templates/index.html` → `KNOWN_PLAZAS`

Search for the `KNOWN_PLAZAS` JavaScript object/array in `index.html` and add ALL 30 new plaza names to it so they appear on the live map/dashboard. Match the exact plaza names used in the generator and SQL seed data.

### 1F. Update `templates/login.html`

The current login page has 3 quick-login buttons (Ravi, Priya, Amit). Expand the demo grid to show all 10 users as quick-login buttons. Change the grid CSS from `grid-template-columns: repeat(3, 1fr)` to `repeat(5, 1fr)` so they fit in 2 rows of 5.

**Acceptance for Task 1:** Delete `fastag_ledger.db`, run `python3 -c "import sql_ledger; sql_ledger.init_db(reset=True); print(sql_ledger.get_schema_info())"` — verify 10 users, 30 vehicles, 30 tags (28 ACTIVE + 2 BLOCKED), 30 plazas, 0 journeys.

---

## TASK 2: Fix Race Condition in `process_toll_batch`

**File:** `sql_ledger.py` → `process_toll_batch()`

**Current bug:** The function does `SELECT current_balance` first, THEN opens `BEGIN IMMEDIATE TRANSACTION` only for the success path. Under concurrent dedup threads, two threads can read the same balance simultaneously and both deduct.

**Fix:** Move `conn.execute("BEGIN IMMEDIATE;")` to the very top of the function, BEFORE the plaza lookup and wallet SELECT queries. Remove the existing `conn.execute("BEGIN IMMEDIATE;")` from the success path (it's now at the top). Ensure `conn.commit()` is called in ALL three exit paths (blocked, insufficient, success) and `conn.rollback()` in the except block.

**Acceptance:** The entire read→decide→write cycle is enclosed in a single `BEGIN IMMEDIATE` transaction.

---

## TASK 3: Add Idempotency Guard on Journeys Table

**File:** `sql_ledger.py` → `init_db()`

After the `CREATE TABLE IF NOT EXISTS Journeys` statement, add:

```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_journey_idempotent
ON Journeys(tag_id, plaza_id, timestamp);
```

Then change ALL `INSERT INTO Journeys` statements inside `process_toll_batch()` from `INSERT INTO` to `INSERT OR IGNORE INTO`.

**Acceptance:** If the same (tag_id, plaza_id, timestamp) combination is processed twice, the second insert is silently ignored instead of creating a duplicate billing record.

---

## TASK 4: Lock Down the SQL Console (Read-Only Mode)

**File:** `sql_ledger.py` → `execute_raw_query()`

At the top of the function, after stripping the query string, add a safety check:

```python
# Only allow read-only operations from the web console
query_upper = query_clean.upper().lstrip()
allowed_prefixes = ("SELECT", "PRAGMA", "EXPLAIN", "WITH")
if not query_upper.startswith(allowed_prefixes):
    return {
        "success": False,
        "error": "⛔ Write operations (INSERT, UPDATE, DELETE, DROP, ALTER) are disabled in the SQL Console for safety. Use the application endpoints instead."
    }
```

**Acceptance:** Attempting `DROP TABLE Users;` or `DELETE FROM Journeys;` from `/sql_console` returns a friendly error. SELECT queries continue working normally.

---

## TASK 5: Add Vehicle Class Pricing Multipliers

**File:** `sql_ledger.py` → `process_toll_batch()`

After looking up the `base_toll_rate` from `Toll_Plazas` and the tag/vehicle/user info, join `vehicle_class` from the Vehicles table (it's already available via the existing JOIN chain — just add `v.vehicle_class` to the SELECT).

Apply this multiplier before the balance check:

```python
CLASS_MULTIPLIER = {"Car": 1.0, "Bus": 2.0, "Truck": 3.0}
multiplier = CLASS_MULTIPLIER.get(vehicle_class, 1.0)
toll_rate = base_toll_rate * multiplier
```

This means:
- A Car crossing Place1Mumbai (₹120 base) pays ₹120.
- A Truck crossing Place1Mumbai pays ₹360.
- A Bus crossing Place1Mumbai pays ₹240.

**Acceptance:** Log in as a user who owns a Truck. Their journey deductions should be 3x the base rate shown in Toll_Plazas.

---

## TASK 6: Add Impossible Travel / Cloned Tag Fraud Detection

**File:** `sql_ledger.py` → `process_toll_batch()`

After confirming the tag is ACTIVE and before the balance check, add a fraud detection query:

```python
# Fraud Detection: Check for impossible travel (tag cloning)
cur.execute("""
    SELECT p.plaza_name, j.timestamp
    FROM Journeys j
    JOIN Toll_Plazas p ON j.plaza_id = p.plaza_id
    WHERE j.tag_id = ? AND j.payment_status = 'SUCCESS'
    ORDER BY j.journey_id DESC
    LIMIT 1;
""", (tag_id,))
last_journey = cur.fetchone()

if last_journey:
    last_plaza = last_journey["plaza_name"]
    last_time_str = last_journey["timestamp"]
    
    # Extract city from current plaza name and last plaza name
    # Plaza names are like "Place1Delhi", "Place2Mumbai" etc.
    import re
    def extract_city(plaza_name):
        match = re.search(r'Place\d+(.*)', plaza_name)
        return match.group(1) if match else plaza_name
    
    current_city = extract_city(current_plaza_name)  # need to fetch plaza_name for current plaza
    last_city = extract_city(last_plaza)
    
    if current_city != last_city:
        from datetime import datetime
        try:
            last_time = datetime.fromisoformat(last_time_str)
            current_time = datetime.fromisoformat(timestamp_str) if timestamp_str else datetime.now(timezone.utc)
            gap_hours = abs((current_time - last_time).total_seconds()) / 3600
            
            # If same tag appears in a different city within 2 hours — physically impossible
            if gap_hours < 2.0:
                cur.execute("""
                    INSERT OR IGNORE INTO Journeys (tag_id, plaza_id, timestamp, deducted_amount, payment_status, failure_reason)
                    VALUES (?, ?, ?, 0.00, 'FAILED', ?);
                """, (tag_id, plaza_id, timestamp_str, f"Suspected Tag Cloning: {last_city}→{current_city} in {gap_hours:.1f}h"))
                conn.commit()
                return {
                    "status": "FAILED",
                    "payment_status": "FAILED",
                    "tag_id": tag_id,
                    "deducted": 0.00,
                    "reason": f"Suspected Tag Cloning: {last_city}→{current_city} in {gap_hours:.1f}h"
                }
        except:
            pass  # If timestamp parsing fails, skip fraud check gracefully
```

**Note:** You will need to also fetch `plaza_name` alongside `plaza_id` and `base_toll_rate` in the initial plaza lookup query so it's available for city extraction.

**Acceptance:** When the generator is running with `--region ALL`, some cars will inevitably appear in two different cities within seconds. Their journeys should show up as `FAILED — Suspected Tag Cloning` in the user dashboard and SQL console.

---

## TASK 7: Update `project_explanation.md`

After all tasks are complete, append a new section to `project_explanation.md` documenting:
- The expanded 10-user, 30-vehicle, 10-city scale.
- Vehicle class pricing multiplier logic.
- Impossible travel fraud detection algorithm.
- Idempotency guard and race condition fix.
- SQL console read-only safety lock.

---

## TASK 8: Final Smoke Test Checklist

After all tasks are implemented, manually verify each of these:

1. `rm fastag_ledger.db && python3 app.py` → server starts, DB is created with 10 users, 30 vehicles, 30 plazas.
2. Open `http://localhost:5000/` → main dashboard loads, all 7 nav buttons visible (Live Database, Batch Output, Stations Summary, Owner Portal, 3NF SQL Ledger, SQL Console).
3. Open `http://localhost:5000/login` → 10 quick-login buttons visible in 2 rows of 5.
4. Login as `amit / amit123` → dashboard shows Car3Amit as BLOCKED, wallet at ₹75.
5. Login as `rohan / rohan123` → dashboard shows 3 vehicles, healthy wallet.
6. Start generator: `python3 generator.py --region ALL --workers 2` → pings flowing.
7. Wait 60 seconds → check Amit's dashboard: should see FAILED journeys (blocked tag + insufficient balance).
8. Open `/sql_console` → run preset "Blocked Tag Audit" → see FAILED rows with reasons.
9. Open `/sql_console` → try `DROP TABLE Users;` → must get blocked with friendly error.
10. Open `/sql_console` → run preset "Revenue by Toll Plaza" → all 30 plazas listed.
11. Open `/sql_console` → run `SELECT tag_id, failure_reason FROM Journeys WHERE failure_reason LIKE '%Cloning%';` → should see impossible travel detections (if generator ran with ALL regions).

---

## Execution Summary

| Task | File(s) | Estimated Time | Dependencies |
|------|---------|---------------|-------------|
| 1A | `owners.py` | 5 min | None |
| 1B | `sql_ledger.py` (seed data) | 15 min | 1A |
| 1C | `sql_ledger.py` (plazas) | 10 min | None |
| 1D | `generator.py` | 5 min | 1C |
| 1E | `templates/index.html` | 10 min | 1C |
| 1F | `templates/login.html` | 5 min | 1A |
| 2 | `sql_ledger.py` (race fix) | 5 min | None |
| 3 | `sql_ledger.py` (idempotency) | 5 min | None |
| 4 | `sql_ledger.py` (console lock) | 5 min | None |
| 5 | `sql_ledger.py` (class pricing) | 10 min | 1B |
| 6 | `sql_ledger.py` (fraud detect) | 15 min | 1C, 2 |
| 7 | `project_explanation.md` | 10 min | All above |
| 8 | Manual smoke test | 10 min | All above |
| **TOTAL** | | **~110 min** | |
