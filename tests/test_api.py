import pytest
import app

@pytest.fixture
def client():
    app.app.config["TESTING"] = True
    with app.app.test_client() as client:
        yield client

def test_ingest_accepts_valid_batch(client):
    payload = {
        "pings": [
            {
                "tag_id": "Car1Ravi",
                "plaza_id": "Place1Delhi",
                "rssi_signal_strength": -45.2,
                "lane_id": "LANE_1",
                "region": "DELHI"
            }
        ]
    }
    res = client.post("/api/ingest", json=payload)
    assert res.status_code == 201
    assert res.get_json()["status"] == "ok"

def test_ingest_rejects_empty(client):
    res = client.post("/api/ingest", json={"pings": []})
    assert res.status_code == 400

    res2 = client.post("/api/ingest", json={})
    assert res2.status_code == 400

def test_sql_execute_requires_auth(client):
    res = client.post("/api/sql/execute", json={"query": "SELECT 1;"})
    assert res.status_code == 403
    assert "Unauthorized" in res.get_json()["error"]

def test_login_admin(client):
    res = client.post("/login", data={"username": "admin", "password": "admin123"}, follow_redirects=False)
    assert res.status_code == 302
    assert res.headers["Location"].endswith("/dashboard")

def test_login_owner(client):
    res = client.post("/login", data={"username": "ravi", "password": "ravi123"}, follow_redirects=False)
    assert res.status_code == 302
    assert res.headers["Location"].endswith("/portal/ravi")

def test_health_endpoint(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.get_json()
    assert "status" in data
    assert "storage_backend" in data
    assert "timestamp" in data
