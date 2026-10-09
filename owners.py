OWNER_DATA = {
    "owner1": {
        "name": "Ravi Kumar",
        "username": "ravi",
        "cars": ["Car1Ravi", "Car2Ravi", "Car3Ravi"]
    },
    "owner2": {
        "name": "Priya Sharma",
        "username": "priya",
        "cars": ["Car1Priya", "Car2Priya", "Car3Priya"]
    },
    "owner3": {
        "name": "Amit Patel",
        "username": "amit",
        "cars": ["Car1Amit", "Car2Amit", "Car3Amit"]
    }
}

ALL_CARS = []
for info in OWNER_DATA.values():
    ALL_CARS.extend(info["cars"])
