from flask import Flask, send_from_directory, jsonify, request
from flask_cors import CORS
import os
from pymongo import MongoClient
from ml_model import PharmacyIntelligenceLayer
import datetime

app = Flask(__name__)
CORS(app)

# Use current directory for static files
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Global database handles
MONGO_URI = os.environ.get('MONGO_URI')
_db_cache = {}

def get_db():
    if 'db' not in _db_cache:
        if not MONGO_URI: return None
        try:
            client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            _db_cache['db'] = client.get_database()
        except: return None
    return _db_cache['db']

def get_coll(name):
    db = get_db()
    return db[name] if db is not None else None

# Initialize AI Layer (Lazy)
_ai_cache = {}
def get_ai():
    if 'ai' not in _ai_cache:
        inv = get_coll('inventory')
        ai = PharmacyIntelligenceLayer(inv)
        ai.load_model()
        _ai_cache['ai'] = ai
    return _ai_cache['ai']

@app.route('/api/dashboard')
def get_dashboard():
    inv = get_coll('inventory')
    sales = get_coll('sales')
    if inv is None: return jsonify({"success": False, "error": "DB Disconnected"}), 500
    
    items = list(inv.find())
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    revenue = sum(s.get('total_ghs', 0) for s in sales.find({"date": today})) if sales else 0
    
    return jsonify({
        "totalItems": len(items),
        "totalStockValue": round(sum(i.get('Quantity_In_Stock', 0) * i.get('Selling_Price_USD', 0) for i in items), 2),
        "todayRevenue": round(revenue, 2),
        "lowStockCount": inv.count_documents({"$expr": {"$lte": ["$Quantity_In_Stock", "$Reorder_Level"]}}),
        "expiredOrNearExpiryCount": sum(1 for i in items if i.get('Days_to_Expiry', 0) <= 30),
        "riskCount": {"High Risk": sum(1 for i in items if i.get('Expiry_Risk_Level') == 'High Risk'), "Medium Risk": 0, "Low Risk": 0}
    })

@app.route('/api/login', methods=['POST'])
def login():
    users = get_coll('users')
    if users is None: return jsonify({"success": False, "error": "DB Offline"}), 500
    
    # Ensure default user exists
    if users.count_documents({}) == 0:
        users.insert_one({"username": "sheripha", "password": "admin123", "role": "admin"})

    data = request.json
    user = users.find_one({"username": data.get('username'), "password": data.get('password')})
    if user: return jsonify({"success": True, "role": user.get('role'), "username": user.get('username')})
    return jsonify({"success": False}), 401

@app.route('/api/inventory', methods=['GET'])
def get_inventory():
    inv = get_coll('inventory')
    if inv is None: return jsonify([]), 500
    return jsonify(list(inv.find({}, {"_id": 0})))

@app.route('/api/settings', methods=['GET'])
def get_settings():
    st = get_coll('settings')
    if st is None: return jsonify({}), 500
    return jsonify(st.find_one({}, {"_id": 0}) or {})

# CATCH-ALL ROUTE
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    if path.startswith('api/'): return jsonify({"success": False}), 404
    
    # Try file in root
    full_path = os.path.join(BASE_DIR, path)
    if path and os.path.exists(full_path) and os.path.isfile(full_path):
        return send_from_directory(BASE_DIR, path)
    
    return send_from_directory(BASE_DIR, 'index.html')

if __name__ == '__main__':
    from waitress import serve
    serve(app, host='0.0.0.0', port=5000)
