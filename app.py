from flask import Flask, send_from_directory, jsonify, request
from flask_cors import CORS
import os
from dotenv import load_dotenv
from pymongo import MongoClient
from bson import ObjectId
from ml_model import PharmacyIntelligenceLayer
import datetime
import random
import math

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder='public')
CORS(app)

# Global database handles
MONGO_URI = os.getenv('MONGO_URI')
client = None
db = None
inventory_coll = None
sales_coll = None
audit_coll = None
users_coll = None
settings_coll = None

def initialize_database():
    global client, db, inventory_coll, sales_coll, audit_coll, users_coll, settings_coll
    if not MONGO_URI: return False
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db = client.get_database() 
        inventory_coll, sales_coll, audit_coll, users_coll, settings_coll = \
            db['inventory'], db['sales'], db['audit'], db['users'], db['settings']
        return True
    except: return False

# Initialize
initialize_database()
intelligence = PharmacyIntelligenceLayer(inventory_coll)
intelligence.load_model()

# --- UNIVERSAL ROUTING (FOR VERCEL) ---

@app.route('/api/dashboard', methods=['GET'])
def get_dashboard():
    if inventory_coll is None: return jsonify({"success": False}), 500
    items = list(inventory_coll.find())
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    revenue = sum(s.get('total_ghs', 0) for s in sales_coll.find({"date": today}))
    return jsonify({
        "totalItems": len(items),
        "totalStockValue": round(sum(i.get('Quantity_In_Stock', 0) * i.get('Selling_Price_USD', 0) for i in items), 2),
        "todayRevenue": round(revenue, 2),
        "lowStockCount": inventory_coll.count_documents({"$expr": {"$lte": ["$Quantity_In_Stock", "$Reorder_Level"]}}),
        "expiredOrNearExpiryCount": sum(1 for i in items if i.get('Days_to_Expiry', 0) <= 30),
        "riskCount": {"High Risk": sum(1 for i in items if i.get('Expiry_Risk_Level') == 'High Risk'), "Medium Risk": 0, "Low Risk": 0}
    })

@app.route('/api/inventory', methods=['GET', 'POST'])
def manage_inventory():
    if request.method == 'POST':
        # Simple add for demo
        inventory_coll.insert_one(request.json)
        return jsonify({"success": True})
    return jsonify(list(inventory_coll.find({}, {"_id": 0})))

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    user = users_coll.find_one({"username": data.get('username'), "password": data.get('password')})
    if user: return jsonify({"success": True, "role": user.get('role'), "username": user.get('username')})
    return jsonify({"success": False}), 401

@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    if request.method == 'POST':
        settings_coll.replace_one({}, request.json, upsert=True)
        return jsonify({"success": True})
    return jsonify(settings_coll.find_one({}, {"_id": 0}) or {})

# CATCH-ALL STATIC SERVING
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    if path.startswith('api/'):
        return jsonify({"success": False, "message": "API not found"}), 404
    
    # Check if file exists in public
    full_path = os.path.join(app.static_folder, path)
    if path and os.path.exists(full_path) and os.path.isfile(full_path):
        return send_from_directory(app.static_folder, path)
    
    # Default to index.html
    return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    from waitress import serve
    serve(app, host='0.0.0.0', port=5000)
