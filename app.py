from flask import Flask, send_from_directory, jsonify, request
from flask_cors import CORS
import os
from pymongo import MongoClient
from ml_model import PharmacyIntelligenceLayer
import datetime

app = Flask(__name__, static_folder=os.path.abspath(os.path.dirname(__file__)))
CORS(app)

# Use direct os.environ for Vercel
MONGO_URI = os.environ.get('MONGO_URI')
inventory_coll = None
sales_coll = None
users_coll = None
settings_coll = None

def initialize_database():
    global inventory_coll, sales_coll, users_coll, settings_coll
    if not MONGO_URI: return False
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db = client.get_database() 
        inventory_coll, sales_coll, users_coll, settings_coll = \
            db['inventory'], db['sales'], db['users'], db['settings']
    except: return False
    
    # Seed new Admin if empty
    if users_coll and users_coll.count_documents({}) == 0:
        users_coll.insert_one({"username": "sheripha", "password": "admin123", "role": "admin"})
    return True

initialize_database()
intelligence = PharmacyIntelligenceLayer(inventory_coll)
intelligence.load_model()

@app.route('/api/dashboard')
def get_dashboard():
    if not MONGO_URI:
        return jsonify({"success": False, "error": "MONGO_URI is missing in Vercel settings"}), 500
    if inventory_coll is None:
        return jsonify({"success": False, "error": "Database connection failed"}), 500
    
    items = list(inventory_coll.find())
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    revenue = sum(s.get('total_ghs', 0) for s in sales_coll.find({"date": today}))
    return jsonify({
        "totalItems": len(items), "totalStockValue": round(sum(i.get('Quantity_In_Stock', 0) * i.get('Selling_Price_USD', 0) for i in items), 2),
        "todayRevenue": round(revenue, 2), "lowStockCount": inventory_coll.count_documents({"$expr": {"$lte": ["$Quantity_In_Stock", "$Reorder_Level"]}}),
        "expiredOrNearExpiryCount": sum(1 for i in items if i.get('Days_to_Expiry', 0) <= 30),
        "riskCount": {"High Risk": sum(1 for i in items if i.get('Expiry_Risk_Level') == 'High Risk'), "Medium Risk": 0, "Low Risk": 0}
    })

@app.route('/api/login', methods=['POST'])
def login():
    if users_coll is None: return jsonify({"success": False, "error": "Database not connected"}), 500
    if users_coll.count_documents({}) == 0:
        users_coll.insert_many([
            {"username": "sheripha", "password": "admin123", "role": "admin"},
            {"username": "pharm", "password": "pharm123", "role": "pharmacist"}
        ])
    data = request.json
    user = users_coll.find_one({"username": data.get('username'), "password": data.get('password')})
    if user: return jsonify({"success": True, "role": user.get('role'), "username": user.get('username')})
    return jsonify({"success": False}), 401

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    if path.startswith('api/'): return jsonify({"success": False}), 404
    full_path = os.path.join(app.static_folder, path)
    if path and os.path.exists(full_path) and os.path.isfile(full_path):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    from waitress import serve
    serve(app, host='0.0.0.0', port=5000)
