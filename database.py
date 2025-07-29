from pymongo import MongoClient
from datetime import datetime, timedelta
from bson import ObjectId, regex
import os
import random
import string



# Connect to MongoDB Atlas
client = MongoClient("mongodb+srv://rusoxyny:rusoxyny@cluster0.e4uj5.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
db = client["bet_tracker"]
collection = db["picks"]

def generate_short_id(length=6):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def add_pick(user, odds, stake):
    from .db import collection
    short_id = generate_short_id()
    # Ensure uniqueness (basic check)
    while collection.find_one({"short_id": short_id}):
        short_id = generate_short_id()
    
    pick = {
        "short_id": short_id,
        "user": user,
        "odds": odds,
        "stake": stake,
        "result": None,
        "timestamp": datetime.utcnow()
    }
    return collection.insert_one(pick)

    collection.insert_one({
        "user": user,
        "odds": float(odds),
        "stake": float(stake),
        "result": "pending",
        "date": datetime.utcnow()
    })

def set_result(short_id, result):
    # Find matching pick using prefix of ObjectId
    pick = collection.find_one({"_id": {"$regex": f"^{short_id}"}})
    if not pick:
        return False
# Try short_id first, fallback to ObjectId
if len(pick_id) == 24:
    filter_query = {"_id": ObjectId(pick_id)}
else:
    filter_query = {"short_id": pick_id}

collection.update_one(filter_query, {"$set": {"result": result}})

    return True

def get_pending():
    return collection.find({"result": "pending"})

def get_picks_by_user(user, period="daily"):
    now = datetime.utcnow()

    if period == "daily":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "weekly":
        start = now - timedelta(days=7)
    elif period == "monthly":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    return collection.find({
        "user": user,
        "result": {"$ne": "pending"},
        "date": {"$gte": start}
    })
