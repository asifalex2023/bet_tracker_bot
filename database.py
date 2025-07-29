from pymongo import MongoClient
from datetime import datetime, timedelta
from bson import ObjectId
import random, string

client = MongoClient("mongodb+srv://rusoxyny:rusoxyny@cluster0.e4uj5.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
db         = client["bet_tracker"]
collection = db["picks"]

def generate_short_id(length=6):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

# … add_pick, set_result, get_pending stay unchanged …

def get_picks_by_user(user, period="daily"):
    # identical to what you already had
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
        "date":  {"$gte": start}
    })

# NEW ↓↓↓ ---------------------------------------------------
def get_all_users():
    "Return a sorted list of distinct user names that have *any* finished pick."
    return sorted(collection.distinct("user", {"result": {"$ne": "pending"}}))

def reset_database():
    "Danger – deletes every document in the picks collection."
    collection.delete_many({})
