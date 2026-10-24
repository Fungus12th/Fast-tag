"""
FASTag DA-3: SQL Financial Ledger Layer (3NF, ACID-Compliant)
=============================================================
Embedded zero-bloat SQLite relational storage implementing the exact
6-table schema and atomic transaction procedure specified in the DA-1/DA-2 design.
"""

import os
import re
import sqlite3
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from plaza_data import CITIES, ALL_PLAZA_ROWS, PLAZA_NAME_TO_CITY, PLAZA_ID_TO_CITY

DB_PATH = os.path.join(os.path.dirname(__file__), "fastag_ledger.db")

def get_connection():
    """Returns a SQLite connection with foreign key enforcement and WAL mode."""
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn

def init_db(reset: bool = False):
    """Initializes the 6 relational tables, idempotency index, and default seed data."""
    if reset and os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
        except OSError:
            pass

    conn = get_connection()
    cur = conn.cursor()

    # Table 1: Users
    cur.execute("""
    CREATE TABLE IF NOT EXISTS Users (
        user_id       INTEGER PRIMARY KEY AUTOINCREMENT,
        username      VARCHAR(50) UNIQUE NOT NULL,
        password      VARCHAR(255) NOT NULL,
        full_name     VARCHAR(100) NOT NULL,
        phone_number  VARCHAR(15) UNIQUE NOT NULL,
        created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Table 2: Wallet_Ledgers (with CHECK constraint for zero negative balance)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS Wallet_Ledgers (
        ledger_id       INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id         INTEGER UNIQUE NOT NULL,
        current_balance DECIMAL(10,2) NOT NULL CHECK (current_balance >= 0.00),
        last_updated    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE CASCADE
    );
    """)

    # Table 3: Vehicles
    cur.execute("""
    CREATE TABLE IF NOT EXISTS Vehicles (
        registration_no VARCHAR(20) PRIMARY KEY,
        user_id         INTEGER NOT NULL,
        vehicle_class   VARCHAR(10) NOT NULL,
        FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE CASCADE
    );
    """)

    # Table 4: RFID_Tags
    cur.execute("""
    CREATE TABLE IF NOT EXISTS RFID_Tags (
        tag_id          VARCHAR(50) PRIMARY KEY,
        registration_no VARCHAR(20) UNIQUE NOT NULL,
        status          VARCHAR(15) NOT NULL CHECK (status IN ('ACTIVE','BLOCKED','REPLACED')),
        issued_date     DATE NOT NULL,
        FOREIGN KEY (registration_no) REFERENCES Vehicles(registration_no) ON DELETE CASCADE
    );
    """)

    # Table 5: Toll_Plazas (Task 4.3: Added region column)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS Toll_Plazas (
        plaza_id       INTEGER PRIMARY KEY,
        plaza_name     VARCHAR(100) UNIQUE NOT NULL,
        highway_name   VARCHAR(50) NOT NULL,
        base_toll_rate DECIMAL(8,2) NOT NULL,
        region         VARCHAR(30) NOT NULL DEFAULT 'DELHI'
    );
    """)

    # Table 6: Journeys (Append-only financial audit log)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS Journeys (
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
    """)

    # Idempotency index to prevent double charging
    cur.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS idx_journey_idempotent
    ON Journeys(tag_id, plaza_id, timestamp);
    """)

    conn.commit()

    # Seed Default Data if empty
    cur.execute("SELECT COUNT(*) AS cnt FROM Users;")
    if cur.fetchone()["cnt"] == 0:
        _seed_default_data(cur)
        conn.commit()
    else:
        # Migrate any unhashed passwords
        cur.execute("SELECT user_id, password FROM Users;")
        unhashed = [(u["user_id"], u["password"]) for u in cur.fetchall() if not u["password"].startswith(("scrypt:", "pbkdf2:"))]
        for uid, plain in unhashed:
            cur.execute("UPDATE Users SET password = ? WHERE user_id = ?;", (generate_password_hash(plain), uid))
        if unhashed:
            conn.commit()

        # Migrate Toll_Plazas to ensure region column exists (Task 4.3)
        cur.execute("PRAGMA table_info(Toll_Plazas);")
        col_names = [col["name"] for col in cur.fetchall()]
        if "region" not in col_names:
            cur.execute("ALTER TABLE Toll_Plazas ADD COLUMN region VARCHAR(30) NOT NULL DEFAULT 'DELHI';")
            for pid, pname, hwy, rate, reg in ALL_PLAZA_ROWS:
                cur.execute("UPDATE Toll_Plazas SET region = ? WHERE plaza_id = ?;", (reg, pid))
            conn.commit()

    conn.close()

    # Initialize / Synchronize Distributed Regional Nodes (DDBMS)
    try:
        import ddbms_manager
        ddbms_manager.init_all_nodes(reset=reset)
    except Exception as ddbms_err:
        print(f"[DDBMS] Warning initializing nodes: {ddbms_err}")

def _seed_default_data(cur):
    """Populates 10 owners, their 30 cars/tags across classes, and 30 toll plazas."""
    # 1. 10 Users
    users = [
        (1,  "ravi",   generate_password_hash("ravi123"),   "Ravi Kumar",   "+91-9876543210"),
        (2,  "priya",  generate_password_hash("priya123"),  "Priya Sharma", "+91-9812345678"),
        (3,  "amit",   generate_password_hash("amit123"),   "Amit Patel",   "+91-9900112233"),
        (4,  "sneha",  generate_password_hash("sneha123"),  "Sneha Reddy",  "+91-9988776655"),
        (5,  "vikram", generate_password_hash("vikram123"), "Vikram Singh", "+91-9871234567"),
        (6,  "ananya", generate_password_hash("ananya123"), "Ananya Das",   "+91-9865432100"),
        (7,  "rohan",  generate_password_hash("rohan123"),  "Rohan Mehta",  "+91-9823456789"),
        (8,  "kavita", generate_password_hash("kavita123"), "Kavita Joshi", "+91-9845678901"),
        (9,  "arjun",  generate_password_hash("arjun123"),  "Arjun Nair",   "+91-9867890123"),
        (10, "meera",  generate_password_hash("meera123"),  "Meera Iyer",   "+91-9889012345"),
    ]
    cur.executemany("INSERT INTO Users (user_id, username, password, full_name, phone_number) VALUES (?, ?, ?, ?, ?);", users)

    # 2. 10 Wallets (Varied for demo edge cases)
    wallets = [
        (1,  2500.00),
        (2,  1800.00),
        (3,  75.00),    # Low balance: will fail after 1 cheap toll
        (4,  3000.00),
        (5,  1200.00),
        (6,  500.00),   # Low-mid balance
        (7,  4000.00),
        (8,  150.00),   # Low balance
        (9,  2200.00),
        (10, 900.00),
    ]
    cur.executemany("INSERT INTO Wallet_Ledgers (user_id, current_balance) VALUES (?, ?);", wallets)

    # 3. 30 Vehicles with mixed classes (Car, Bus, Truck)
    vehicles = [
        # Ravi (1)
        ("TN-01-AB-1001", 1, "Car"),
        ("TN-01-AB-1002", 1, "Car"),
        ("TN-01-AB-1003", 1, "Car"),
        # Priya (2)
        ("DL-03-CD-2001", 2, "Car"),
        ("DL-03-CD-2002", 2, "Car"),
        ("DL-03-CD-2003", 2, "Car"),
        # Amit (3)
        ("MH-02-EF-3001", 3, "Car"),
        ("MH-02-EF-3002", 3, "Car"),
        ("MH-02-EF-3003", 3, "Car"),
        # Sneha (4)
        ("KA-05-GH-4001", 4, "Car"),
        ("KA-05-GH-4002", 4, "Car"),
        ("KA-05-GH-4003", 4, "Truck"),
        # Vikram (5)
        ("RJ-14-JK-5001", 5, "Car"),
        ("RJ-14-JK-5002", 5, "Car"),
        ("RJ-14-JK-5003", 5, "Truck"),
        # Ananya (6)
        ("WB-06-LM-6001", 6, "Car"),
        ("WB-06-LM-6002", 6, "Bus"),
        ("WB-06-LM-6003", 6, "Car"),
        # Rohan (7)
        ("GJ-01-NP-7001", 7, "Car"),
        ("GJ-01-NP-7002", 7, "Bus"),
        ("GJ-01-NP-7003", 7, "Car"),
        # Kavita (8)
        ("GJ-05-QR-8001", 8, "Car"),
        ("GJ-05-QR-8002", 8, "Bus"),
        ("GJ-05-QR-8003", 8, "Car"),
        # Arjun (9)
        ("KL-01-ST-9001", 9, "Car"),
        ("KL-01-ST-9002", 9, "Bus"),
        ("KL-01-ST-9003", 9, "Truck"),
        # Meera (10)
        ("AP-09-UV-0001", 10, "Car"),
        ("AP-09-UV-0002", 10, "Bus"),
        ("AP-09-UV-0003", 10, "Truck"),
    ]
    cur.executemany("INSERT INTO Vehicles (registration_no, user_id, vehicle_class) VALUES (?, ?, ?);", vehicles)

    # 4. 30 RFID Tags (Car3Amit and Car3Kavita are BLOCKED for edge case testing)
    today = datetime.now().date().isoformat()
    tags = [
        ("Car1Ravi",    "TN-01-AB-1001", "ACTIVE",  today),
        ("Car2Ravi",    "TN-01-AB-1002", "ACTIVE",  today),
        ("Car3Ravi",    "TN-01-AB-1003", "ACTIVE",  today),
        ("Car1Priya",   "DL-03-CD-2001", "ACTIVE",  today),
        ("Car2Priya",   "DL-03-CD-2002", "ACTIVE",  today),
        ("Car3Priya",   "DL-03-CD-2003", "ACTIVE",  today),
        ("Car1Amit",    "MH-02-EF-3001", "ACTIVE",  today),
        ("Car2Amit",    "MH-02-EF-3002", "ACTIVE",  today),
        ("Car3Amit",    "MH-02-EF-3003", "BLOCKED", today),  # Edge case 1
        ("Car1Sneha",   "KA-05-GH-4001", "ACTIVE",  today),
        ("Car2Sneha",   "KA-05-GH-4002", "ACTIVE",  today),
        ("Car3Sneha",   "KA-05-GH-4003", "ACTIVE",  today),
        ("Car1Vikram",  "RJ-14-JK-5001", "ACTIVE",  today),
        ("Car2Vikram",  "RJ-14-JK-5002", "ACTIVE",  today),
        ("Car3Vikram",  "RJ-14-JK-5003", "ACTIVE",  today),
        ("Car1Ananya",  "WB-06-LM-6001", "ACTIVE",  today),
        ("Car2Ananya",  "WB-06-LM-6002", "ACTIVE",  today),
        ("Car3Ananya",  "WB-06-LM-6003", "ACTIVE",  today),
        ("Car1Rohan",   "GJ-01-NP-7001", "ACTIVE",  today),
        ("Car2Rohan",   "GJ-01-NP-7002", "ACTIVE",  today),
        ("Car3Rohan",   "GJ-01-NP-7003", "ACTIVE",  today),
        ("Car1Kavita",  "GJ-05-QR-8001", "ACTIVE",  today),
        ("Car2Kavita",  "GJ-05-QR-8002", "ACTIVE",  today),
        ("Car3Kavita",  "GJ-05-QR-8003", "BLOCKED", today),  # Edge case 2
        ("Car1Arjun",   "KL-01-ST-9001", "ACTIVE",  today),
        ("Car2Arjun",   "KL-01-ST-9002", "ACTIVE",  today),
        ("Car3Arjun",   "KL-01-ST-9003", "ACTIVE",  today),
        ("Car1Meera",   "AP-09-UV-0001", "ACTIVE",  today),
        ("Car2Meera",   "AP-09-UV-0002", "ACTIVE",  today),
        ("Car3Meera",   "AP-09-UV-0003", "ACTIVE",  today),
    ]
    cur.executemany("INSERT INTO RFID_Tags (tag_id, registration_no, status, issued_date) VALUES (?, ?, ?, ?);", tags)

    # 5. 30 Toll Plazas across 10 Cities (Task 4.1: Unified Source of Truth)
    cur.executemany("INSERT INTO Toll_Plazas (plaza_id, plaza_name, highway_name, base_toll_rate, region) VALUES (?, ?, ?, ?, ?);", ALL_PLAZA_ROWS)

def process_toll_batch(tag_id: str, plaza_ref: str, timestamp_str: str = None) -> dict:
    """
    Implements the atomic 'Process_Toll_Batch' procedure from Slide 15 / Section 6.1.
    Performs atomic wallet deduction, vehicle class pricing, impossible-travel fraud check,
    and immutable journey logging with full ACID guarantees.
    """
    if not timestamp_str:
        timestamp_str = datetime.now(timezone.utc).isoformat()

    conn = get_connection()
    try:
        # Task 2: Lock the transaction immediately at the start of read-decide-write cycle
        conn.execute("BEGIN IMMEDIATE;")
        cur = conn.cursor()

        # Step 1: Look up Plaza (by ID or by name) - Task 4.3 selects region
        cur.execute("SELECT plaza_id, plaza_name, base_toll_rate, region FROM Toll_Plazas WHERE plaza_id = ? OR plaza_name = ?;", (plaza_ref, plaza_ref))
        plaza_row = cur.fetchone()
        if not plaza_row:
            conn.commit()
            return {"status": "SKIPPED", "reason": f"Unknown plaza: {plaza_ref}"}

        plaza_id = plaza_row["plaza_id"]
        plaza_name = plaza_row["plaza_name"]
        base_toll_rate = float(plaza_row["base_toll_rate"])
        plaza_region = plaza_row["region"]

        # Step 2: Look up Tag, Vehicle, Owner, and Wallet
        cur.execute("""
            SELECT u.user_id, u.full_name, w.current_balance, t.status, v.vehicle_class
            FROM RFID_Tags t
            JOIN Vehicles v       ON t.registration_no = v.registration_no
            JOIN Users u          ON v.user_id = u.user_id
            JOIN Wallet_Ledgers w ON u.user_id = w.user_id
            WHERE t.tag_id = ?;
        """, (tag_id,))
        record = cur.fetchone()

        if not record:
            conn.commit()
            return {"status": "SKIPPED", "reason": f"Unknown tag: {tag_id}"}

        user_id = record["user_id"]
        current_balance = float(record["current_balance"])
        tag_status = record["status"]
        vehicle_class = record["vehicle_class"]

        # Task 5: Vehicle Class Multiplier (Car=1.0x, Bus=2.0x, Truck=3.0x)
        class_multipliers = {"Car": 1.0, "Bus": 2.0, "Truck": 3.0}
        multiplier = class_multipliers.get(vehicle_class, 1.0)
        toll_rate = round(base_toll_rate * multiplier, 2)

        # Step 3: Atomic Evaluation (ACID Transaction)
        def _sync_local_node(j_id, amt, st, reas):
            try:
                import ddbms_manager
                city_k = ddbms_manager.detect_city_for_plaza(plaza_name or plaza_id)
                ddbms_manager.record_local_passage(city_k, {
                    "journey_id": j_id,
                    "tag_id": tag_id,
                    "plaza_id": plaza_id,
                    "plaza_name": plaza_name,
                    "timestamp": timestamp_str,
                    "deducted_amount": amt,
                    "payment_status": st,
                    "failure_reason": reas
                })
            except Exception:
                pass

        # Check 1: Tag Status
        if tag_status != "ACTIVE":
            cur.execute("""
                INSERT OR IGNORE INTO Journeys (tag_id, plaza_id, timestamp, deducted_amount, payment_status, failure_reason)
                VALUES (?, ?, ?, 0.00, 'FAILED', ?);
            """, (tag_id, plaza_id, timestamp_str, f"Tag {tag_status}"))
            conn.commit()
            _sync_local_node(cur.lastrowid, 0.00, "FAILED", f"Tag {tag_status}")
            return {
                "status": "FAILED",
                "payment_status": "FAILED",
                "tag_id": tag_id,
                "plaza_id": plaza_id,
                "deducted": 0.00,
                "balance": current_balance,
                "reason": f"RFID Tag is {tag_status}"
            }

        # Task 6 & Task 4.3: Spatiotemporal Fraud Detection ("Impossible Travel" via region column)
        cur.execute("""
            SELECT p.plaza_name, p.region, j.timestamp
            FROM Journeys j
            JOIN Toll_Plazas p ON j.plaza_id = p.plaza_id
            WHERE j.tag_id = ? AND j.payment_status = 'SUCCESS'
            ORDER BY j.journey_id DESC
            LIMIT 1;
        """, (tag_id,))
        last_journey = cur.fetchone()

        if last_journey:
            last_city = last_journey["region"]
            current_city = plaza_region

            if current_city != last_city:
                try:
                    last_time = datetime.fromisoformat(last_journey["timestamp"])
                    curr_time = datetime.fromisoformat(timestamp_str) if timestamp_str else datetime.now(timezone.utc)
                    gap_hours = abs((curr_time - last_time).total_seconds()) / 3600.0

                    if gap_hours < 2.0:
                        cloning_reason = f"Suspected Tag Cloning: {last_city}→{current_city} in {gap_hours:.1f}h"
                        cur.execute("""
                            INSERT OR IGNORE INTO Journeys (tag_id, plaza_id, timestamp, deducted_amount, payment_status, failure_reason)
                            VALUES (?, ?, ?, 0.00, 'FAILED', ?);
                        """, (tag_id, plaza_id, timestamp_str, cloning_reason))
                        conn.commit()
                        _sync_local_node(cur.lastrowid, 0.00, "FAILED", cloning_reason)
                        return {
                            "status": "FAILED",
                            "payment_status": "FAILED",
                            "tag_id": tag_id,
                            "plaza_id": plaza_id,
                            "deducted": 0.00,
                            "balance": current_balance,
                            "reason": cloning_reason
                        }
                except Exception:
                    pass

        # Check 2: Wallet Balance
        if current_balance < toll_rate:
            cur.execute("""
                INSERT OR IGNORE INTO Journeys (tag_id, plaza_id, timestamp, deducted_amount, payment_status, failure_reason)
                VALUES (?, ?, ?, 0.00, 'FAILED', 'Insufficient Balance');
            """, (tag_id, plaza_id, timestamp_str))
            conn.commit()
            _sync_local_node(cur.lastrowid, 0.00, "FAILED", "Insufficient Balance")
            return {
                "status": "FAILED",
                "payment_status": "FAILED",
                "tag_id": tag_id,
                "plaza_id": plaza_id,
                "deducted": 0.00,
                "balance": current_balance,
                "reason": "Insufficient Wallet Balance"
            }

        # SUCCESS PATH: Atomic Deduction and Journey Insert
        cur.execute("""
            UPDATE Wallet_Ledgers
            SET current_balance = current_balance - ?,
                last_updated = CURRENT_TIMESTAMP
            WHERE user_id = ?;
        """, (toll_rate, user_id))

        cur.execute("""
            INSERT OR IGNORE INTO Journeys (tag_id, plaza_id, timestamp, deducted_amount, payment_status, failure_reason)
            VALUES (?, ?, ?, ?, 'SUCCESS', NULL);
        """, (tag_id, plaza_id, timestamp_str, toll_rate))

        conn.commit()
        _sync_local_node(cur.lastrowid, toll_rate, "SUCCESS", None)

        new_balance = round(current_balance - toll_rate, 2)
        return {
            "status": "SUCCESS",
            "payment_status": "SUCCESS",
            "tag_id": tag_id,
            "plaza_id": plaza_id,
            "deducted": toll_rate,
            "balance": new_balance,
            "vehicle_class": vehicle_class,
            "reason": None
        }

    except Exception as e:
        conn.rollback()
        return {"status": "ERROR", "reason": str(e)}
    finally:
        conn.close()

def authenticate_account(username: str, password: str):
    """
    Unified multi-tier authentication:
    1. 'admin' -> Global Operations Admin (access to master global database)
    2. City accounts (e.g. 'chennai' / 'chennai123') -> City Station Officer (local database)
    3. Vehicle owners (e.g. 'ravi' / 'ravi123') -> Normal User (personal wallet & journeys only)
    """
    u = (username or "").strip().lower()
    p = (password or "").strip()

    if u == "admin" and p == "admin123":
        return {
            "username": "admin",
            "role": "admin",
            "full_name": "Global Operations Administrator",
            "city": None,
        }

    # Check city regional accounts
    for city_key, info in CITIES.items():
        if u == city_key.lower() and p == f"{city_key.lower()}123":
            return {
                "username": u,
                "role": "city",
                "city": city_key,
                "full_name": f"{info['name']} Regional Toll Authority",
            }

    # Check vehicle owner accounts from 3NF SQL Users table
    user = authenticate_user(u, p)
    if user:
        user["role"] = "user"
        user["city"] = None
        return user

    return None

def authenticate_user(username: str, password: str):
    """Verifies user credentials using secure password hashing."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_id, username, password, full_name, phone_number FROM Users WHERE LOWER(username) = LOWER(?);", (username,))
    user = cur.fetchone()
    conn.close()
    if user:
        stored_hash = user["password"]
        is_valid = False
        if stored_hash.startswith(("scrypt:", "pbkdf2:")):
            is_valid = check_password_hash(stored_hash, password)
        elif stored_hash == password:
            is_valid = True

        if is_valid:
            user_dict = dict(user)
            user_dict.pop("password", None)
            return user_dict
    return None

