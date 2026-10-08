"""
FASTag DA-2 — Part 1 Verification Tests
Tests all backend API endpoints end-to-end.
"""

import json
import time
import requests
import sys

BASE_URL = "http://127.0.0.1:5000"
PASS = 0
FAIL = 0


def test(name, func):
    global PASS, FAIL
    try:
        func()
        print(f"  ✅ {name}")
        PASS += 1
    except AssertionError as e:
        print(f"  ❌ {name} — {e}")
        FAIL += 1
    except Exception as e:
        print(f"  ❌ {name} — EXCEPTION: {e}")
        FAIL += 1


# ─── 1. Health Check ───────────────────────────────────────────────────────────
def test_health():
    r = requests.get(f"{BASE_URL}/api/health")
    assert r.status_code == 200, f"Status {r.status_code}"
    d = r.json()
    assert d["status"] == "healthy", f"Not healthy: {d}"
    assert "storage_backend" in d
    assert d["total_pings_ingested"] >= 0

# ─── 2. Dashboard (HTML) ──────────────────────────────────────────────────────
def test_dashboard():
    r = requests.get(f"{BASE_URL}/")
    assert r.status_code == 200, f"Status {r.status_code}"
    assert "FASTag" in r.text, "Dashboard HTML missing title"
    assert "total-pings" in r.text, "Dashboard missing counter element"

# ─── 3. Initial Stats (should be zero) ────────────────────────────────────────
def test_initial_stats():
    r = requests.get(f"{BASE_URL}/api/stats")
    assert r.status_code == 200, f"Status {r.status_code}"
    d = r.json()
    assert "total_raw_pings" in d
    assert "pings_per_second" in d
    assert "chaos_mode" in d
    assert d["chaos_mode"] == False

# ─── 4. Ingest — Error cases ──────────────────────────────────────────────────
def test_ingest_no_body():
    r = requests.post(f"{BASE_URL}/api/ingest", json={})
    assert r.status_code == 400, f"Expected 400, got {r.status_code}"

def test_ingest_empty_pings():
    r = requests.post(f"{BASE_URL}/api/ingest", json={"pings": []})
    assert r.status_code == 400, f"Expected 400, got {r.status_code}"

def test_ingest_invalid_pings():
    r = requests.post(f"{BASE_URL}/api/ingest", json={"pings": "not a list"})
    assert r.status_code == 400, f"Expected 400, got {r.status_code}"

# ─── 5. Ingest — Single batch ─────────────────────────────────────────────────
def test_ingest_single_batch():
    pings = [
        {"plaza_id": "PLAZA_NH48_GURUGRAM", "tag_id": "TAG_001", "rssi_signal_strength": -42.5,
         "lane_id": "LANE_1", "region": "NORTH"},
        {"plaza_id": "PLAZA_NH48_GURUGRAM", "tag_id": "TAG_001", "rssi_signal_strength": -38.2,
         "lane_id": "LANE_1", "region": "NORTH"},
        {"plaza_id": "PLAZA_NH48_GURUGRAM", "tag_id": "TAG_002", "rssi_signal_strength": -55.0,
         "lane_id": "LANE_2", "region": "NORTH"},
        {"plaza_id": "PLAZA_NH44_BANGALORE", "tag_id": "TAG_003", "rssi_signal_strength": -44.0,
         "lane_id": "LANE_1", "region": "SOUTH"},
    ]
    r = requests.post(f"{BASE_URL}/api/ingest", json={"pings": pings})
    assert r.status_code == 201, f"Expected 201, got {r.status_code}"
    d = r.json()
    assert d["status"] == "ok"
    assert d["ingested"] == 4, f"Expected 4 ingested, got {d['ingested']}"
    assert d["total"] >= 4

# ─── 6. Ingest — Large batch ──────────────────────────────────────────────────
def test_ingest_large_batch():
    pings = []
    for i in range(500):
        pings.append({
            "plaza_id": f"PLAZA_{i % 5}",
            "tag_id": f"TAG_{i % 50}",
            "rssi_signal_strength": -30.0 - (i % 40),
            "lane_id": f"LANE_{i % 4}",
            "region": ["NORTH", "SOUTH", "WEST"][i % 3],
        })
    r = requests.post(f"{BASE_URL}/api/ingest", json={"pings": pings})
    assert r.status_code == 201, f"Expected 201, got {r.status_code}"
    d = r.json()
    assert d["ingested"] == 500, f"Expected 500, got {d['ingested']}"

