# FASTag DA-2 — Demo Guide & Rehearsal Script
> **Part 3 Deliverable:** 6-Act live demo for 3 laptops over a private hotspot.

---

## 🖥️ Setup Checklist

### Laptop 1 (Server + NORTH generator)
```bash
# 1. Start the server
python app.py

# 2. Note your IP (shown in server output, e.g., 192.168.X.X)
```

### Laptop 2 (SOUTH generator)
```bash
# Only needs Python + requests installed
pip install requests

# Copy generator.py to this laptop (USB, email, or git pull)
python generator.py --server <LAPTOP_1_IP> --region SOUTH
```

### Laptop 3 (WEST generator)
```bash
pip install requests
python generator.py --server <LAPTOP_1_IP> --region WEST
```

---

## 🎬 The 6-Act Demo Script

### Act 1 — The Calm (30 seconds)
> *"This is our FASTag toll reconciliation dashboard. Right now, no traffic is flowing."*

- Show the empty dashboard at `http://<LAPTOP_1_IP>:5000`
- Point out: hero counters at zero, flat throughput chart, empty event feed, quiet India map

### Act 2 — First Wave (60 seconds)
> *"Let's start ingesting data from the NORTH region — Gurugram, Agra, Jaipur, Delhi."*

**Laptop 1** runs:
```bash
python generator.py --region NORTH --workers 2 --batch 500
```

- Watch the NORTH dots light up on the India map
- Hero counter starts spinning: ~7,000+ pings/sec
- Throughput chart rises
- Event feed starts scrolling

### Act 3 — The Flood (60 seconds)
> *"Now our teammates join from the SOUTH and WEST."*

**Laptop 2** runs:
```bash
python generator.py --server <LAPTOP_1_IP> --region SOUTH --workers 3 --batch 500
```

**Laptop 3** runs:
```bash
python generator.py --server <LAPTOP_1_IP> --region WEST --workers 3 --batch 500
```

- All 3 regions glow on the map simultaneously
- Throughput spikes to **15,000–20,000+ pings/sec** combined
- Per-plaza table fills with all 11 plazas

### Act 4 — The Filter (30 seconds)
> *"Thousands of raw pings… but how many are real journeys? Let's trigger deduplication."*

- Click **"Trigger Dedup"** on the dashboard (or use the API):
  ```bash
  curl -X POST http://<LAPTOP_1_IP>:5000/api/dedup/trigger
  ```
- Watch the **dedup ratio gauge** jump to **95-99%**
- Hero counters: e.g., *"45,000 raw → 842 journeys"*
- Event feed shows deduplicated vehicles with their strongest signal

### Act 5 — Chaos Test (45 seconds)
> *"What happens during Diwali weekend? 10× traffic spike."*

- Click the **🔴 "Simulate Peak Traffic (Diwali Weekend)"** button on the dashboard
- All 3 generators detect chaos mode and **ramp to 10× throughput**
- Throughput chart spikes dramatically
- System handles the load without crashing
- Click the button again to deactivate

### Act 6 — Kill Switch (30 seconds)
> *"Can the system survive a node failure? Let's kill Laptop 3."*

- **Laptop 3:** Press `Ctrl+C` to stop the generator
- Dashboard: WEST region dims on the map
- Other regions continue unaffected
- Throughput dips but the system stays stable
- *"The architecture is fault-tolerant — losing a data source doesn't crash the pipeline."*

---

## ⏱️ Total Demo Time: ~4.5 minutes

| Act | Duration | What Happens |
|-----|----------|-------------|
| 1 — The Calm | 30s | Show empty dashboard |
| 2 — First Wave | 60s | Laptop 1 starts NORTH |
| 3 — The Flood | 60s | Laptops 2 & 3 join (SOUTH + WEST) |
| 4 — The Filter | 30s | Trigger dedup, show massive reduction |
| 5 — Chaos Test | 45s | 10× spike via chaos mode |
| 6 — Kill Switch | 30s | Kill Laptop 3, system survives |

---

## 🛠️ CLI Reference

```
python generator.py [OPTIONS]

Options:
  --server, -s   Server IP address           (default: 127.0.0.1)
  --port, -p     Server port                 (default: 5000)
  --region, -r   NORTH | SOUTH | WEST | EAST (default: NORTH)
  --workers, -w  Number of sender threads     (default: 3)
  --batch, -b    Pings per batch per worker   (default: 500)
  --delay, -d    Seconds between batches      (default: 0.1)
  --tags, -t     Unique vehicle tag pool size  (default: 200)
```

### Tuning for Higher Throughput
```bash
# Maximum throughput (aggressive)
python generator.py --workers 5 --batch 1000 --delay 0.05

# Conservative (won't overwhelm a slow laptop)
python generator.py --workers 1 --batch 200 --delay 0.2
```

---

## 🔧 Troubleshooting

| Problem | Fix |
|---------|-----|
| `Cannot connect to server` | Check that `app.py` is running and firewall allows port 5000 |
| `ModuleNotFoundError: requests` | Run `pip install requests` |
| Low throughput | Increase `--workers` and `--batch`, decrease `--delay` |
| Chaos mode not activating | Ensure all generators can reach `/api/chaos/status` |
| Map dots not lighting up | Verify `--region` matches a known plaza group |