def get_city_dashboard_data(city_name: str) -> dict:
    """Fetches local regional database info, plazas, and transactions for a specific city."""
    city_key = (city_name or "").strip().upper()
    if city_key not in CITIES:
        return None

    info = CITIES[city_key]
    conn = get_connection()
    cur = conn.cursor()

    # Query local plazas
    cur.execute(
        "SELECT plaza_id, plaza_name, highway_name, base_toll_rate FROM Toll_Plazas WHERE plaza_name IN (?, ?, ?);",
        tuple(info["plazas"])
    )
    plazas = [dict(r) for r in cur.fetchall()]
    plaza_ids = [p["plaza_id"] for p in plazas]

    stats = {
        "total_journeys": 0,
        "total_revenue": 0.0,
        "successful_journeys": 0,
        "failed_journeys": 0,
    }
    recent_journeys = []

    if plaza_ids:
        placeholders = ",".join("?" * len(plaza_ids))
        cur.execute(f"""
            SELECT 
                COUNT(*) as total_journeys,
                SUM(CASE WHEN payment_status = 'SUCCESS' THEN deducted_amount ELSE 0.0 END) as total_revenue,
                SUM(CASE WHEN payment_status = 'SUCCESS' THEN 1 ELSE 0 END) as successful_journeys,
                SUM(CASE WHEN payment_status = 'FAILED' THEN 1 ELSE 0 END) as failed_journeys
            FROM Journeys 
            WHERE plaza_id IN ({placeholders});
        """, tuple(plaza_ids))
        srow = cur.fetchone()
        if srow:
            stats["total_journeys"] = srow["total_journeys"] or 0
            stats["total_revenue"] = float(srow["total_revenue"] or 0.0)
            stats["successful_journeys"] = srow["successful_journeys"] or 0
            stats["failed_journeys"] = srow["failed_journeys"] or 0

        cur.execute(f"""
            SELECT j.journey_id, j.timestamp, j.tag_id, j.deducted_amount, j.payment_status, j.failure_reason,
                   tp.plaza_name, tp.highway_name, v.registration_no, v.vehicle_class, u.full_name as owner_name
            FROM Journeys j
            JOIN Toll_Plazas tp ON j.plaza_id = tp.plaza_id
            JOIN RFID_Tags t   ON j.tag_id = t.tag_id
            JOIN Vehicles v    ON t.registration_no = v.registration_no
            JOIN Users u       ON v.user_id = u.user_id
            WHERE j.plaza_id IN ({placeholders})
            ORDER BY j.journey_id DESC
            LIMIT 50;
        """, tuple(plaza_ids))
        recent_journeys = [dict(r) for r in cur.fetchall()]

    conn.close()

    return {
        "city_key": city_key,
        "city_name": info["name"],
        "highway": info["highway"],
        "plazas": plazas,
        "stats": stats,
        "recent_journeys": recent_journeys,
    }