# ─── 7. Stats after ingestion ─────────────────────────────────────────────────
def test_stats_after_ingest():
    r = requests.get(f"{BASE_URL}/api/stats")
    assert r.status_code == 200
    d = r.json()
    assert d["total_raw_pings"] >= 504, f"Expected >= 504, got {d['total_raw_pings']}"
    assert d["pings_per_second"] >= 0

# ─── 8. Plaza stats ───────────────────────────────────────────────────────────
def test_plaza_stats():
    r = requests.get(f"{BASE_URL}/api/stats/plaza")
    assert r.status_code == 200
    d = r.json()
    assert "plazas" in d
    assert len(d["plazas"]) > 0, "No plaza stats returned"
    # Check structure of a plaza entry
    first_key = list(d["plazas"].keys())[0]
    plaza = d["plazas"][first_key]
    assert "total_pings" in plaza
    assert "unique_tags" in plaza
    assert "duplicates" in plaza

# ─── 9. Throughput history ─────────────────────────────────────────────────────
def test_throughput_history():
    r = requests.get(f"{BASE_URL}/api/stats/throughput?buckets=10")
    assert r.status_code == 200
    d = r.json()
    assert "data" in d
    assert len(d["data"]) == 10, f"Expected 10 buckets, got {len(d['data'])}"
    assert "timestamp" in d["data"][0]
    assert "pps" in d["data"][0]

# ─── 10. Dedup trigger ────────────────────────────────────────────────────────
def test_dedup_trigger():
    r = requests.post(f"{BASE_URL}/api/dedup/trigger")
    assert r.status_code == 200
    d = r.json()
    assert "raw_count" in d
    assert "journey_count" in d
    assert "dedup_ratio" in d
    assert d["raw_count"] > 0, "Dedup saw no raw pings"
    assert d["journey_count"] > 0, "Dedup produced no journeys"
    assert d["journey_count"] <= d["raw_count"], "More journeys than raw pings?!"
    assert d["dedup_ratio"] >= 0

# ─── 11. Dedup results (event feed) ───────────────────────────────────────────
def test_dedup_results():
    r = requests.get(f"{BASE_URL}/api/dedup/results")
    assert r.status_code == 200
    d = r.json()
    assert "journeys" in d
    assert len(d["journeys"]) > 0, "No journeys in results"
    j = d["journeys"][0]
    assert "tag_id" in j
    assert "plaza_id" in j
    assert "rssi_signal_strength" in j
    assert "duplicate_count" in j

# ─── 12. Dedup config GET ─────────────────────────────────────────────────────
def test_dedup_config_get():
    r = requests.get(f"{BASE_URL}/api/dedup/config")
    assert r.status_code == 200
    d = r.json()
    assert "interval_seconds" in d
    assert d["interval_seconds"] > 0

# ─── 13. Dedup config PUT ─────────────────────────────────────────────────────
def test_dedup_config_put():
    r = requests.put(f"{BASE_URL}/api/dedup/config", json={"interval_seconds": 15})
    assert r.status_code == 200
    d = r.json()
    assert d["interval_seconds"] == 15
    # Verify it took effect
    r2 = requests.get(f"{BASE_URL}/api/dedup/config")
    assert r2.json()["interval_seconds"] == 15
    # Reset
    requests.put(f"{BASE_URL}/api/dedup/config", json={"interval_seconds": 30})

# ─── 14. Chaos mode toggle ────────────────────────────────────────────────────
def test_chaos_toggle_on():
    r = requests.post(f"{BASE_URL}/api/chaos", json={"active": True})
    assert r.status_code == 200
    d = r.json()
    assert d["active"] == True
    assert d["multiplier"] == 10

def test_chaos_status():
    r = requests.get(f"{BASE_URL}/api/chaos/status")
    assert r.status_code == 200
    d = r.json()
    assert d["active"] == True
    assert d["activated_at"] is not None

