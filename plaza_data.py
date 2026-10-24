"""
FASTag Shared Plaza & City Registry (Single Source of Truth)
============================================================
Consolidated master definitions for 10 regional metros, 30 toll plazas,
base rates, highways, and regional node mappings.
"""

CITIES_METADATA = {
    "DELHI": {
        "city_name": "New Delhi",
        "node_id": "NODE_DELHI_01",
        "highway": "NH-44 / Delhi-Meerut Expy",
        "predicate": "σ(region = 'DELHI')",
        "plazas": [
            (201, "Place1Delhi", "NH-44", 95.00, "DELHI"),
            (202, "Place2Delhi", "Delhi-Meerut Expy", 85.00, "DELHI"),
            (203, "Place3Delhi", "NH-48", 105.00, "DELHI"),
        ]
    },
    "KOLKATA": {
        "city_name": "Kolkata",
        "node_id": "NODE_KOLKATA_01",
        "highway": "NH-16 / NH-19 / Durgapur Expy",
        "predicate": "σ(region = 'KOLKATA')",
        "plazas": [
            (204, "Place1Kolkata", "NH-16", 70.00, "KOLKATA"),
            (205, "Place2Kolkata", "NH-19", 80.00, "KOLKATA"),
            (206, "Place3Kolkata", "Kolkata-Durgapur Expy", 90.00, "KOLKATA"),
        ]
    },
    "MUMBAI": {
        "city_name": "Mumbai",
        "node_id": "NODE_MUMBAI_01",
        "highway": "Mumbai-Pune Expy / Sea Link",
        "predicate": "σ(region = 'MUMBAI')",
        "plazas": [
            (207, "Place1Mumbai", "Mumbai-Pune Expy", 120.00, "MUMBAI"),
            (208, "Place2Mumbai", "Eastern Freeway", 80.00, "MUMBAI"),
            (209, "Place3Mumbai", "Bandra-Worli Sealink", 95.00, "MUMBAI"),
        ]
    },
    "BENGALURU": {
        "city_name": "Bengaluru",
        "node_id": "NODE_BENGALURU_01",
        "highway": "NICE Road / Mysuru Expy",
        "predicate": "σ(region = 'BENGALURU')",
        "plazas": [
            (210, "Place1Bengaluru", "NICE Road", 85.00, "BENGALURU"),
            (211, "Place2Bengaluru", "NH-44 South", 75.00, "BENGALURU"),
            (212, "Place3Bengaluru", "Bengaluru-Mysuru Expy", 110.00, "BENGALURU"),
        ]
    },
    "CHENNAI": {
        "city_name": "Chennai",
        "node_id": "NODE_CHENNAI_01",
        "highway": "OMR / GST Road / NH-16",
        "predicate": "σ(region = 'CHENNAI')",
        "plazas": [
            (213, "Place1Chennai", "Grand Southern Trunk", 75.00, "CHENNAI"),
            (214, "Place2Chennai", "OMR IT Corridor", 65.00, "CHENNAI"),
            (215, "Place3Chennai", "NH-16 East", 90.00, "CHENNAI"),
        ]
    },
    "HYDERABAD": {
        "city_name": "Hyderabad",
        "node_id": "NODE_HYDERABAD_01",
        "highway": "ORR / NH-65",
        "predicate": "σ(region = 'HYDERABAD')",
        "plazas": [
            (216, "Place1Hyderabad", "ORR Hyderabad", 60.00, "HYDERABAD"),
            (217, "Place2Hyderabad", "NH-65", 85.00, "HYDERABAD"),
            (218, "Place3Hyderabad", "Hyderabad-Vijayawada", 100.00, "HYDERABAD"),
        ]
    },
    "AHMEDABAD": {
        "city_name": "Ahmedabad",
        "node_id": "NODE_AHMEDABAD_01",
        "highway": "NH-48 West / SG Highway",
        "predicate": "σ(region = 'AHMEDABAD')",
        "plazas": [
            (219, "Place1Ahmedabad", "NH-48 West", 70.00, "AHMEDABAD"),
            (220, "Place2Ahmedabad", "Ahmedabad-Vadodara Expy", 95.00, "AHMEDABAD"),
            (221, "Place3Ahmedabad", "SG Highway", 55.00, "AHMEDABAD"),
        ]
    },
    "SURAT": {
        "city_name": "Surat",
        "node_id": "NODE_SURAT_01",
        "highway": "NH-48 Surat / Diamond Bridge",
        "predicate": "σ(region = 'SURAT')",
        "plazas": [
            (222, "Place1Surat", "NH-48 Surat", 65.00, "SURAT"),
            (223, "Place2Surat", "Diamond Bridge Expy", 75.00, "SURAT"),
            (224, "Place3Surat", "Surat-Hazira Road", 60.00, "SURAT"),
        ]
    },
    "PUNE": {
        "city_name": "Pune",
        "node_id": "NODE_PUNE_01",
        "highway": "NH-48 Pune / Satara NH",
        "predicate": "σ(region = 'PUNE')",
        "plazas": [
            (225, "Place1Pune", "NH-48 Pune", 90.00, "PUNE"),
            (226, "Place2Pune", "Pune-Satara NH", 80.00, "PUNE"),
            (227, "Place3Pune", "Pune-Bengaluru Expy", 105.00, "PUNE"),
        ]
    },
    "JAIPUR": {
        "city_name": "Jaipur",
        "node_id": "NODE_JAIPUR_01",
        "highway": "Delhi-Jaipur Expy / Ring Road",
        "predicate": "σ(region = 'JAIPUR')",
        "plazas": [
            (228, "Place1Jaipur", "Delhi-Jaipur Expy", 100.00, "JAIPUR"),
            (229, "Place2Jaipur", "NH-48 Jaipur", 85.00, "JAIPUR"),
            (230, "Place3Jaipur", "Jaipur Ring Road", 60.00, "JAIPUR"),
        ]
    }
}

# Simplified view for sql_ledger.py
CITIES = {
    city_k: {
        "name": meta["city_name"],
        "plazas": [p[1] for p in meta["plazas"]],
        "highway": meta["highway"]
    }
    for city_k, meta in CITIES_METADATA.items()
}

# Generator registry view {CITY: [plaza_names]}
PLAZA_REGISTRY = {
    city_k: [p[1] for p in meta["plazas"]]
    for city_k, meta in CITIES_METADATA.items()
}

# All 30 plaza 5-tuples: (plaza_id, plaza_name, highway_name, base_toll_rate, region)
ALL_PLAZA_ROWS = [
    plaza_tuple
    for meta in CITIES_METADATA.values()
    for plaza_tuple in meta["plazas"]
]

# Fast lookup mappings
PLAZA_ID_TO_CITY = {}
PLAZA_NAME_TO_CITY = {}
for city_k, data in CITIES_METADATA.items():
    for pid, pname, hwy, rate, reg in data["plazas"]:
        PLAZA_ID_TO_CITY[pid] = city_k
        PLAZA_NAME_TO_CITY[pname.lower()] = city_k
