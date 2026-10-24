import os
import uuid
import pytest
from datetime import datetime, timezone, timedelta
import sql_ledger

@pytest.fixture(autouse=True)
def isolated_db(monkeypatch, tmp_path):
    test_db = str(tmp_path / f"test_ledger_{uuid.uuid4().hex[:8]}.db")
    monkeypatch.setattr(sql_ledger, "DB_PATH", test_db)
    sql_ledger.init_db(reset=True)
    yield test_db

def test_successful_toll_deduction():
    initial_balance = 2500.00
    res = sql_ledger.process_toll_batch("Car1Ravi", "Place1Delhi")
    assert res["status"] == "SUCCESS"
    assert res["deducted"] == 95.00
    assert res["balance"] == initial_balance - 95.00

def test_blocked_tag_rejected():
    res = sql_ledger.process_toll_batch("Car3Amit", "Place1Delhi")
    assert res["status"] == "FAILED"
    assert "BLOCKED" in res["reason"]
    assert res["deducted"] == 0.00

def test_insufficient_balance():
    res = sql_ledger.process_toll_batch("Car1Amit", "Place1Mumbai")
    assert res["status"] == "FAILED"
    assert "Insufficient" in res["reason"]
    assert res["deducted"] == 0.00

def test_idempotency():
    ts = "2026-10-24T12:00:00+00:00"
    res1 = sql_ledger.process_toll_batch("Car2Ravi", "Place2Delhi", timestamp_str=ts)
    assert res1["status"] == "SUCCESS"
    res2 = sql_ledger.process_toll_batch("Car2Ravi", "Place2Delhi", timestamp_str=ts)
    
    conn = sql_ledger.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS cnt FROM Journeys WHERE tag_id = 'Car2Ravi' AND timestamp = ?;", (ts,))
    assert cur.fetchone()["cnt"] == 1
    conn.close()

def test_vehicle_class_multiplier():
    # Car3Sneha is a Truck (3.0x multiplier on Place1Delhi 95.00 = 285.00)
    res = sql_ledger.process_toll_batch("Car3Sneha", "Place1Delhi")
    assert res["status"] == "SUCCESS"
    assert res["deducted"] == 285.00

def test_impossible_travel_fraud():
    now = datetime.now(timezone.utc)
    t1 = now.isoformat()
    t2 = (now + timedelta(minutes=15)).isoformat()

    res1 = sql_ledger.process_toll_batch("Car1Priya", "Place1Delhi", timestamp_str=t1)
    assert res1["status"] == "SUCCESS"

    res2 = sql_ledger.process_toll_batch("Car1Priya", "Place1Chennai", timestamp_str=t2)
    assert res2["status"] == "FAILED"
    assert "Suspected Tag Cloning" in res2["reason"]

def test_wallet_recharge():
    old_bal = sql_ledger.recharge_wallet(1, 0)
    new_bal = sql_ledger.recharge_wallet(1, 500.0)
    assert new_bal == old_bal + 500.0
