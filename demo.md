# FASTag Distributed Toll Reconciliation — Quick Demo Instructions

Step-by-step instructions for launching and testing the FASTag Distributed Ingestion, Deduplication, and DDBMS system.

---

## 🚀 Quick Launch (Single Terminal / Local Testing)

### 1. Start the Ingestion & DDBMS Server
```bash
python app.py
```
*Web Portal:* `http://localhost:5000`

### 2. Start the Synthetic Traffic Load Generator
In a second terminal:
```bash
# Streams high-frequency pings across all 10 Indian cities
python generator.py --server 127.0.0.1 --region ALL --workers 3 --batch 200 --delay 0.1
```

---

## 🌐 Multi-Laptop Network Setup

Ensure all laptops are connected to the same Wi-Fi network or private hotspot:

1. **Laptop 1 (Central Server Hub):**
   - Start the server: `python app.py`
   - Find your IP address (`hostname -I` or `ipconfig`)
   - Projected URL: `http://<LAPTOP_1_IP>:5000`

2. **Laptop 2 (Regional Generator — Delhi, Jaipur, Mumbai):**
   ```bash
   python generator.py --server <LAPTOP_1_IP> --region DELHI,JAIPUR,MUMBAI --workers 2
   ```

3. **Laptop 3 (Regional Generator — Chennai, Bengaluru, Kolkata):**
   ```bash
   python generator.py --server <LAPTOP_1_IP> --region CHENNAI,BENGALURU,KOLKATA --workers 2
   ```

---

## 🔑 Login Accounts & Credentials

Navigate to `http://localhost:5000/login` (use the quick-login chips):

1. **Global Admin:** `admin` / `admin123`
   - Access to Master Operations Dashboard (`/dashboard`)
   - Distributed SQL Query Console (`/sql_console`)
   - DDBMS Architecture Visualizer (`/ddbms`)
   - 3NF Relational Ledger Inspector (`/sql_ledger`)

2. **Regional City Stations:** `chennai` / `chennai123` *(or any city name + 123)*
   - Dedicated local station operations at `/city/<city>`
   - Local Node SQL Terminal executing directly on `data/nodes/<city>_node.db`
   - Outcome distribution and plaza revenue charts

3. **Vehicle Owners:** `ravi` / `ravi123`, `priya` / `priya123`, `amit` / `amit123`
   - Personal wallet, top-up buttons, custom amount top-up
   - RFID tag management (Lock/Unlock)
   - Filterable transaction history and CSV statement export

---

## 🧪 Testing the Test Suite
Run the automated test suites anytime:
```bash
pytest tests/ -v
```
- `tests/test_ledger.py`: Verifies ACID deduction, blocked tags, insufficient balance, idempotency index, vehicle multipliers, and impossible-travel fraud detection.
- `tests/test_api.py`: Verifies ingestion endpoints, validation, RBAC authentication, and health checks.
