import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
MONGO_URI = os.getenv('MONGO_URI')

try:
    print(f"Testing connection with URI: {MONGO_URI}")
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client.get_database()
    print("Successfully connected to database:", db.name)
    collections = db.list_collection_names()
    print("Collections:", collections)
except Exception as e:
    print("Database Connection Error:", e)