def get_user_dashboard_data(username: str) -> dict:
    """Fetches user profile, wallet balance, vehicles, tags, and journeys from SQL."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT user_id, username, full_name, phone_number FROM Users WHERE username = ?;", (username,))
    user = cur.fetchone()
    if not user:
        conn.close()
        return None

    user_dict = dict(user)
    uid = user_dict["user_id"]

    # Wallet
    cur.execute("SELECT ledger_id, current_balance, last_updated FROM Wallet_Ledgers WHERE user_id = ?;", (uid,))
    wallet = cur.fetchone()
    user_dict["wallet"] = dict(wallet) if wallet else {"current_balance": 0.0}

    # Vehicles & Tags
    cur.execute("""
        SELECT v.registration_no, v.vehicle_class, t.tag_id, t.status, t.issued_date
        FROM Vehicles v
        JOIN RFID_Tags t ON v.registration_no = t.registration_no
        WHERE v.user_id = ?;
    """, (uid,))
    vehicles = [dict(r) for r in cur.fetchall()]
    user_dict["vehicles"] = vehicles

    # Journeys for these tags
    tag_ids = [v["tag_id"] for v in vehicles]
    journeys = []
    if tag_ids:
        placeholders = ",".join(["?"] * len(tag_ids))
        cur.execute(f"""
            SELECT j.journey_id, j.tag_id, j.timestamp, j.deducted_amount, j.payment_status, j.failure_reason,
                   p.plaza_name, p.highway_name
            FROM Journeys j
            JOIN Toll_Plazas p ON j.plaza_id = p.plaza_id
            WHERE j.tag_id IN ({placeholders})
            ORDER BY j.journey_id DESC
            LIMIT 100;
        """, tag_ids)
        journeys = [dict(r) for r in cur.fetchall()]

    user_dict["journeys"] = journeys
    conn.close()
    return user_dict

def recharge_wallet(user_id: int, amount: float) -> float:
    """Adds balance to user wallet."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE Wallet_Ledgers
        SET current_balance = current_balance + ?,
            last_updated = CURRENT_TIMESTAMP
        WHERE user_id = ?;
    """, (amount, user_id))
    conn.commit()

    cur.execute("SELECT current_balance FROM Wallet_Ledgers WHERE user_id = ?;", (user_id,))
    row = cur.fetchone()
    conn.close()
    return float(row["current_balance"]) if row else 0.0

def get_all_tables_data() -> dict:
    """Returns data from all 6 relational tables to display the SQL Ledger Inspector."""
    conn = get_connection()
    cur = conn.cursor()

    tables = ["Users", "Wallet_Ledgers", "Vehicles", "RFID_Tags", "Toll_Plazas", "Journeys"]
    result = {}
    for tbl in tables:
        if tbl == "Journeys":
            cur.execute("SELECT * FROM Journeys ORDER BY journey_id DESC LIMIT 50;")
        else:
            cur.execute(f"SELECT * FROM {tbl};")
        rows = [dict(r) for r in cur.fetchall()]
        result[tbl] = rows

    conn.close()
    return result

def execute_raw_query(query_str: str) -> dict:
    """
    Executes arbitrary SQL on the central database with execution timing and error handling.
    Task 4: Enforces read-only safety guard for the web console.
    """
    import time
    start_time = time.perf_counter()
    query_clean = query_str.strip()

    if not query_clean:
        return {"success": False, "error": "Query cannot be empty."}

    # Task 4: Only allow read-only operations from the web console
    query_upper = query_clean.upper().lstrip()
    allowed_prefixes = ("SELECT", "PRAGMA", "EXPLAIN", "WITH")
    if not query_upper.startswith(allowed_prefixes):
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return {
            "success": False,
            "error": "⛔ Write operations (INSERT, UPDATE, DELETE, DROP, ALTER) are disabled in the SQL Console for safety. Use the application endpoints instead.",
            "execution_time_ms": elapsed_ms
        }

    conn = get_connection()
    # Task 2.5: Enforce SQLite engine-level read-only authorizer
    allowed_actions = {
        sqlite3.SQLITE_SELECT,
        sqlite3.SQLITE_READ,
        sqlite3.SQLITE_FUNCTION,
        sqlite3.SQLITE_PRAGMA,
    }
    def _read_only_authorizer(action, arg1, arg2, dbname, trigger):
        if action in allowed_actions:
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY

    conn.set_authorizer(_read_only_authorizer)
    try:
        cur = conn.cursor()
        cur.execute(query_clean)

        # Queries returning rows (SELECT, PRAGMA, EXPLAIN, WITH)
        if cur.description:
            columns = [desc[0] for desc in cur.description]
            raw_rows = cur.fetchall()
            rows = [list(r) for r in raw_rows]
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return {
                "success": True,
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
                "execution_time_ms": elapsed_ms,
                "type": "SELECT"
            }
        else:
            conn.commit()
            rows_affected = cur.rowcount
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return {
                "success": True,
                "rows_affected": rows_affected,
                "execution_time_ms": elapsed_ms,
                "type": "DML",
                "message": f"Query executed successfully. Rows affected: {rows_affected}"
            }
    except Exception as e:
        conn.rollback()
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return {
            "success": False,
            "error": str(e),
            "execution_time_ms": elapsed_ms
        }
    finally:
        conn.close()

def get_schema_info() -> dict:
    """Returns database schema information: tables, column definitions, and live row counts."""
    conn = get_connection()
    cur = conn.cursor()
    schema = {}
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;")
    tables = [r["name"] for r in cur.fetchall()]
    for tbl in tables:
        cur.execute(f"PRAGMA table_info({tbl});")
        cols = [{"cid": r["cid"], "name": r["name"], "type": r["type"], "notnull": r["notnull"], "pk": r["pk"]} for r in cur.fetchall()]
        cur.execute(f"SELECT COUNT(*) AS cnt FROM {tbl};")
        count = cur.fetchone()["cnt"]
        schema[tbl] = {"columns": cols, "count": count}
    conn.close()
    return schema

def toggle_rfid_tag_status(user_id: int, tag_id: str) -> dict:
    """Toggles RFID tag status between ACTIVE and BLOCKED for a vehicle owner or admin (Task 6.3)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT t.tag_id, t.status, v.user_id
        FROM RFID_Tags t
        JOIN Vehicles v ON t.registration_no = v.registration_no
        WHERE t.tag_id = ?;
    """, (tag_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return {"success": False, "error": f"Tag {tag_id} not found."}

    if user_id and row["user_id"] != user_id:
        conn.close()
        return {"success": False, "error": "Unauthorized: Tag does not belong to you."}

    new_status = "BLOCKED" if row["status"] == "ACTIVE" else "ACTIVE"
    cur.execute("UPDATE RFID_Tags SET status = ? WHERE tag_id = ?;", (new_status, tag_id))
    conn.commit()
    conn.close()

    # Sync local DDBMS edge cache
    try:
        import ddbms_manager
        for city_k in ddbms_manager.CITIES_METADATA:
            cconn = ddbms_manager.get_node_connection(city_k)
            cconn.execute("UPDATE Edge_Tags_Cache SET status = ? WHERE tag_id = ?;", (new_status, tag_id))
            cconn.commit()
            cconn.close()
    except Exception:
        pass

    return {"success": True, "tag_id": tag_id, "new_status": new_status}


# ─────────────────────────────────────────────────────────────────────────────
# Real-Time Security & Operational Error Log Engine
# ─────────────────────────────────────────────────────────────────────────────
def get_security_error_logs(limit=100, alert_type=None):
    """
    Retrieves real-time operational and security alert logs from fastag_ledger.db:
    - Impossible travel tag cloning fraud
    - Insufficient wallet balance failures
    - Blocked / blacklisted tag passage attempts
    """
    conn = get_connection()
    cur = conn.cursor()

    # Get summary counts
    cur.execute("""
        SELECT 
            COUNT(*) as total_alerts,
            SUM(CASE WHEN failure_reason LIKE '%Cloning%' THEN 1 ELSE 0 END) as cloning_alerts,
            SUM(CASE WHEN failure_reason LIKE '%Insufficient%' THEN 1 ELSE 0 END) as insufficient_alerts,
            SUM(CASE WHEN failure_reason LIKE '%BLOCKED%' OR failure_reason LIKE '%Tag %' THEN 1 ELSE 0 END) as blocked_alerts
        FROM Journeys
        WHERE payment_status = 'FAILED';
    """)
    srow = cur.fetchone()
    summary = {
        "total_alerts": srow["total_alerts"] or 0,
        "cloning_alerts": srow["cloning_alerts"] or 0,
        "insufficient_alerts": srow["insufficient_alerts"] or 0,
        "blocked_alerts": srow["blocked_alerts"] or 0
    }

    query = """
        SELECT 
            j.journey_id,
            j.tag_id,
            j.plaza_id,
            COALESCE(p.plaza_name, 'Plaza ' || j.plaza_id) as plaza_name,
            COALESCE(p.region, 'UNKNOWN') as region,
            COALESCE(p.highway_name, 'Highway') as highway_name,
            j.timestamp,
            j.deducted_amount,
            j.payment_status,
            j.failure_reason,
            COALESCE(t.registration_no, 'Unknown') as registration_no,
            COALESCE(v.vehicle_class, 'Car') as vehicle_class,
            COALESCE(u.full_name, 'Unknown Owner') as owner_name,
            COALESCE(u.phone_number, 'N/A') as phone_number
        FROM Journeys j
        LEFT JOIN Toll_Plazas p ON j.plaza_id = p.plaza_id
        LEFT JOIN RFID_Tags t ON j.tag_id = t.tag_id
        LEFT JOIN Vehicles v ON t.registration_no = v.registration_no
        LEFT JOIN Users u ON v.user_id = u.user_id
        WHERE j.payment_status = 'FAILED'
    """
    params = []
    if alert_type == "cloning":
        query += " AND j.failure_reason LIKE '%Cloning%'"
    elif alert_type == "insufficient":
        query += " AND j.failure_reason LIKE '%Insufficient%'"
    elif alert_type == "blocked":
        query += " AND (j.failure_reason LIKE '%BLOCKED%' OR j.failure_reason LIKE '%Tag %')"

    query += " ORDER BY j.journey_id DESC LIMIT ?;"
    params.append(limit)

    cur.execute(query, tuple(params))
    rows = cur.fetchall()
    conn.close()

    alerts = []
    for r in rows:
        reason = r["failure_reason"] or "Transaction Rejected"
        if "Cloning" in reason:
            cat = "TAG_CLONING_FRAUD"
            severity = "CRITICAL"
            action = "🚨 Gate Barred · Zero Deducted · Fraud Audit Flagged"
        elif "Insufficient" in reason:
            cat = "INSUFFICIENT_BALANCE"
            severity = "WARNING"
            action = "⚠️ Gate Held · Zero Deducted · User Alert Dispatched"
        elif "BLOCKED" in reason or "Tag " in reason:
            cat = "BLOCKED_TAG"
            severity = "DANGER"
            action = "🛑 Gate Locked · Impound Alert Notified"
        else:
            cat = "OPERATIONAL_FAILURE"
            severity = "INFO"
            action = "Audit Logged"

        alerts.append({
            "journey_id": r["journey_id"],
            "timestamp": r["timestamp"],
            "tag_id": r["tag_id"],
            "registration_no": r["registration_no"],
            "vehicle_class": r["vehicle_class"],
            "owner_name": r["owner_name"],
            "phone_number": r["phone_number"],
            "plaza_id": r["plaza_id"],
            "plaza_name": r["plaza_name"],
            "region": r["region"],
            "highway_name": r["highway_name"],
            "failure_reason": reason,
            "category": cat,
            "severity": severity,
            "action_taken": action
        })

    return {
        "summary": summary,
        "alerts": alerts,
        "count": len(alerts)
    }