def test_chaos_toggle_off():
    r = requests.post(f"{BASE_URL}/api/chaos")  # Toggle (should turn off)
    assert r.status_code == 200
    d = r.json()
    assert d["active"] == False

def test_chaos_verify_off():
    r = requests.get(f"{BASE_URL}/api/chaos/status")
    assert r.status_code == 200
    assert r.json()["active"] == False

# ─── 15. Dedup correctness — verify highest RSSI wins ─────────────────────────
def test_dedup_highest_rssi_wins():
    """Ingest known data with controlled RSSI values and verify dedup picks the highest."""
    # Ingest 3 pings for the same tag at the same plaza with different RSSI
    pings = [
        {"plaza_id": "TEST_PLAZA", "tag_id": "TAG_RSSI_TEST", "rssi_signal_strength": -60.0,
         "lane_id": "L1", "region": "NORTH"},
        {"plaza_id": "TEST_PLAZA", "tag_id": "TAG_RSSI_TEST", "rssi_signal_strength": -25.0,   # WINNER
         "lane_id": "L2", "region": "NORTH"},
        {"plaza_id": "TEST_PLAZA", "tag_id": "TAG_RSSI_TEST", "rssi_signal_strength": -45.0,
         "lane_id": "L1", "region": "NORTH"},
    ]
    requests.post(f"{BASE_URL}/api/ingest", json={"pings": pings})
    time.sleep(0.2)

    # Trigger dedup
    requests.post(f"{BASE_URL}/api/dedup/trigger")

    # Check results
    r = requests.get(f"{BASE_URL}/api/dedup/results")
    d = r.json()
    rssi_test_journey = [j for j in d["journeys"] if j["tag_id"] == "TAG_RSSI_TEST"
                         and j["plaza_id"] == "TEST_PLAZA"]
    assert len(rssi_test_journey) == 1, f"Expected 1 journey for TAG_RSSI_TEST, got {len(rssi_test_journey)}"
    assert rssi_test_journey[0]["rssi_signal_strength"] == -25.0, \
        f"Expected RSSI -25.0 (highest), got {rssi_test_journey[0]['rssi_signal_strength']}"
    assert rssi_test_journey[0]["duplicate_count"] == 3, \
        f"Expected 3 dupes, got {rssi_test_journey[0]['duplicate_count']}"


# ─────────────────────────────────────────────────────────────────────────────────
# Run all tests
# ─────────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  FASTag DA-2 — Part 1 Backend Verification Tests")
    print("=" * 60)

    print("\n[Health & Dashboard]")
    test("Health check", test_health)
    test("Dashboard loads", test_dashboard)

    print("\n[Stats - Initial]")
    test("Initial stats endpoint", test_initial_stats)

    print("\n[Ingestion - Error Handling]")
    test("Ingest: missing body", test_ingest_no_body)
    test("Ingest: empty pings array", test_ingest_empty_pings)
    test("Ingest: invalid pings type", test_ingest_invalid_pings)

    print("\n[Ingestion - Success]")
    test("Ingest: single batch (4 pings)", test_ingest_single_batch)
    test("Ingest: large batch (500 pings)", test_ingest_large_batch)

    print("\n[Stats - After Ingestion]")
    test("Stats reflect ingested data", test_stats_after_ingest)
    test("Per-plaza stats", test_plaza_stats)
    test("Throughput history", test_throughput_history)

    print("\n[Deduplication]")
    test("Dedup: manual trigger", test_dedup_trigger)
    test("Dedup: results / event feed", test_dedup_results)
    test("Dedup: config GET", test_dedup_config_get)
    test("Dedup: config PUT", test_dedup_config_put)
    test("Dedup: highest RSSI wins", test_dedup_highest_rssi_wins)

    print("\n[Chaos Mode]")
    test("Chaos: toggle ON", test_chaos_toggle_on)
    test("Chaos: status check (ON)", test_chaos_status)
    test("Chaos: toggle OFF", test_chaos_toggle_off)
    test("Chaos: verify OFF", test_chaos_verify_off)

    print("\n" + "=" * 60)
    print(f"  Results: {PASS} passed, {FAIL} failed")
    print("=" * 60)

    sys.exit(1 if FAIL > 0 else 0)
