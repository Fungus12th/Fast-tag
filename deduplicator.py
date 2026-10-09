"""
FASTag DA-2 â€” Batch Deduplication Worker
Periodically scans recent pings, groups by tag_id, picks the one with highest RSSI
(closest to antenna) per tag per plaza, and produces "billable journeys."
"""

import threading
import time
from collections import defaultdict
from datetime import datetime, timezone

import config


class BatchDeduplicator:
    """
    Background worker that deduplicates raw RFID pings into clean journeys.

    Logic:
      1. Grab all pings from the last N seconds (configurable window).
      2. Group by (plaza_id, tag_id).
      3. For each group, pick the ping with the highest rssi_signal_strength
         (closest to the toll antenna = most accurate read).
      4. That "winning" ping becomes a billable journey.
      5. Track stats: raw count, journey count, dedup ratio.
    """

    def __init__(self, storage):
        self._storage = storage
        self._lock = threading.Lock()
        self._run_lock = threading.Lock()
        self._timer = None
        self._running = False

        # Configurable interval
        self._interval = config.DEDUP_INTERVAL_SECONDS

        # Latest dedup results
        self._last_run_at = None
        self._last_raw_count = 0
        self._last_journey_count = 0
        self._last_dedup_ratio = 0.0
        self._last_journeys = []       # The "winning" deduplicated records

        # Cumulative totals across all runs
        self._total_raw_processed = 0
        self._total_journeys = 0

    # â”€â”€â”€ Public Interface â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def is_running(self) -> bool:
        return self._running

    def start(self):
        """Start the periodic dedup worker."""
        if self._running:
            return
        self._running = True
        self._schedule_next()
        print(f"[DEDUP] Worker started â€” running every {self._interval}s")

    def stop(self):
        """Stop the periodic dedup worker."""
        self._running = False
        if self._timer:
            self._timer.cancel()
            self._timer = None
        print("[DEDUP] Worker stopped")

    def trigger_now(self):
        """Manually trigger a dedup run (called from the dashboard button)."""
        return self._run_dedup()

    def set_interval(self, seconds: int):
        """Update the dedup interval. Takes effect on the next cycle."""
        self._interval = max(5, min(seconds, 300))  # Clamp between 5s and 5min
        print(f"[DEDUP] Interval updated to {self._interval}s")

    def get_interval(self) -> int:
        return self._interval

    def get_results(self) -> dict:
        """Get the latest dedup run results."""
        with self._lock:
            return {
                "last_run_at":          self._last_run_at,
                "last_raw_count":       self._last_raw_count,
                "last_journey_count":   self._last_journey_count,
                "last_dedup_ratio":     self._last_dedup_ratio,
                "total_raw_processed":  self._total_raw_processed,
                "total_journeys":       self._total_journeys,
                "journeys":            self._last_journeys[-50:],  # Last 50 for the event feed
            }

    # â”€â”€â”€ Internal â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _schedule_next(self):
        """Schedule the next dedup run."""
        if not self._running:
            return
        self._timer = threading.Timer(self._interval, self._tick)
        self._timer.daemon = True
        self._timer.start()

    def _tick(self):
        """Timer callback â€” run dedup and reschedule."""
        try:
            self._run_dedup()
        except Exception as e:
            print(f"[DEDUP] Error during dedup run: {e}")
        finally:
            self._schedule_next()

    def _run_dedup(self) -> dict:
        """Core deduplication logic."""
        with self._run_lock:
            window = config.DEDUP_TIME_WINDOW_SECONDS
            recent_pings = self._storage.get_recent_pings(window_seconds=window)
            raw_count = len(recent_pings)
            
            # Use actual total ingested as authoritative cumulative raw count
            true_total_raw = getattr(self._storage, 'get_total_ingested', lambda: self._total_raw_processed)()

            # Group by (plaza_id, tag_id) â†’ pick highest RSSI
            groups = defaultdict(list)
            for ping in recent_pings:
                key = (ping["plaza_id"], ping["tag_id"])
                groups[key].append(ping)

            journeys = []
            for (plaza_id, tag_id), pings in groups.items():
                # Winner = highest RSSI (closest to antenna)
                winner = max(pings, key=lambda p: p["rssi_signal_strength"])
                journeys.append({
                    "plaza_id":             plaza_id,
                    "tag_id":               tag_id,
                    "rssi_signal_strength": winner["rssi_signal_strength"],
                    "ping_timestamp":       winner.get("ping_timestamp", ""),
                    "lane_id":              winner.get("lane_id", ""),
                    "region":               winner.get("region", ""),
                    "duplicate_count":      len(pings),
                })

            journey_count = len(journeys)
            dedup_ratio = round(
                ((raw_count - journey_count) / raw_count * 100) if raw_count > 0 else 0.0,
                2,
            )

            now_iso = datetime.now(timezone.utc).isoformat()

            with self._lock:
                self._last_run_at = now_iso
                self._last_raw_count = raw_count
                self._last_journey_count = journey_count
                self._last_dedup_ratio = dedup_ratio
                self._last_journeys = journeys
                self._total_raw_processed = true_total_raw() if callable(true_total_raw) else true_total_raw
                self._total_journeys += journey_count

            print(
                f"[DEDUP] Run complete: {raw_count} raw pings -> {journey_count} journeys "
                f"({dedup_ratio}% duplicates filtered)"
            )

            # Temp storage for the output
            try:
                import json
                import os
                out_file = "batch_output.json"
                existing = []
                if os.path.exists(out_file):
                    with open(out_file, "r") as f:
                        try:
                            existing = json.load(f)
                        except json.JSONDecodeError:
                            pass
                existing.extend(journeys)
                with open(out_file, "w") as f:
                    json.dump(existing, f, indent=4)
            except Exception as e:
                print(f"[DEDUP] Error saving temp output: {e}")


            return {
                "raw_count":     raw_count,
                "journey_count": journey_count,
                "dedup_ratio":   dedup_ratio,
                "timestamp":     now_iso,
            }



