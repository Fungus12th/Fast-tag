#!/usr/bin/env python3
"""
FASTag DA-2 — Part 3: High-Throughput Load Generator
=====================================================
Simulates RFID toll-plaza traffic from a specific geographic region and
POSTs batched pings to the Flask ingestion server.

Features:
  • Batching — sends 500+ pings per HTTP POST to bypass network I/O limits.
  • Realistic duplicates — a pool of ~200 unique tags; each tag generates
    multiple pings with fluctuating RSSI to mimic idling at a barrier.
  • Region assignment — each laptop sends data for NORTH / SOUTH / WEST plazas
    so the India map lights up independently.
  • Chaos Mode — polls /api/chaos/status every ~1 s; when active, throughput
    is multiplied by the server's chaos multiplier (default 10×).
  • Multi-laptop ready — only needs Python + requests; no Cassandra required.
    Target server IP is a CLI argument.

Usage:
  python generator.py                                  # defaults: localhost, NORTH
  python generator.py --server 192.168.1.100 --region SOUTH
  python generator.py --server 10.0.0.5 --region WEST --workers 4 --batch 800
"""

import argparse
import random
import string
import sys
import threading
import time
import uuid
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    print("ERROR: 'requests' package is required.  Install it with:")
    print("       pip install requests")
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# Plaza Registry (must match templates/index.html KNOWN_PLAZAS)
# ─────────────────────────────────────────────────────────────────────────────
PLAZA_REGISTRY = {
    "DELHI": [
        "Place1Delhi",
        "Place2Delhi",
        "Place3Delhi",
        "Place4Delhi",
    ],
    "CHENNAI": [
        "Place1Chennai",
        "Place2Chennai",
        "Place3Chennai",
    ],
    "MUMBAI": [
        "Place1Mumbai",
        "Place2Mumbai",
        "Place3Mumbai",
        "Place4Mumbai",
    ],
    "OTHER": [
        "Place1Other",
        "Place2Other",
    ],
}

LANE_IDS = ["LANE_1", "LANE_2", "LANE_3", "LANE_4"]


# ─────────────────────────────────────────────────────────────────────────────
# ANSI colour helpers (for terminal output)
# ─────────────────────────────────────────────────────────────────────────────
class C:
    """ANSI colour codes for terminal output."""
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    DIM    = "\033[2m"
    RED    = "\033[91m"
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    BLUE   = "\033[94m"
    CYAN   = "\033[96m"
    WHITE  = "\033[97m"

    @staticmethod
    def ok(msg):     return f"{C.GREEN}✅ {msg}{C.RESET}"
    @staticmethod
    def warn(msg):   return f"{C.YELLOW}⚠  {msg}{C.RESET}"
    @staticmethod
    def err(msg):    return f"{C.RED}❌ {msg}{C.RESET}"
    @staticmethod
    def info(msg):   return f"{C.CYAN}ℹ  {msg}{C.RESET}"
    @staticmethod
    def chaos(msg):  return f"{C.RED}{C.BOLD}🔥 {msg}{C.RESET}"


# ─────────────────────────────────────────────────────────────────────────────
# Tag Pool — generates a fixed pool of realistic tag IDs
# ─────────────────────────────────────────────────────────────────────────────
def generate_tag_pool(size: int = 200) -> list[str]:
    """Create a pool of unique FASTag RFID tag IDs (now strictly 9 specific cars)."""
    try:
        from owners import ALL_CARS
        return ALL_CARS
    except ImportError:
        return [f"TAG_CAR_{i}" for i in range(1, 10)]


