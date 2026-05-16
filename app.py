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
    if not MONGO_URI:
        print("Warning: MONGO_URI not found in environment.")
        return False
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db = client.get_database() 
        inventory_coll = db['inventory']
        sales_coll = db['sales']
        audit_coll = db['audit']
        users_coll = db['users']
        settings_coll = db['settings']
        return True
    except Exception as e:
        print(f"Database Error: {e}")
        return False

# Initialize DB & ML Layer
initialize_database()
intelligence = PharmacyIntelligenceLayer(inventory_coll)

# Vercel Boot Logic: Load pre-trained model or train once locally
if not intelligence.load_model():
    print("No pre-trained model found. Training now...")
    df = intelligence.train_demand_forecast_model()
    if df is not None:
        intelligence.seed_database_and_predict(df)

# --- STATIC FILE SERVING ---
@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    if path.startswith('api/'):
        return jsonify({"success": False, "message": "API endpoint not found"}), 404
    full_path = os.path.join(app.static_folder, path)
    if os.path.exists(full_path) and os.path.isfile(full_path):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')

# --- API ENDPOINTS ---

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username, password = data.get('username'), data.get('password')
    user = users_coll.find_one({"username": username, "password": password})
    if user:
        audit_coll.insert_one({"event": "Login", "username": username, "timestamp": datetime.datetime.now().isoformat()})
        return jsonify({"success": True, "role": user.get('role'), "username": username})
    return jsonify({"success": False}), 401

@app.route('/api/dashboard', methods=['GET'])
def get_dashboard():
    items = list(inventory_coll.find())
    total_val = sum((i.get('Quantity_In_Stock', 0) * i.get('Selling_Price_USD', 0)) for i in items)
    low_stock = inventory_coll.count_documents({"$expr": {"$lte": ["$Quantity_In_Stock", "$Reorder_Level"]}})
    
    risk_count = {'High Risk': 0, 'Medium Risk': 0, 'Low Risk': 0}
    for i in items:
        r = i.get('Expiry_Risk_Level', 'Low Risk')
        risk_count[r] = risk_count.get(r, 0) + 1

    today = datetime.datetime.now().strftime("%Y-%m-%d")
    revenue = sum(s.get('total_ghs', 0) for s in sales_coll.find({"date": today}))

    return jsonify({
        "totalItems": len(items),
        "totalStockValue": round(total_val, 2),
        "todayRevenue": round(revenue, 2),
        "lowStockCount": low_stock,
        "expiredOrNearExpiryCount": sum(1 for i in items if i.get('Days_to_Expiry', 0) <= 30),
        "riskCount": risk_count
    })

@app.route('/api/inventory', methods=['GET', 'POST'])
def manage_inventory():
    if request.method == 'POST':
        data = request.json
        settings = settings_coll.find_one({})
        rate = float(settings.get('exchange_rate', 1.0)) if settings else 14.5
        cost_usd = float(data['cost']) / rate
        daily_rate = intelligence.predict_single(data['category'], cost_usd, int(data.get('sales_last_30', 0)))
        
        new_item = {
            "Batch_ID": f"BATCH-{random.randint(1000, 9999)}",
            "Medicine_Name": data['name'],
            "Category": data['category'],
            "Quantity_In_Stock": int(data['qty']),
            "Selling_Price_USD": float(data['price']) / rate,
            "ML_Predicted_Consumption": round(daily_rate, 2),
            "Expiry_Risk_Level": "Low Risk" # simplified for demo
        }
        inventory_coll.insert_one(new_item)
        return jsonify({"success": True})
    
    search = request.args.get('search', '').lower()
    query = {"Medicine_Name": {"$regex": search, "$options": "i"}} if search else {}
    return jsonify(list(inventory_coll.find(query, {"_id": 0})))

@app.route('/api/forecast', methods=['GET'])
def get_forecast():
    items = list(inventory_coll.find({}, {"_id": 0}))
    return jsonify(items)

@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    if request.method == 'POST':
        settings_coll.replace_one({}, request.json, upsert=True)
        return jsonify({"success": True})
    return jsonify(settings_coll.find_one({}, {"_id": 0}) or {})

@app.route('/api/checkout', methods=['POST'])
def checkout():
    data = request.json
    for item in data.get('cart', []):
        inventory_coll.update_one({"Batch_ID": item['Batch_ID']}, {"$inc": {"Quantity_In_Stock": -item['qty']}})
    
    sales_coll.insert_one({
        "date": datetime.datetime.now().strftime("%Y-%m-%d"),
        "total_ghs": data.get('total', 0),
        "pharmacist": data.get('staff_name', 'Unknown'),
        "timestamp": datetime.datetime.now().isoformat()
    })
    return jsonify({"success": True})

# Export app for Vercel
app = app

if __name__ == '__main__':
    from waitress import serve
    print("MedAI GH running locally on http://localhost:5000")
    serve(app, host='0.0.0.0', port=5000, threads=8)
