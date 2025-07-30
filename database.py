# database.py
from pymongo import MongoClient
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo        # ← NEW

DHAKA = ZoneInfo("Asia/Dhaka")       # ← NEW
from bson import ObjectId
import random
import string

# ────────── Mongo connection ──────────
client = MongoClient(
    "mongodb+srv://rusoxyny:rusoxyny@cluster0.e4uj5.mongodb.net/"
    "?retryWrites=true&w=majority&appName=Cluster0"
)
db         = client["bet_tracker"]
collection = db["picks"]

# ────────── helpers ──────────
def generate_short_id() -> str:
    """
    Return a UNIQUE two–digit string (“00” … “99”).
    Uses a counter document in Mongo to stay sequential and avoid clashes.
    """
    counter = db["counters"].find_one_and_update(
        {"_id": "pick_id"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True,
    )
    seq = (counter["seq"] - 1) % 100             # wrap after 99 → 00
    short_id = f"{seq:02}"

    # safety-net: keep advancing until we hit an unused id
    while collection.find_one({"short_id": short_id}):
        counter = db["counters"].find_one_and_update(
            {"_id": "pick_id"},
            {"$inc": {"seq": 1}},
            upsert=True,
            return_document=True,
        )
        seq = (counter["seq"] - 1) % 100
        short_id = f"{seq:02}"
    return short_id

# ────────── CRUD functions ──────────
def add_pick(user: str, odds: float, stake: float) -> bool:
    short_id = generate_short_id()
    while collection.find_one({"short_id": short_id}):
        short_id = generate_short_id()

    pick = {
        "short_id": short_id,
        "user":     user,
        "odds":     float(odds),
        "stake":    float(stake),
        "result":   "pending",
        "date":     datetime.utcnow(),
    }
    collection.insert_one(pick)
    return True

def set_result(pick_id: str, result: str) -> bool:
    # accept either 24-char ObjectId or our 2-digit short id
    if len(pick_id) == 24:
        try:
            flt = {"_id": ObjectId(pick_id)}
        except Exception:
            flt = {"short_id": pick_id}
    else:
        flt = {"short_id": pick_id}

    upd = collection.update_one(flt, {"$set": {"result": result.lower()}})
    return upd.modified_count > 0

def get_pending():
    return collection.find({"result": "pending"})

def get_picks_by_user(user: str, period: str = "daily"):
    now = datetime.utcnow()

    if period == "daily":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "weekly":
        start = now - timedelta(days=7)
    elif period == "monthly":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == "lifetime":
        start = datetime.min               # everything ever
    else:                                  # fallback to daily
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    return collection.find(
        {
            "user":   user,
            "result": {"$ne": "pending"},
            "date":   {"$gte": start},
        }
    )

# ────────── helpers for leaderboard / admin ──────────
def get_all_users():
    return sorted(collection.distinct("user", {"result": {"$ne": "pending"}}))

def reset_database():
    collection.delete_many({})
