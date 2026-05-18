from flask import Flask, jsonify, request
from flask_cors import CORS
import os
from dotenv import load_dotenv
from pymongo import MongoClient
import datetime

load_dotenv()

app = Flask(__name__)
CORS(app)

MONGO_URI = os.environ.get('MONGO_URI')
_db_cache = {}

def get_db():
    if 'client' not in _db_cache:
        if not MONGO_URI:
            return None
        try:
            client = MongoClient(
                MONGO_URI,
                serverSelectionTimeoutMS=8000,
                connectTimeoutMS=8000,
                socketTimeoutMS=8000
            )
            _db_cache['client'] = client
            _db_cache['db'] = client.get_database()
        except Exception as e:
            print(f"DB Connection Error: {e}")
            return None
    return _db_cache.get('db')

def get_coll(name):
    db = get_db()
    if db is None:
        return None
    return db[name]

# ─── HEALTH CHECK ───────────────────────────────────────────────
@app.route('/api/health')
def health():
    db = get_db()
    return jsonify({"status": "ok", "db": "connected" if db else "offline"})

# ─── DASHBOARD ──────────────────────────────────────────────────
@app.route('/api/dashboard')
def get_dashboard():
    inv = get_coll('inventory')
    if inv is None:
        return jsonify({"success": False, "error": "DB Offline"}), 500
    try:
        items = list(inv.find({}, {"_id": 0}))
        total_value = round(sum(
            i.get('Quantity_In_Stock', 0) * i.get('Selling_Price_USD', 0)
            for i in items
        ), 2)
        low_stock = sum(
            1 for i in items
            if i.get('Quantity_In_Stock', 0) <= i.get('Reorder_Level', 10)
        )
        expiry_risk = sum(
            1 for i in items
            if i.get('Days_to_Expiry', 999) <= 30
        )
        return jsonify({
            "totalItems": len(items),
            "totalStockValue": total_value,
            "todayRevenue": 0,
            "lowStockCount": low_stock,
            "expiredOrNearExpiryCount": expiry_risk,
            "riskCount": {"High Risk": expiry_risk, "Medium Risk": 0, "Low Risk": len(items) - expiry_risk}
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ─── LOGIN ───────────────────────────────────────────────────────
@app.route('/api/login', methods=['POST'])
def login():
    users = get_coll('users')
    if users is None:
        return jsonify({"success": False, "error": "DB Offline"}), 500
    try:
        # Seed default admin if no users exist
        if users.count_documents({}) == 0:
            users.insert_one({
                "username": "sheripha",
                "password": "admin123",
                "role": "admin"
            })
        data = request.get_json() or {}
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        user = users.find_one({"username": username, "password": password})
        if user:
            return jsonify({
                "success": True,
                "role": user.get('role', 'pharmacist'),
                "username": user.get('username')
            })
        return jsonify({"success": False, "message": "Invalid credentials"}), 401
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ─── REGISTER ────────────────────────────────────────────────────
@app.route('/api/register', methods=['POST'])
def register():
    users = get_coll('users')
    if users is None:
        return jsonify({"success": False, "error": "DB Offline"}), 500
    try:
        data = request.get_json() or {}
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        role = data.get('role', 'pharmacist')

        if not username or not password:
            return jsonify({"success": False, "message": "Username and password are required"}), 400

        if users.find_one({"username": username}):
            return jsonify({"success": False, "message": "Username already exists"}), 400

        users.insert_one({"username": username, "password": password, "role": role})
        return jsonify({"success": True, "username": username, "role": role})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ─── INVENTORY ───────────────────────────────────────────────────
@app.route('/api/inventory', methods=['GET'])
def get_inv():
    inv = get_coll('inventory')
    if inv is None:
        return jsonify([]), 200
    try:
        search = request.args.get('search', '').strip()
        if search:
            import re
            regex = re.compile(search, re.IGNORECASE)
            query = {"$or": [
                {"Medicine_Name": regex},
                {"Batch_ID": regex},
                {"Category": regex}
            ]}
        else:
            query = {}
        items = list(inv.find(query, {"_id": 0}).limit(100))
        return jsonify(items)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ─── USERS ───────────────────────────────────────────────────────
@app.route('/api/users', methods=['GET'])
def get_users():
    users = get_coll('users')
    if users is None:
        return jsonify([]), 500
    try:
        return jsonify(list(users.find({}, {"_id": 0, "password": 0})))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/users', methods=['POST'])
def manage_users():
    users = get_coll('users')
    if users is None:
        return jsonify({"success": False, "error": "DB Offline"}), 500
    try:
        data = request.get_json() or {}
        action = data.get('action')
        username = data.get('username', '').strip()

        if action == 'add':
            if users.find_one({"username": username}):
                return jsonify({"success": False, "message": "User already exists"}), 400
            users.insert_one({"username": username, "password": data.get('password'), "role": data.get('role', 'pharmacist')})
            return jsonify({"success": True})
        elif action == 'edit':
            update = {"role": data.get('role')}
            if data.get('password'):
                update['password'] = data.get('password')
            users.update_one({"username": username}, {"$set": update})
            return jsonify({"success": True})
        elif action == 'delete':
            users.delete_one({"username": username})
            return jsonify({"success": True})
        return jsonify({"success": False, "message": "Invalid action"}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ─── SALES ───────────────────────────────────────────────────────
@app.route('/api/admin/sales', methods=['GET'])
def get_sales():
    sales = get_coll('sales')
    if sales is None:
        return jsonify([]), 500
    try:
        return jsonify(list(sales.find({}, {"_id": 0}).sort("timestamp", -1)))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/sales/today', methods=['GET'])
def sales_today():
    sales = get_coll('sales')
    if sales is None:
        return jsonify({"total_revenue_ghs": 0, "transaction_count": 0}), 200
    try:
        today = datetime.datetime.utcnow().strftime('%Y-%m-%d')
        query = {"timestamp": {"$regex": f"^{today}"}}
        pharmacist = request.args.get('pharmacist')
        if pharmacist:
            query['pharmacist'] = pharmacist
        all_sales = list(sales.find(query, {"_id": 0}))
        total = sum(s.get('total_ghs', 0) for s in all_sales)
        return jsonify({"total_revenue_ghs": round(total, 2), "transaction_count": len(all_sales)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/checkout', methods=['POST'])
def checkout():
    inv = get_coll('inventory')
    sales = get_coll('sales')
    if inv is None or sales is None:
        return jsonify({"success": False, "error": "DB Offline"}), 500
    try:
        data = request.get_json() or {}
        cart = data.get('cart', [])
        staff_name = data.get('staff_name', 'Unknown')
        customer_name = data.get('customer_name', 'Walk-in Customer')
        total = 0
        details = []
        for item in cart:
            db_item = inv.find_one({"Batch_ID": item.get('Batch_ID')}, {"_id": 0})
            if not db_item or db_item.get('Quantity_In_Stock', 0) < item.get('qty', 1):
                return jsonify({"success": False, "error": f"Insufficient stock for {item.get('name')}"}), 400
            inv.update_one({"Batch_ID": item['Batch_ID']}, {"$inc": {"Quantity_In_Stock": -item['qty']}})
            total += item['qty'] * item.get('price', item.get('Selling_Price_USD', 0))
            details.append(f"{item['qty']}x {item.get('name', item.get('Medicine_Name', '?'))}")

        sales.insert_one({
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "pharmacist": staff_name,
            "customer_name": customer_name,
            "items": len(cart),
            "total_ghs": round(total, 2),
            "details": ", ".join(details)
        })
        return jsonify({"success": True, "total": round(total, 2)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# Required by Vercel
if __name__ == '__main__':
    from waitress import serve
    print("MedAI GH - Production Server Active")
    print("Local URL: http://localhost:5000")
    serve(app, host='0.0.0.0', port=5000, threads=8)
