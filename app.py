from flask import Flask, send_from_directory, jsonify, request
from flask_cors import CORS
import os
from pymongo import MongoClient
from bson import ObjectId
from werkzeug.utils import secure_filename
from ml_model import PharmacyIntelligenceLayer
import datetime
import threading
import random
import math

# --- CONFIGURATION ---
UPLOAD_FOLDER = 'public/uploads/profiles'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
# Replace with your actual MongoDB Atlas connection string
MONGO_URI = os.environ.get('MONGO_URI', "mongodb://localhost:27017/medai_gh")

app = Flask(__name__, static_folder='public')
CORS(app)

# Global database handles
client = None
db = None
inventory_coll = None
sales_coll = None
audit_coll = None
users_coll = None
settings_coll = None

def initialize_database():
    global client, db, inventory_coll, sales_coll, audit_coll, users_coll, settings_coll
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        # Trigger a command to verify connection
        client.admin.command('ping')
        db = client.get_database() # Gets database from URI or defaults
        
        inventory_coll = db['inventory']
        sales_coll = db['sales']
        audit_coll = db['audit']
        users_coll = db['users']
        settings_coll = db['settings']
        
        print("Connected to MongoDB successfully.")
    except Exception as e:
        print(f"CRITICAL: MongoDB connection failed: {e}")
        # Fallback or exit
        return False
    return True

if not initialize_database():
    print("System halting due to database unavailability.")

# Initialize ML Layer
intelligence = PharmacyIntelligenceLayer(inventory_coll)
df = intelligence.train_demand_forecast_model()
intelligence.seed_database_and_predict(df)

# Seed Settings & Users if empty
if settings_coll.count_documents({}) == 0:
    settings_coll.insert_one({
        "hospital_name": "Ghana National Hospital",
        "nhis_id": "GHA-NHIS-9921",
        "expiry_threshold": 30,
        "currency": "GH₵",
        "exchange_rate": 1.0
    })

