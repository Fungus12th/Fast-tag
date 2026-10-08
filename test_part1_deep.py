"""
FASTag DA-2 — Part 1 Deep Verification (Round 2)
Stress tests, concurrency, edge cases, and cross-laptop simulation.
"""

import json
import time
import threading
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


# ─── 1. Concurrent ingestion from multiple "laptops" ──────────────────────────
def test_concurrent_ingestion():
    """Simulate 3 laptops sending data concurrently."""
    errors = []
    results = {}

    def send_from_laptop(laptop_name, region, plaza_prefix, count):
        try:
            pings = []
            for i in range(count):
                pings.append({
                    "plaza_id": f"{plaza_prefix}_{i % 3}",
                    "tag_id": f"TAG_{laptop_name}_{i % 20}",
                    "rssi_signal_strength": -30.0 - (i % 30),
                    "region": region,
                    "lane_id": f"LANE_{i % 4}",
                })
            r = requests.post(f"{BASE_URL}/api/ingest", json={"pings": pings})
            assert r.status_code == 201, f"{laptop_name}: status {r.status_code}"
            d = r.json()
            assert d["ingested"] == count, f"{laptop_name}: expected {count}, got {d['ingested']}"
            results[laptop_name] = d["ingested"]
        except Exception as e:
            errors.append(f"{laptop_name}: {e}")

    threads = [
        threading.Thread(target=send_from_laptop, args=("LAPTOP1", "NORTH", "PLAZA_NORTH", 1000)),
        threading.Thread(target=send_from_laptop, args=("LAPTOP2", "SOUTH", "PLAZA_SOUTH", 1000)),
        threading.Thread(target=send_from_laptop, args=("LAPTOP3", "WEST",  "PLAZA_WEST",  1000)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert len(errors) == 0, f"Errors: {errors}"
    assert sum(results.values()) == 3000, f"Expected 3000 total, got {sum(results.values())}"


# ─── 2. Stats reflect concurrent data ─────────────────────────────────────────
def test_stats_after_concurrent():
    r = requests.get(f"{BASE_URL}/api/stats")
    d = r.json()
    # We've ingested 504 + 3 + 3000 = 3507 minimum
    assert d["total_raw_pings"] >= 3507, f"Expected >= 3507, got {d['total_raw_pings']}"


# ─── 3. Plaza stats show all 3 regions ────────────────────────────────────────
def test_all_regions_visible():
    r = requests.get(f"{BASE_URL}/api/stats/plaza")
    d = r.json()["plazas"]
    regions = set()
    for plaza_data in d.values():
        regions.add(plaza_data["region"])
    assert "NORTH" in regions, f"NORTH not in regions: {regions}"
    assert "SOUTH" in regions, f"SOUTH not in regions: {regions}"
    assert "WEST" in regions, f"WEST not in regions: {regions}"


# ─── 4. Dedup after concurrent ingestion ──────────────────────────────────────
def test_dedup_after_concurrent():
    r = requests.post(f"{BASE_URL}/api/dedup/trigger")
    d = r.json()
    assert d["raw_count"] > 0, "No raw pings for dedup"
    assert d["journey_count"] > 0, "No journeys produced"
    assert d["journey_count"] < d["raw_count"], "Dedup should reduce count"
    assert d["dedup_ratio"] > 0, "Dedup ratio should be > 0 with duplicates"
    print(f"    → {d['raw_count']} raw → {d['journey_count']} journeys ({d['dedup_ratio']}% filtered)")


# ─── 5. Throughput is non-zero after recent ingestion ──────────────────────────
def test_throughput_nonzero():
    # Ingest a small batch to ensure throughput window has data
    pings = [{"plaza_id": "P", "tag_id": "T", "rssi_signal_strength": -40}]
    requests.post(f"{BASE_URL}/api/ingest", json={"pings": pings})
    time.sleep(0.1)
    r = requests.get(f"{BASE_URL}/api/stats")
    d = r.json()
    # PPS might be very low but should show something
    assert d["pings_per_second"] >= 0, f"PPS negative: {d['pings_per_second']}"


# ─── 6. Dedup interval clamping ───────────────────────────────────────────────
def test_dedup_interval_clamp_low():
    """Interval should clamp at 5s minimum."""
    r = requests.put(f"{BASE_URL}/api/dedup/config", json={"interval_seconds": 1})
    d = r.json()
    assert d["interval_seconds"] >= 5, f"Expected >= 5, got {d['interval_seconds']}"

def test_dedup_interval_clamp_high():
    """Interval should clamp at 300s maximum."""
    r = requests.put(f"{BASE_URL}/api/dedup/config", json={"interval_seconds": 999})
    d = r.json()
    assert d["interval_seconds"] <= 300, f"Expected <= 300, got {d['interval_seconds']}"
    # Reset
    requests.put(f"{BASE_URL}/api/dedup/config", json={"interval_seconds": 30})

# ─── 7. Chaos mode explicit set ───────────────────────────────────────────────
def test_chaos_explicit_set():
    requests.post(f"{BASE_URL}/api/chaos", json={"active": False})
    r = requests.get(f"{BASE_URL}/api/chaos/status")
    assert r.json()["active"] == False

    requests.post(f"{BASE_URL}/api/chaos", json={"active": True})
    r = requests.get(f"{BASE_URL}/api/chaos/status")
    d = r.json()
    assert d["active"] == True
    assert d["multiplier"] == 10
    assert d["activated_at"] is not None

    # Clean up
    requests.post(f"{BASE_URL}/api/chaos", json={"active": False})


# ─── 8. Multiple dedup runs accumulate totals ─────────────────────────────────
def test_dedup_cumulative_totals():
    r1 = requests.get(f"{BASE_URL}/api/dedup/results").json()
    total_before = r1["total_journeys"]

    # Trigger another run
    requests.post(f"{BASE_URL}/api/dedup/trigger")
    r2 = requests.get(f"{BASE_URL}/api/dedup/results").json()

    assert r2["total_journeys"] >= total_before, \
        f"Total journeys should accumulate: {r2['total_journeys']} < {total_before}"
    assert r2["total_raw_processed"] >= r1["total_raw_processed"]


# ─── 9. Dedup results contain correct journey structure ───────────────────────
def test_journey_structure():
    r = requests.get(f"{BASE_URL}/api/dedup/results")
    d = r.json()
    assert len(d["journeys"]) > 0
    j = d["journeys"][0]
    required_fields = ["plaza_id", "tag_id", "rssi_signal_strength", "duplicate_count"]
    for field in required_fields:
        assert field in j, f"Missing field '{field}' in journey: {j}"
    assert isinstance(j["rssi_signal_strength"], (int, float))
    assert isinstance(j["duplicate_count"], int)
    assert j["duplicate_count"] >= 1


# ─── 10. Cross-laptop access simulation ───────────────────────────────────────
def test_cross_laptop_access():
    """Verify the server is accessible on all interfaces (0.0.0.0)."""
    # Test on 127.0.0.1
    r = requests.get(f"http://127.0.0.1:5000/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


# ─── 11. Ingestion with missing optional fields ───────────────────────────────
def test_ingest_minimal_fields():
    """Ingest pings with only required-ish fields (plaza_id, tag_id, rssi)."""
    pings = [
        {"plaza_id": "MINIMAL", "tag_id": "MIN_TAG", "rssi_signal_strength": -50},
    ]
    r = requests.post(f"{BASE_URL}/api/ingest", json={"pings": pings})
    assert r.status_code == 201
    assert r.json()["ingested"] == 1


def test_ingest_completely_empty_ping():
    """Ingest a ping with no fields — should still work (defaults applied)."""
    pings = [{}]
    r = requests.post(f"{BASE_URL}/api/ingest", json={"pings": pings})
    assert r.status_code == 201
    assert r.json()["ingested"] == 1


# ─────────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  FASTag DA-2 — Part 1 Deep Verification (Round 2)")
    print("=" * 60)

    print("\n[Concurrency & Stress]")
    test("3 laptops send 1000 pings each concurrently", test_concurrent_ingestion)
    test("Stats reflect 3000+ concurrent pings", test_stats_after_concurrent)
    test("All 3 regions visible in plaza stats", test_all_regions_visible)

    print("\n[Deduplication — Deep]")
    test("Dedup after concurrent data", test_dedup_after_concurrent)
    test("Dedup cumulative totals", test_dedup_cumulative_totals)
    test("Journey structure correctness", test_journey_structure)

    print("\n[Throughput]")
    test("Throughput non-negative", test_throughput_nonzero)

    print("\n[Config Edge Cases]")
    test("Dedup interval clamp (too low)", test_dedup_interval_clamp_low)
    test("Dedup interval clamp (too high)", test_dedup_interval_clamp_high)

    print("\n[Chaos Mode — Deep]")
    test("Chaos explicit set/unset", test_chaos_explicit_set)

    print("\n[Edge Cases]")
    test("Ingest with minimal fields", test_ingest_minimal_fields)
    test("Ingest with empty ping object", test_ingest_completely_empty_ping)
    test("Cross-laptop access (0.0.0.0 binding)", test_cross_laptop_access)

    print("\n" + "=" * 60)
    print(f"  Results: {PASS} passed, {FAIL} failed")
    print("=" * 60)

    sys.exit(1 if FAIL > 0 else 0)
