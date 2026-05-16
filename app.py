from flask import Flask, send_from_directory, jsonify, request
from flask_cors import CORS
import os
from dotenv import load_dotenv
from pymongo import MongoClient
from ml_model import PharmacyIntelligenceLayer
import datetime

# Load environment variables
load_dotenv()

# ABSOLUTE PATHING FOR VERCEL
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
STATIC_FOLDER = os.path.join(BASE_DIR, 'public')

app = Flask(__name__, static_folder=STATIC_FOLDER)
CORS(app)

# Global database handles
MONGO_URI = os.getenv('MONGO_URI')
inventory_coll = None
sales_coll = None
users_coll = None
settings_coll = None

def initialize_database():
    global inventory_coll, sales_coll, users_coll, settings_coll
    if not MONGO_URI:
        print("ERROR: MONGO_URI is missing from Environment Variables!")
        return False
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db = client.get_database() 
        inventory_coll = db['inventory']
        sales_coll = db['sales']
        users_coll = db['users']
        settings_coll = db['settings']
        return True
    except Exception as e:
        print(f"ERROR: Database connection failed: {e}")
        return False

# Initialize
initialize_database()
intelligence = PharmacyIntelligenceLayer(inventory_coll)
intelligence.load_model()

@app.route('/api/dashboard', methods=['GET'])
def get_dashboard():
    if inventory_coll is None:
        return jsonify({"success": False, "error": "Database not connected. Check MONGO_URI in Vercel Settings."}), 500
    
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

@app.route('/api/login', methods=['POST'])
def login():
    if users_coll is None: return jsonify({"success": False, "error": "DB Error"}), 500
    data = request.json
    user = users_coll.find_one({"username": data.get('username'), "password": data.get('password')})
    if user: return jsonify({"success": True, "role": user.get('role'), "username": user.get('username')})
    return jsonify({"success": False}), 401

@app.route('/api/inventory', methods=['GET'])
def get_inv():
    if inventory_coll is None: return jsonify([]), 500
    return jsonify(list(inventory_coll.find({}, {"_id": 0})))

@app.route('/api/settings', methods=['GET'])
def get_settings():
    if settings_coll is None: return jsonify({}), 500
    return jsonify(settings_coll.find_one({}, {"_id": 0}) or {})

# --- CATCH-ALL ROUTE ---
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    if path.startswith('api/'):
        return jsonify({"success": False, "message": "API not found"}), 404
    
    # Try serving as a file
    full_path = os.path.join(app.static_folder, path)
    if path and os.path.exists(full_path) and os.path.isfile(full_path):
        return send_from_directory(app.static_folder, path)
    
    # Fallback to index.html
    return send_from_directory(app.static_folder, 'index.html')

# For Vercel
app = app

if __name__ == '__main__':
    from waitress import serve
    serve(app, host='0.0.0.0', port=5000)