if users_coll.count_documents({}) == 0:
    users_coll.insert_many([
        {"username": "admin", "password": "admin123", "role": "admin"},
        {"username": "pharm", "password": "pharm123", "role": "pharmacist"}
    ])

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
    username = data.get('username')
    password = data.get('password')
    
    user = users_coll.find_one({"username": username, "password": password})
    if user:
        role = user.get('role')
        audit_coll.insert_one({
            "event": "Login",
            "username": username,
            "role": role,
            "timestamp": datetime.datetime.now().isoformat()
        })
        return jsonify({
            "success": True, 
            "token": "dummy-token", 
            "role": role, 
            "username": username,
            "profile_pic": user.get('profile_pic', None)
        })
    return jsonify({"success": False, "message": "Invalid Credentials"}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    data = request.json or {}
    username = data.get('username', 'Unknown')
    audit_coll.insert_one({
        "event": "Logout",
        "username": username,
        "timestamp": datetime.datetime.now().isoformat(),
        "details": "User session closed."
    })
    return jsonify({"success": True})

@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    if request.method == 'POST':
        data = request.json
        settings_coll.delete_many({})
        settings_coll.insert_one(data)
        return jsonify({"success": True})
    
    settings = settings_coll.find_one({}, {"_id": 0})
    return jsonify(settings if settings else {})

@app.route('/api/dashboard', methods=['GET'])
def get_dashboard():
    all_items = list(inventory_coll.find())
    total_items = len(all_items)
    
    total_stock_value = sum((i.get('Quantity_In_Stock', 0) * i.get('Selling_Price_USD', 0)) for i in all_items)
    low_stock_count = inventory_coll.count_documents({"$expr": {"$lte": ["$Quantity_In_Stock", "$Reorder_Level"]}})
    
    risk_count = {'High Risk': 0, 'Medium Risk': 0, 'Low Risk': 0}
    expired_count = 0
    
    for item in all_items:
        risk = item.get('Expiry_Risk_Level', 'Low Risk')
        risk_count[risk] = risk_count.get(risk, 0) + 1
        if item.get('Days_to_Expiry', 0) <= 30:
            expired_count += 1
            
    # Today's Revenue
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    todays_sales = list(sales_coll.find({"date": today}))
    today_revenue = sum(s.get('total_ghs', 0) for s in todays_sales)

    return jsonify({
        "totalItems": total_items,
        "totalStockValue": round(total_stock_value, 2),
        "todayRevenue": round(today_revenue, 2),
        "lowStockCount": low_stock_count,
        "expiredOrNearExpiryCount": expired_count,
        "riskCount": risk_count
    })

@app.route('/api/inventory', methods=['GET'])
def get_inventory():
    search = request.args.get('search', '').lower()
    query = {}
    if search:
        query = {"$or": [
            {"Medicine_Name": {"$regex": search, "$options": "i"}},
            {"Category": {"$regex": search, "$options": "i"}},
            {"Batch_ID": {"$regex": search, "$options": "i"}}
        ]}
    
    items = list(inventory_coll.find(query, {"_id": 0}).sort("Medicine_Name", 1))
    return jsonify(items)

@app.route('/api/inventory', methods=['POST'])
def add_inventory_item():
    data = request.json
    settings = settings_coll.find_one({})
    exchange_rate = float(settings.get('exchange_rate', 1.0)) if settings else 14.5

    days_to_expiry = int(data['days_to_expiry'])
    expiry_date = (datetime.datetime.now() + datetime.timedelta(days=days_to_expiry)).strftime('%Y-%m-%d')
    
    cost_usd = round(float(data['cost']) / exchange_rate, 4)
    price_usd = round(float(data['price']) / exchange_rate, 4)
    sales_30 = int(data.get('sales_last_30', 0))

    # AI Prediction
    daily_rate = intelligence.predict_single(data['category'], cost_usd, sales_30)
    pred_exhaust = math.floor(int(data['qty']) / daily_rate) if daily_rate > 0 else 'Unlimited'
    if isinstance(pred_exhaust, int) and pred_exhaust > 36500: pred_exhaust = 'Unlimited'
    
    risk_level = intelligence.automated_expiry_risk_classifier(pred_exhaust, days_to_expiry)

    new_item = {
        "Batch_ID": f"BATCH-{random.randint(1000, 9999)}",
        "Medicine_Name": data['name'],
        "Category": data['category'],
        "Manufacturer": data['manufacturer'],
        "Manufacturing_Date": data['manufacturing_date'],
        "Quantity_In_Stock": int(data['qty']),
        "Reorder_Level": int(data['reorder']),
        "Cost_Price_USD": cost_usd,
        "Selling_Price_USD": price_usd,
        "Days_to_Expiry": days_to_expiry,
        "Expiry_Date": expiry_date,
        "Expiry_Risk_Level": risk_level,
        "Sales_Last_30_Days": sales_30,
        "ML_Predicted_Consumption": round(daily_rate, 2),
        "ML_Predicted_Days_To_Exhaust": pred_exhaust,
        "AI_Recommendation": "Reprioritize stock." if risk_level == 'High Risk' else "Monitor levels."
    }
    
    inventory_coll.insert_one(new_item)
    return jsonify({"success": True, "batch_id": new_item['Batch_ID']})

@app.route('/api/inventory/<batch_id>', methods=['PUT'])
def update_inventory_item(batch_id):
    data = request.json
    settings = settings_coll.find_one({})
    exchange_rate = float(settings.get('exchange_rate', 1.0)) if settings else 14.5

    cost_usd = round(float(data['cost']) / exchange_rate, 4)
    price_usd = round(float(data['price']) / exchange_rate, 4)
    
    daily_rate = intelligence.predict_single(data['category'], cost_usd, int(data.get('sales_last_30', 0)))
    pred_exhaust = math.floor(int(data['qty']) / daily_rate) if daily_rate > 0 else 'Unlimited'
    
    inventory_coll.update_one({"Batch_ID": batch_id}, {"$set": {
        "Medicine_Name": data['name'],
        "Quantity_In_Stock": int(data['qty']),
        "Cost_Price_USD": cost_usd,
        "Selling_Price_USD": price_usd,
        "ML_Predicted_Consumption": round(daily_rate, 2),
        "ML_Predicted_Days_To_Exhaust": pred_exhaust
    }})
    return jsonify({"success": True})

@app.route('/api/inventory/<batch_id>', methods=['DELETE'])
def delete_inventory_item(batch_id):
    inventory_coll.delete_one({"Batch_ID": batch_id})
    return jsonify({"success": True})

@app.route('/api/forecast', methods=['GET'])
def get_forecast():
    search = request.args.get('search', '').lower()
    query = {}
    if search:
        query = {"Medicine_Name": {"$regex": search, "$options": "i"}}
    
    items = list(inventory_coll.find(query, {"_id": 0}))
    for item in items:
        # Calculate Predicted_Stockout_Date for UI
        days = item.get('ML_Predicted_Days_To_Exhaust')
        if isinstance(days, (int, float)):
            item['Predicted_Stockout_Date'] = (datetime.datetime.now() + datetime.timedelta(days=days)).isoformat() + "Z"
        else:
            item['Predicted_Stockout_Date'] = None
            
    return jsonify(items)

@app.route('/api/checkout', methods=['POST'])
def checkout():
    data = request.json
    cart = data.get('cart', [])
    staff_name = data.get('staff_name', 'Unknown')
    total = 0
    
    for item in cart:
        res = inventory_coll.update_one(
            {"Batch_ID": item['Batch_ID'], "Quantity_In_Stock": {"$gte": item['qty']}},
            {"$inc": {"Quantity_In_Stock": -item['qty']}}
        )
        if res.modified_count == 0:
            return jsonify({"success": False, "error": f"Insufficient stock for {item['name']}"}), 400
        
        # Calculate total (requires fetching price or trust frontend)
        # For security, ideally fetch from DB. Here we trust for demo.
        total += item['price'] * item['qty']
                
    sales_coll.insert_one({
        "date": datetime.datetime.now().strftime("%Y-%m-%d"),
        "timestamp": datetime.datetime.now().isoformat(),
        "total_ghs": round(total, 2),
        "items": len(cart),
        "pharmacist": staff_name,
        "details": ", ".join([f"{i['name']} (x{i['qty']})" for i in cart])
    })
    return jsonify({"success": True, "total": round(total, 2)})

@app.route('/api/recommendations', methods=['GET'])
def get_recommendations():
    high_risk = list(inventory_coll.find({"Expiry_Risk_Level": "High Risk"}, {"_id": 0}).limit(10))
    return jsonify(high_risk)

@app.route('/api/charts/risk', methods=['GET'])
def get_charts():
    pipeline = [
        {"$group": {"_id": "$Category", "stock": {"$sum": "$Quantity_In_Stock"}}},
        {"$project": {"name": "$_id", "stock": 1, "_id": 0}},
        {"$sort": {"stock": -1}},
        {"$limit": 5}
    ]
    return jsonify(list(inventory_coll.aggregate(pipeline)))

@app.route('/api/admin/audit', methods=['GET'])
def get_audit():
    logs = list(audit_coll.find({}, {"_id": 0}).sort("timestamp", -1).limit(100))
    return jsonify(logs)

@app.route('/api/users', methods=['GET'])
def get_users():
    return jsonify(list(users_coll.find({}, {"_id": 0})))

@app.route('/api/admin/users', methods=['POST'])
def manage_users():
    data = request.form if request.form else request.json
    action = data.get('action')
    username = data.get('username')
    
    if action == 'add':
        users_coll.insert_one({"username": username, "password": data.get('password'), "role": data.get('role', 'pharmacist')})
    elif action == 'edit':
        users_coll.update_one({"username": username}, {"$set": {"role": data.get('role'), "password": data.get('password')}})
    elif action == 'delete':
        users_coll.delete_one({"username": username})
        
    return jsonify({"success": True})

@app.route('/api/sales/today', methods=['GET'])
def sales_today():
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    pharmacist = request.args.get('pharmacist')
    query = {"date": today}
    if pharmacist: query["pharmacist"] = pharmacist
    
    sales = list(sales_coll.find(query))
    total = sum(s['total_ghs'] for s in sales)
    return jsonify({"total_revenue_ghs": round(total, 2), "transaction_count": len(sales)})

@app.route('/api/my/sales', methods=['GET'])
def my_sales():
    pharmacist = request.args.get('pharmacist')
    sales = list(sales_coll.find({"pharmacist": pharmacist}, {"_id": 0}).sort("timestamp", -1).limit(50))
    return jsonify(sales)

if __name__ == '__main__':
    from waitress import serve
    print("MedAI GH running with MongoDB on http://localhost:5000")
    serve(app, host='0.0.0.0', port=5000, threads=8)