# ─────────────────────────────────────────────────────────────────────────────
# Ping Factory — builds a batch of realistic pings
# ─────────────────────────────────────────────────────────────────────────────
def generate_ping_batch(
    batch_size: int,
    tag_pool: list[str],
    plazas: list[str],
    region: str,
) -> list[dict]:
    """
    Generate a batch of RFID pings with realistic duplicates and chaotic behavior.
    """
    import time
    now = datetime.now(timezone.utc)
    pings = []

    # Chaotic logic: Cars go "offline" for chunks of time so they don't all get 
    # equal pings. We use 45-second buckets (slightly out of sync with 30s dedup)
    time_bucket = int(time.time()) // 45
    
    active_tags = []
    for i, tag in enumerate(tag_pool):
        random.seed(time_bucket + i)
        # 40% chance the car is actively driving through a toll right now
        if random.random() < 0.4:
            active_tags.append(tag)
    
    # Reset random seed back to pure randomness for the actual ping generation
    random.seed()
    
    # If no cars are driving, just pick one randomly to keep data flowing
    if not active_tags:
        active_tags = [random.choice(tag_pool)]

    for _ in range(batch_size):
        tag = random.choice(active_tags)
        
        # Also limit plazas dynamically to create plaza visit imbalance
        random.seed(time_bucket + hash(tag))
        active_plaza = random.choice(plazas)
        random.seed()
        
        plaza = active_plaza

        # Base RSSI for this particular ping: -25 to -65 dBm + jitter
        base_rssi = random.uniform(-65.0, -25.0)
        rssi = round(base_rssi + random.gauss(0, 3.0), 1)

        pings.append({
            "ping_id":               str(uuid.uuid4()),
            "plaza_id":              plaza,
            "tag_id":                tag,
            "rssi_signal_strength":  rssi,
            "ping_timestamp":        now.isoformat(),
            "lane_id":               random.choice(LANE_IDS),
            "region":                next((r for r, pl in PLAZA_REGISTRY.items() if plaza in pl), region),
        })

    return pings


# ─────────────────────────────────────────────────────────────────────────────
# Chaos Mode Monitor
# ─────────────────────────────────────────────────────────────────────────────
class ChaosMonitor:
    """Background thread that polls /api/chaos/status."""

    def __init__(self, base_url: str, poll_interval: float = 1.0):
        self.base_url = base_url
        self.poll_interval = poll_interval
        self.active = False
        self.multiplier = 1
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _run(self):
        url = f"{self.base_url}/api/chaos/status"
        while not self._stop.is_set():
            try:
                resp = requests.get(url, timeout=2)
                if resp.ok:
                    data = resp.json()
                    was_active = self.active
                    self.active = data.get("active", False)
                    self.multiplier = data.get("multiplier", 10) if self.active else 1

                    # Log transitions
                    if self.active and not was_active:
                        print(f"\n{C.chaos('CHAOS MODE ACTIVATED — ramping to ' + str(self.multiplier) + 'x throughput!')}")
                    elif not self.active and was_active:
                        print(f"\n{C.info('Chaos mode deactivated — returning to baseline.')}")
            except requests.RequestException:
                pass  # Server might be briefly unreachable
            self._stop.wait(self.poll_interval)


# ─────────────────────────────────────────────────────────────────────────────
# Worker — sends batches to the server
# ─────────────────────────────────────────────────────────────────────────────
class IngestWorker:
    """
    A single worker thread that continuously generates and sends ping batches.
    """

    def __init__(
        self,
        worker_id: int,
        base_url: str,
        tag_pool: list[str],
        plazas: list[str],
        region: str,
        batch_size: int,
        base_delay: float,
        chaos_monitor: ChaosMonitor,
        stats: dict,
        stats_lock: threading.Lock,
    ):
        self.worker_id = worker_id
        self.base_url = base_url
        self.tag_pool = tag_pool
        self.plazas = plazas
        self.region = region
        self.batch_size = batch_size
        self.base_delay = base_delay
        self.chaos = chaos_monitor
        self.stats = stats
        self.stats_lock = stats_lock
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _run(self):
        url = f"{self.base_url}/api/ingest"
        session = requests.Session()
        consecutive_errors = 0

        while not self._stop.is_set():
            # Determine effective batch size and delay under chaos
            effective_batch = self.batch_size
            effective_delay = self.base_delay
            if self.chaos.active and self.chaos.multiplier > 1:
                # Increase batch size AND decrease delay to achieve multiplier
                effective_batch = int(self.batch_size * min(self.chaos.multiplier, 5))
                effective_delay = self.base_delay / min(self.chaos.multiplier, 5)

            pings = generate_ping_batch(
                effective_batch, self.tag_pool, self.plazas, self.region
            )

            try:
                resp = session.post(url, json={"pings": pings}, timeout=10)
                if resp.ok:
                    data = resp.json()
                    with self.stats_lock:
                        self.stats["total_sent"] += data.get("ingested", len(pings))
                        self.stats["batches_sent"] += 1
                        self.stats["errors"] = max(0, self.stats["errors"])  # keep existing
                    consecutive_errors = 0
                else:
                    with self.stats_lock:
                        self.stats["errors"] += 1
                    consecutive_errors += 1
            except requests.RequestException:
                with self.stats_lock:
                    self.stats["errors"] += 1
                consecutive_errors += 1

            # Back-off on repeated failures
            if consecutive_errors > 10:
                self._stop.wait(2.0)
            elif consecutive_errors > 0:
                self._stop.wait(0.5)
            else:
                self._stop.wait(max(effective_delay, 0.01))


