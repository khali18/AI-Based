from flask import Flask, jsonify, request
from flask_cors import CORS
import os
from dotenv import load_dotenv
import os
import sys
# Add parent directory to sys.path so ml_model can be found on Vercel
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pymongo import MongoClient
from ml_model import PharmacyIntelligenceLayer
import datetime

# Load local environment variables if they exist
load_dotenv()

app = Flask(__name__)
CORS(app)

MONGO_URI = os.environ.get('MONGO_URI')
_cache = {}

def get_coll(name):
    if 'db' not in _cache:
        if not MONGO_URI: return None
        try:
            client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            _cache['db'] = client.get_database()
        except: return None
    return _cache['db'][name]

# AI Layer Helper
def get_ai():
    if 'ai' not in _cache:
        inv = get_coll('inventory')
        ai = PharmacyIntelligenceLayer(inv)
        ai.load_model()
        _cache['ai'] = ai
    return _cache['ai']

@app.route('/api/dashboard')
def get_dashboard():
    inv = get_coll('inventory')
    if inv is None: return jsonify({"success": False, "error": "DB Offline"}), 500
    items = list(inv.find())
    return jsonify({
        "totalItems": len(items),
        "totalStockValue": round(sum(i.get('Quantity_In_Stock', 0) * i.get('Selling_Price_USD', 0) for i in items), 2),
        "todayRevenue": 0, # Placeholder
        "lowStockCount": inv.count_documents({"$expr": {"$lte": ["$Quantity_In_Stock", "$Reorder_Level"]}}),
        "expiredOrNearExpiryCount": sum(1 for i in items if i.get('Days_to_Expiry', 0) <= 30),
        "riskCount": {"High Risk": 0, "Medium Risk": 0, "Low Risk": 0}
    })

@app.route('/api/login', methods=['POST'])
def login():
    users = get_coll('users')
    if users is None: return jsonify({"success": False, "error": "DB Offline"}), 500
    
    # Seeding fallback
    if users.count_documents({}) == 0:
        users.insert_one({"username": "sheripha", "password": "admin123", "role": "admin"})

    data = request.json
    user = users.find_one({"username": data.get('username'), "password": data.get('password')})
    if user: return jsonify({"success": True, "role": user.get('role'), "username": user.get('username')})
    return jsonify({"success": False}), 401

@app.route('/api/register', methods=['POST'])
def register():
    users = get_coll('users')
    if users is None: return jsonify({"success": False, "error": "DB Offline"}), 500
    
    data = request.json
    username = data.get('username')
    password = data.get('password')
    role = data.get('role', 'pharmacist')

    if users.find_one({"username": username}):
        return jsonify({"success": False, "message": "Username already exists"}), 400
    
    users.insert_one({"username": username, "password": password, "role": role})
    return jsonify({"success": True, "username": username, "role": role})

@app.route('/api/inventory', methods=['GET'])
def get_inv():
    inv = get_coll('inventory')
    if inv is None: return jsonify([]), 500
    return jsonify(list(inv.find({}, {"_id": 0})))

# Vercel needs the app object
app = app

if __name__ == '__main__':
    from waitress import serve
    print("-----------------------------------------------")
    print("MedAI GH - PRODUCTION SERVER ACTIVE")
    print("Local URL: http://localhost:5000")
    print("Cloud DB: Connected (Atlas)")
    print("-----------------------------------------------")
    serve(app, host='0.0.0.0', port=5000, threads=8)
