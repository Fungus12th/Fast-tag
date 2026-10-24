OWNER_DATA = {
    "owner1":  {"name": "Ravi Kumar",       "username": "ravi",     "cars": ["Car1Ravi",    "Car2Ravi",    "Car3Ravi"]},
    "owner2":  {"name": "Priya Sharma",     "username": "priya",    "cars": ["Car1Priya",   "Car2Priya",   "Car3Priya"]},
    "owner3":  {"name": "Amit Patel",       "username": "amit",     "cars": ["Car1Amit",    "Car2Amit",    "Car3Amit"]},
    "owner4":  {"name": "Sneha Reddy",      "username": "sneha",    "cars": ["Car1Sneha",   "Car2Sneha",   "Car3Sneha"]},
    "owner5":  {"name": "Vikram Singh",     "username": "vikram",   "cars": ["Car1Vikram",  "Car2Vikram",  "Car3Vikram"]},
    "owner6":  {"name": "Ananya Das",       "username": "ananya",   "cars": ["Car1Ananya",  "Car2Ananya",  "Car3Ananya"]},
    "owner7":  {"name": "Rohan Mehta",      "username": "rohan",    "cars": ["Car1Rohan",   "Car2Rohan",   "Car3Rohan"]},
    "owner8":  {"name": "Kavita Joshi",     "username": "kavita",   "cars": ["Car1Kavita",  "Car2Kavita",  "Car3Kavita"]},
    "owner9":  {"name": "Arjun Nair",       "username": "arjun",    "cars": ["Car1Arjun",   "Car2Arjun",   "Car3Arjun"]},
    "owner10": {"name": "Meera Iyer",       "username": "meera",    "cars": ["Car1Meera",   "Car2Meera",   "Car3Meera"]},
}

ALL_CARS = []
for info in OWNER_DATA.values():
    ALL_CARS.extend(info["cars"])