# ─────────────────────────────────────────────────────────────────────────────
# Stats Printer
# ─────────────────────────────────────────────────────────────────────────────
class StatsPrinter:
    """Periodically prints throughput stats to the terminal."""

    def __init__(
        self,
        stats: dict,
        stats_lock: threading.Lock,
        chaos_monitor: ChaosMonitor,
        interval: float = 2.0,
    ):
        self.stats = stats
        self.stats_lock = stats_lock
        self.chaos = chaos_monitor
        self.interval = interval
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._last_total = 0
        self._last_time = time.time()

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _run(self):
        while not self._stop.is_set():
            self._stop.wait(self.interval)
            if self._stop.is_set():
                break

            now = time.time()
            elapsed = now - self._last_time

            with self.stats_lock:
                total = self.stats["total_sent"]
                batches = self.stats["batches_sent"]
                errors = self.stats["errors"]

            delta = total - self._last_total
            pps = delta / elapsed if elapsed > 0 else 0
            self._last_total = total
            self._last_time = now

            chaos_tag = f" {C.RED}[CHAOS {self.chaos.multiplier}x]{C.RESET}" if self.chaos.active else ""
            print(
                f"  {C.DIM}│{C.RESET} "
                f"{C.BOLD}{C.WHITE}Sent:{C.RESET} {total:>10,}   "
                f"{C.CYAN}PPS:{C.RESET} {pps:>8,.0f}   "
                f"{C.BLUE}Batches:{C.RESET} {batches:>7,}   "
                f"{C.RED if errors else C.GREEN}Errors:{C.RESET} {errors:>4}"
                f"{chaos_tag}",
                end="\r\n",
            )


# ─────────────────────────────────────────────────────────────────────────────
# Server Health Check
# ─────────────────────────────────────────────────────────────────────────────
def check_server(base_url: str) -> bool:
    """Verify the ingestion server is reachable."""
    try:
        resp = requests.get(f"{base_url}/api/health", timeout=5)
        if resp.ok:
            data = resp.json()
            print(C.ok(f"Server reachable — {data.get('storage_backend', '?')} backend"))
            return True
        else:
            print(C.err(f"Server returned HTTP {resp.status_code}"))
            return False
    except requests.ConnectionError:
        print(C.err(f"Cannot connect to {base_url} — is the server running?"))
        return False
    except requests.Timeout:
        print(C.err(f"Connection to {base_url} timed out"))
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="FASTag DA-2 — High-Throughput Load Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                        # localhost, NORTH region
  %(prog)s --server 192.168.1.100 --region SOUTH  # remote server, SOUTH
  %(prog)s --region WEST --workers 4 --batch 800  # 4 workers, 800 pings/batch
  %(prog)s --server 10.0.0.5 --tags 500           # larger tag pool (more unique vehicles)
        """,
    )
    parser.add_argument(
        "--server", "-s",
        default="127.0.0.1",
        help="IP address or hostname of the Flask server (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port", "-p",
        type=int, default=5000,
        help="Port of the Flask server (default: 5000)",
    )
    parser.add_argument(
        "--region", "-r",
        choices=["ALL", "DELHI", "CHENNAI", "MUMBAI", "OTHER"],
        default="ALL",
        help="Geographic region this generator simulates (default: NORTH)",
    )
    parser.add_argument(
        "--workers", "-w",
        type=int, default=3,
        help="Number of concurrent sender threads (default: 3)",
    )
    parser.add_argument(
        "--batch", "-b",
        type=int, default=500,
        help="Pings per batch per worker (default: 500)",
    )
    parser.add_argument(
        "--delay", "-d",
        type=float, default=0.1,
        help="Seconds between batches per worker at baseline (default: 0.1)",
    )
    parser.add_argument(
        "--tags", "-t",
        type=int, default=50000,
        help="Size of the unique tag pool (default: 50000)",
    )

    args = parser.parse_args()

    base_url = f"http://{args.server}:{args.port}"
    region = args.region
    if region == "ALL":
        plazas = [p for r in PLAZA_REGISTRY.values() for p in r]
    else:
        plazas = PLAZA_REGISTRY.get(region, PLAZA_REGISTRY["DELHI"])

    # ─── Banner ──────────────────────────────────────────────────────────
    print(f"""
{C.BOLD}{C.CYAN}════════════════════════════════════════════════════════════════
  FASTag DA-2 — Load Generator (Part 3)
