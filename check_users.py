import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()
MONGO_URI = os.getenv('MONGO_URI') or "mongodb+srv://sheripha2_db_user:Admin123@cluster0.xpjpg6o.mongodb.net/medai_gh?retryWrites=true&w=majority&appName=Cluster0"

client = MongoClient(MONGO_URI)
db = client.get_database("medai_gh")
users_col = db["users"]

print("Users in database:")
for user in users_col.find():
    print(f"ID: {user.get('_id')}, Username: {user.get('username')}, Role: {user.get('role')}, Status: {user.get('status')}")
