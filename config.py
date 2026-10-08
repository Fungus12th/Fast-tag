"""
FASTag DA-2 — Configuration
Centralizes all tunable parameters for the server, database, and deduplication worker.
"""

import os

# ─── Flask Server ───────────────────────────────────────────────────────────────
SERVER_HOST = os.getenv("FASTAG_HOST", "0.0.0.0")   # Bind to all interfaces for cross-laptop access
SERVER_PORT = int(os.getenv("FASTAG_PORT", 5000))
DEBUG_MODE  = os.getenv("FASTAG_DEBUG", "true").lower() == "true"

# ─── Cassandra ──────────────────────────────────────────────────────────────────
CASSANDRA_CONTACT_POINTS = os.getenv("CASSANDRA_HOSTS", "127.0.0.1").split(",")
CASSANDRA_PORT           = int(os.getenv("CASSANDRA_PORT", 9042))
CASSANDRA_KEYSPACE       = "fastag_telemetry"
CASSANDRA_TABLE          = "raw_rfid_pings"

# ─── Storage Mode ───────────────────────────────────────────────────────────────
# "cassandra" — use live Cassandra cluster
# "memory"    — pure in-memory (for dev / mock / when Cassandra is not installed)
# "auto"      — try Cassandra first, fall back to memory
STORAGE_MODE = os.getenv("FASTAG_STORAGE", "auto")

# ─── Deduplication Worker ───────────────────────────────────────────────────────
DEDUP_INTERVAL_SECONDS  = int(os.getenv("DEDUP_INTERVAL", 30))       # Run dedup every N seconds
DEDUP_TIME_WINDOW_SECONDS = int(os.getenv("DEDUP_WINDOW", 60))       # Look-back window for dedup
DEDUP_AUTO_START        = os.getenv("DEDUP_AUTO_START", "true").lower() == "true"

# ─── Chaos Mode ─────────────────────────────────────────────────────────────────
CHAOS_MULTIPLIER = int(os.getenv("CHAOS_MULTIPLIER", 10))            # 10x throughput on chaos

# ─── In-Memory Limits ──────────────────────────────────────────────────────────
MAX_RAW_PINGS_IN_MEMORY = int(os.getenv("MAX_RAW_PINGS", 500_000))   # Cap to prevent OOM

# ─── Throughput Tracking ────────────────────────────────────────────────────────
THROUGHPUT_WINDOW_SECONDS = int(os.getenv("THROUGHPUT_WINDOW", 5))    # Sliding window for PPS calc