════════════════════════════════════════════════════════════════{C.RESET}
  {C.WHITE}Server:{C.RESET}     {base_url}
  {C.WHITE}Region:{C.RESET}     {region}
  {C.WHITE}Plazas:{C.RESET}     {', '.join(plazas)}
  {C.WHITE}Workers:{C.RESET}    {args.workers}
  {C.WHITE}Batch size:{C.RESET} {args.batch} pings/batch
  {C.WHITE}Base delay:{C.RESET} {args.delay}s between batches
  {C.WHITE}Tag pool:{C.RESET}   {args.tags} unique vehicles
{C.BOLD}{C.CYAN}════════════════════════════════════════════════════════════════{C.RESET}
""")

    # ─── Health check ────────────────────────────────────────────────────
    print(C.info("Checking server connectivity..."))
    if not check_server(base_url):
        print(C.err("Aborting — fix the connection and retry."))
        sys.exit(1)

    # ─── Setup ───────────────────────────────────────────────────────────
    tag_pool = generate_tag_pool(args.tags)
    print(C.ok(f"Generated {len(tag_pool)} unique tag IDs"))

    stats = {"total_sent": 0, "batches_sent": 0, "errors": 0}
    stats_lock = threading.Lock()

    # Start chaos monitor
    chaos_monitor = ChaosMonitor(base_url, poll_interval=1.0)
    chaos_monitor.start()
    print(C.ok("Chaos mode monitor started (polling every 1s)"))

    # Start workers
    workers = []
    for i in range(args.workers):
        w = IngestWorker(
            worker_id=i,
            base_url=base_url,
            tag_pool=tag_pool,
            plazas=plazas,
            region=region,
            batch_size=args.batch,
            base_delay=args.delay,
            chaos_monitor=chaos_monitor,
            stats=stats,
            stats_lock=stats_lock,
        )
        w.start()
        workers.append(w)
    print(C.ok(f"Started {len(workers)} worker threads"))

    # Start stats printer
    printer = StatsPrinter(stats, stats_lock, chaos_monitor, interval=2.0)
    printer.start()

    print(f"\n{C.BOLD}{C.GREEN}  🚀 Generator running — press Ctrl+C to stop{C.RESET}\n")

    # ─── Run until interrupted ───────────────────────────────────────────
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass

    # ─── Graceful shutdown ───────────────────────────────────────────────
    print(f"\n\n{C.info('Shutting down...')}")
    printer.stop()
    for w in workers:
        w.stop()
    chaos_monitor.stop()

    with stats_lock:
        final_total = stats["total_sent"]
        final_batches = stats["batches_sent"]
        final_errors = stats["errors"]

    print(f"""
{C.BOLD}{C.CYAN}════════════════════════════════════════════════════════════════
  Generator Stopped — Final Stats
════════════════════════════════════════════════════════════════{C.RESET}
  {C.WHITE}Total pings sent:{C.RESET}  {final_total:,}
  {C.WHITE}Total batches:{C.RESET}     {final_batches:,}
  {C.WHITE}Errors:{C.RESET}            {final_errors:,}
{C.BOLD}{C.CYAN}════════════════════════════════════════════════════════════════{C.RESET}
""")


if __name__ == "__main__":
    main()
