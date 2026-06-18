import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()
MONGO_URI = os.getenv('MONGO_URI') or "mongodb+srv://sheripha2_db_user:Admin123@cluster0.xpjpg6o.mongodb.net/medai_gh?retryWrites=true&w=majority&appName=Cluster0"

client = MongoClient(MONGO_URI)
db = client.get_database("medai_gh")
inventory_col = db["inventory"]

count = inventory_col.count_documents({})
print(f"Total drugs in the inventory database: {count}")

print("\nBreakdown of drug counts by Category:")
pipeline = [
    {"$group": {"_id": "$Category", "count": {"$sum": 1}}},
    {"$sort": {"count": -1}}
]
for result in inventory_col.aggregate(pipeline):
    print(f" - {result['_id']}: {result['count']} drugs")
