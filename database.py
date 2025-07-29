from pymongo import MongoClient
from datetime import datetime, timedelta
from bson import ObjectId
import random
import string

# Connect to MongoDB Atlas
client = MongoClient("mongodb+srv://rusoxyny:rusoxyny@cluster0.e4uj5.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
db = client["bet_tracker"]
collection = db["picks"]

def generate_short_id(length=6):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def add_pick(user, odds, stake):
    short_id = generate_short_id()
    while collection.find_one({"short_id": short_id}):
        short_id = generate_short_id()
    
    pick = {
        "short_id": short_id,
        "user": user,
        "odds": float(odds),
        "stake": float(stake),
        "result": "pending",
        "date": datetime.utcnow()
    }
    collection.insert_one(pick)
    return True

def set_result(pick_id, result):
    # Try short_id first, fallback to full ObjectId if 24 chars
    if len(pick_id) == 24:
        try:
            filter_query = {"_id": ObjectId(pick_id)}
        except:
            filter_query = {"short_id": pick_id}
    else:
        filter_query = {"short_id": pick_id}

    updated = collection.update_one(filter_query, {"$set": {"result": result}})
    return updated.modified_count > 0

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
