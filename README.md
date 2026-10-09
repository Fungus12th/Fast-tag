# FASTag High-Frequency Toll Reconciliation Ledger

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

A hybrid polyglot-persistence design for real-time highway toll collection. This project simulates a high-frequency FASTag RFID ingestion engine capable of processing tens of thousands of pings per second, deduplicating them into clean journey records, and visualizing the live network traffic across India.

---

## 🏗 Architecture Overview

1. **The Generators (`generator.py`):** Simulate toll plazas at various geographic locations (Delhi, Mumbai, Chennai) pinging the central server with raw RFID data.
2. **The Ingestion Server (`app.py`):** A Flask backend that receives raw pings and stores them instantly. It uses an adaptive storage fallback mechanism (starts with ultra-fast `InMemoryStorage` and scales to distributed `Cassandra`).
3. **The Deduplicator:** A background worker running in the central server that sweeps raw pings every 30 seconds to extract clean, deduplicated vehicle journeys.
4. **The Live Dashboard:** A web-based visualizer that provides a real-time, zero-refresh look at the network's throughput and deduplication metrics, complete with an interactive map of India.

---

## 🚀 Getting Started (Single Machine)

### 1. Prerequisites
Ensure you have Python installed. Clone the repository and install the backend dependencies on your main machine:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install flask cassandra-driver requests
```

### 2. Start the Main Server
Launch the central Ingestion API and Dashboard server:
```bash
python app.py
```
*The server will boot up using `InMemoryStorage` by default. You can now visit `http://localhost:5000` in your browser.*

### 3. Start a Local Data Generator
In a new terminal window (ensure your `.venv` is activated), start pumping simulated data:
```bash
python generator.py --region DELHI --workers 2
```

---

## 🌐 The Multi-Laptop Demo Setup

To truly see the system shine, you can run the generators on entirely different laptops connected to the same Wi-Fi network, pointing them all at your main server.

### Step 1: Find your Main Server's IP Address
On the laptop running `app.py`, open a terminal and run:
```bash
hostname -I
```
*(Take note of the IP address, e.g., `192.168.1.100`)*

### Step 2: Prepare the "Client" Laptops
On any other laptop on the same network, copy over `generator.py` and install the required library in a virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install requests
```

### Step 3: Unleash the Data!
Run the generator on the client laptops, pointing them to the Main Server's IP. 

**Delhi Laptop:**
```bash
python generator.py --server 192.168.1.100 --region DELHI --workers 2
```
**Mumbai Laptop:**
```bash
python generator.py --server 192.168.1.100 --region MUMBAI --workers 2
```
**Chennai Laptop:**
```bash
python generator.py --server 192.168.1.100 --region CHENNAI --workers 2
```

Watch the live map light up instantly on your main server's dashboard at `http://localhost:5000`!

---

## ⚙️ Configuration & Controls

- **Raw Database View:** Visit `http://localhost:5000/database` to watch the raw JSON ingestion stream in real-time.
- **Deduplication Interval:** Use the slider on the main dashboard to control how often the backend deduplicator sweeps the raw data for clean journeys.
- **Generator Throttle:** You can increase the load by adding more workers or increasing the batch size:
  ```bash
  python generator.py --server 192.168.1.100 --region DELHI --workers 5 --batch 1000
  ```

## 🧹 Resetting the Data
Because the application leverages high-speed in-memory storage, wiping the slate clean is as simple as restarting the `app.py` script. All counters, logs, and database entries will reset to zero.
