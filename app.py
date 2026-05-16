from flask import Flask, send_from_directory, jsonify, request
from flask_cors import CORS
import os
from pymongo import MongoClient
from ml_model import PharmacyIntelligenceLayer
import datetime

# Root-level configuration
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__, static_folder=BASE_DIR, static_url_path='')
CORS(app)

MONGO_URI = os.environ.get('MONGO_URI')
_cache = {}

def get_db_coll(name):
    if 'db' not in _cache:
        if not MONGO_URI: return None
        try:
            client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            _cache['db'] = client.get_database()
        except: return None
    return _cache['db'][name]

@app.route('/api/dashboard')
def get_dashboard():
    inv = get_db_coll('inventory')
    if inv is None: return jsonify({"success": False, "error": "Database not configured"}), 500
    items = list(inv.find())
    return jsonify({
        "totalItems": len(items),
        "totalStockValue": round(sum(i.get('Quantity_In_Stock', 0) * i.get('Selling_Price_USD', 0) for i in items), 2),
        "todayRevenue": 0,
        "lowStockCount": inv.count_documents({"$expr": {"$lte": ["$Quantity_In_Stock", "$Reorder_Level"]}}),
        "expiredOrNearExpiryCount": sum(1 for i in items if i.get('Days_to_Expiry', 0) <= 30),
        "riskCount": {"High Risk": 0, "Medium Risk": 0, "Low Risk": 0}
    })

@app.route('/api/login', methods=['POST'])
def login():
    users = get_db_coll('users')
    if users is None: return jsonify({"success": False, "error": "Database offline"}), 500
    
    # Ensure default user
    if users.count_documents({}) == 0:
        users.insert_one({"username": "sheripha", "password": "admin123", "role": "admin"})

    data = request.json
    user = users.find_one({"username": data.get('username'), "password": data.get('password')})
    if user: return jsonify({"success": True, "role": user.get('role'), "username": user.get('username')})
    return jsonify({"success": False}), 401

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    if path.startswith('api/'): return jsonify({"success": False}), 404
    
    # Serve static files automatically if they exist
    if path and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    
    # Fallback to index.html
    return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    from waitress import serve
    serve(app, host='0.0.0.0', port=5000)
