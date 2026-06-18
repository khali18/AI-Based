from flask import Flask, jsonify, request
from flask_cors import CORS
import os
from dotenv import load_dotenv
from pymongo import MongoClient
import datetime
import certifi
from ml_model import PharmacyIntelligenceLayer

load_dotenv()

app = Flask(__name__, static_folder='../public', static_url_path='')
CORS(app)

# Initialize ML Intelligence Layer
intelligence = PharmacyIntelligenceLayer()
model_loaded = intelligence.load_model()
if not model_loaded:
    print("Warning: ML Model failed to load. Will use simple heuristics fallback.")

@app.route('/')
def serve_index():
    return app.send_static_file('index.html')

MONGO_URI = os.getenv('MONGO_URI') or 'mongodb+srv://sheripha2_db_user:Admin123@cluster0.xpjpg6o.mongodb.net/medai_gh?retryWrites=true&w=majority&appName=Cluster0'
_db_cache = {}

def get_db():
    if 'client' not in _db_cache:
        if not MONGO_URI:
            return None
        try:
            client = MongoClient(
                MONGO_URI,
                tlsCAFile=certifi.where(),
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

# Helper: Log event to audit collection
def log_event(username, event, details, metadata=None):
    try:
        audit = get_coll('audit')
        if audit is not None:
            audit.insert_one({
                "timestamp": datetime.datetime.utcnow().isoformat(),
                "username": username,
                "event": event,
                "details": details,
                "metadata": metadata
            })
    except Exception as e:
        print(f"Audit Logging Error: {e}")

# Helper: automated classification for expiry risk
def get_risk_label(days_to_expiry, threshold=30):
    if days_to_expiry <= threshold:
        return 'High Risk'
    elif days_to_expiry <= threshold * 3:
        return 'Medium Risk'
    return 'Low Risk'

# ─── HEALTH CHECK ───────────────────────────────────────────────
@app.route('/api/health')
def health():
    db = get_db()
    return jsonify({"status": "ok", "db": "connected" if db else "offline"})

# ─── DASHBOARD ──────────────────────────────────────────────────
@app.route('/api/dashboard')
def get_dashboard():
    inv = get_coll('inventory')
    sales = get_coll('sales')
    settings_coll = get_coll('settings')
    if inv is None:
        return jsonify({"success": False, "error": "DB Offline"}), 500
    try:
        # Load settings
        settings = settings_coll.find_one({}, {"_id": 0}) if settings_coll is not None else None
        threshold = settings.get('expiry_threshold', 30) if settings else 30
        exchange_rate = settings.get('exchange_rate', 1.0) if settings else 1.0

        items = list(inv.find({}, {"_id": 0}))
        
        # Calculate stock value in USD
        total_value = round(sum(
            i.get('Quantity_In_Stock', 0) * i.get('Selling_Price_USD', 0)
            for i in items
        ), 2)
        
        # Calculate low stock count
        low_stock = sum(
            1 for i in items
            if i.get('Quantity_In_Stock', 0) <= i.get('Reorder_Level', 10)
        )
        
        # Calculate near-expiry count
        expiry_risk = sum(
            1 for i in items
            if i.get('Days_to_Expiry', 999) <= threshold
        )
        
        # Calculate today's revenue (in GHS) from sales collection
        today_str = datetime.datetime.utcnow().strftime('%Y-%m-%d')
        today_sales = list(sales.find({"timestamp": {"$regex": f"^{today_str}"}})) if sales is not None else []
        today_rev = round(sum(s.get('total_ghs', 0) for s in today_sales), 2)

        # Classify all risks
        risk_count = {"High Risk": 0, "Medium Risk": 0, "Low Risk": 0}
        for i in items:
            days = i.get('Days_to_Expiry', 999)
            risk = get_risk_label(days, threshold)
            risk_count[risk] += 1

        return jsonify({
            "totalItems": len(items),
            "totalStockValue": total_value,
            "todayRevenue": today_rev,
            "lowStockCount": low_stock,
            "expiredOrNearExpiryCount": expiry_risk,
            "riskCount": risk_count
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ─── RECOMMENDATIONS ─────────────────────────────────────────────
@app.route('/api/recommendations')
def get_recommendations():
    inv = get_coll('inventory')
    if inv is None:
        return jsonify([]), 200
    try:
        # Fetch items with High Risk, sorted by days remaining
        high_risk = list(inv.find({"Expiry_Risk_Level": "High Risk"}, {"_id": 0}).sort("Days_to_Expiry", 1).limit(10))
        if not high_risk:
            # Fallback to general low Days_to_Expiry if not pre-labeled
            high_risk = list(inv.find({}, {"_id": 0}).sort("Days_to_Expiry", 1).limit(10))
        return jsonify(high_risk)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ─── CHARTS RISK ─────────────────────────────────────────────────
@app.route('/api/charts/risk')
def get_chart_risk():
    inv = get_coll('inventory')
    if inv is None:
        return jsonify([]), 200
    try:
        items = list(inv.find({}, {"_id": 0}))
        categories = {}
        for item in items:
            cat = item.get('Category', 'General')
            if cat not in categories:
                categories[cat] = {"name": cat, "stock": 0}
            categories[cat]["stock"] += item.get('Quantity_In_Stock', 0)
        
        sorted_cats = sorted(categories.values(), key=lambda x: x['stock'], reverse=True)
        return jsonify(sorted_cats[:5])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ─── DEMAND FORECASTING ───────────────────────────────────────────
@app.route('/api/forecast')
def get_forecast():
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
                {"Batch_ID": regex}
            ]}
        else:
            query = {}
        
        items = list(inv.find(query, {"_id": 0}).sort("Medicine_Name", 1).limit(100))
        
        forecasted = []
        for item in items:
            stock = item.get('Quantity_In_Stock', 0)
            days = item.get('ML_Predicted_Days_To_Exhaust')
            rate = item.get('Daily_Consumption_Rate', item.get('ML_Predicted_Consumption', 0.1))
            if rate is None or rate == 0:
                rate = 0.1
            
            if days is None:
                days = int(stock / rate)
            
            if days == 'Unlimited' or days == 'Infinity' or days is None:
                stockout_date = None
                days_label = 'Unlimited'
            else:
                try:
                    days_int = int(days)
                    stockout_date = (datetime.datetime.utcnow() + datetime.timedelta(days=days_int)).isoformat()
                    days_label = days_int
                except:
                    stockout_date = None
                    days_label = 'Unlimited'
            
            item['Days_to_Exhaust_Stock'] = days_label
            item['Daily_Consumption_Rate'] = rate
            item['Predicted_Stockout_Date'] = stockout_date
            forecasted.append(item)
            
        return jsonify(forecasted)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ─── LOGIN ───────────────────────────────────────────────────────
@app.route('/api/login', methods=['POST'])
def login():
    users = get_coll('users')
    if users is None:
        return jsonify({"success": False, "error": "DB Offline"}), 500
    try:
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
            log_event(username, 'Login', f"User logged into {user.get('role', 'pharmacist')} portal.", {"role": user.get('role')})
            return jsonify({
                "success": True,
                "role": user.get('role', 'pharmacist'),
                "username": user.get('username'),
                "profile_pic": user.get('profile_pic')
            })
        return jsonify({"success": False, "message": "Invalid credentials"}), 401
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ─── LOGOUT ───────────────────────────────────────────────────────
@app.route('/api/logout', methods=['POST'])
def logout():
    try:
        data = request.get_json() or {}
        username = data.get('username', '').strip()
        if username:
            log_event(username, 'Logout', 'User manually closed session.')
            return jsonify({"success": True})
        return jsonify({"success": False}), 400
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
        log_event('admin', 'Staff Created', f"Registered staff {username} as {role}.")
        return jsonify({"success": True, "username": username, "role": role})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ─── INVENTORY ───────────────────────────────────────────────────
@app.route('/api/inventory', methods=['GET', 'POST'])
def get_inv():
    inv = get_coll('inventory')
    if inv is None:
        return jsonify([]), 200
    try:
        if request.method == 'GET':
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
        else: # POST: Add Product
            data = request.get_json() or {}
            
            import random
            batch_id = f"BATCH-{random.randint(1000, 9999)}"
            while inv.find_one({"Batch_ID": batch_id}):
                batch_id = f"BATCH-{random.randint(1000, 9999)}"
            
            days_to_expiry = int(data.get('days_to_expiry', 365))
            qty = int(data.get('qty', 0))
            reorder = int(data.get('reorder', 10))
            sales_30 = int(data.get('sales_last_30', 0))
            cost = float(data.get('cost', 0.0))
            category = data.get('category', 'General')
            rate = intelligence.predict_single(category, cost, sales_30) if model_loaded else (sales_30 / 30.0 if sales_30 > 0 else 0.1)
            days_to_exhaust = int(qty / rate) if rate > 0 else 999

            new_item = {
                "Batch_ID": batch_id,
                "Medicine_Name": data.get('name'),
                "Category": data.get('category', 'General'),
                "Manufacturer": data.get('manufacturer'),
                "Manufacturing_Date": data.get('manufacturing_date'),
                "Quantity_In_Stock": qty,
                "Reorder_Level": reorder,
                "Unit_Cost_USD": float(data.get('cost', 0.0)),
                "Selling_Price_USD": float(data.get('price', 0.0)),
                "Days_to_Expiry": days_to_expiry,
                "Expiry_Date": data.get('expiry_date'),
                "Sales_Last_30_Days": sales_30,
                "Daily_Consumption_Rate": rate,
                "ML_Predicted_Consumption": rate,
                "ML_Predicted_Days_To_Exhaust": days_to_exhaust,
                "Expiry_Risk_Level": "High Risk" if days_to_expiry <= 30 else ("Medium Risk" if days_to_expiry <= 90 else "Low Risk"),
                "AI_Recommendation": "Reorder stock soon" if qty <= reorder else "No immediate action required"
            }
            inv.insert_one(new_item)
            log_event('admin', 'Product Added', f"Added product {new_item['Medicine_Name']} ({batch_id}) to inventory.")
            return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/inventory/<batch_id>', methods=['PUT', 'DELETE'])
def update_delete_inv(batch_id):
    inv = get_coll('inventory')
    if inv is None:
        return jsonify({"success": False, "error": "DB Offline"}), 500
    try:
        if request.method == 'PUT':
            data = request.get_json() or {}
            days_to_expiry = int(data.get('days_to_expiry', 365))
            qty = int(data.get('qty', 0))
            reorder = int(data.get('reorder', 10))
            sales_30 = int(data.get('sales_last_30', 0))
            cost = float(data.get('cost', 0.0))
            category = data.get('category', 'General')
            rate = intelligence.predict_single(category, cost, sales_30) if model_loaded else (sales_30 / 30.0 if sales_30 > 0 else 0.1)
            days_to_exhaust = int(qty / rate) if rate > 0 else 999

            update_data = {
                "Medicine_Name": data.get('name'),
                "Category": data.get('category'),
                "Manufacturer": data.get('manufacturer'),
                "Manufacturing_Date": data.get('manufacturing_date'),
                "Quantity_In_Stock": qty,
                "Reorder_Level": reorder,
                "Unit_Cost_USD": float(data.get('cost', 0.0)),
                "Selling_Price_USD": float(data.get('price', 0.0)),
                "Days_to_Expiry": days_to_expiry,
                "Expiry_Date": data.get('expiry_date'),
                "Sales_Last_30_Days": sales_30,
                "Daily_Consumption_Rate": rate,
                "ML_Predicted_Consumption": rate,
                "ML_Predicted_Days_To_Exhaust": days_to_exhaust,
                "Expiry_Risk_Level": "High Risk" if days_to_expiry <= 30 else ("Medium Risk" if days_to_expiry <= 90 else "Low Risk"),
                "AI_Recommendation": "Reorder stock soon" if qty <= reorder else "No immediate action required"
            }
            inv.update_one({"Batch_ID": batch_id}, {"$set": update_data})
            log_event('admin', 'Product Updated', f"Updated product {update_data['Medicine_Name']} ({batch_id}) details.")
            return jsonify({"success": True})
        else: # DELETE
            item = inv.find_one({"Batch_ID": batch_id})
            med_name = item.get('Medicine_Name', 'Unknown') if item else 'Unknown'
            inv.delete_one({"Batch_ID": batch_id})
            log_event('admin', 'Product Deleted', f"Deleted product {med_name} ({batch_id}) from inventory.")
            return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

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
        if request.is_json:
            data = request.get_json() or {}
        else:
            data = request.form
            
        action = data.get('action')
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        role = data.get('role', 'pharmacist')
        
        # Profile Picture Upload
        profile_pic_url = None
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file and file.filename != '':
                ext = file.filename.rsplit('.', 1)[-1].lower()
                if ext in ['png', 'jpg', 'jpeg', 'gif']:
                    try:
                        import base64
                        file_data = file.read()
                        base64_data = base64.b64encode(file_data).decode('utf-8')
                        profile_pic_url = f"data:image/{ext};base64,{base64_data}"
                    except Exception as upload_err:
                        print(f"Base64 Upload Conversion Error: {upload_err}")

        if action == 'add':
            if users.find_one({"username": username}):
                return jsonify({"success": False, "message": "User already exists"}), 400
            
            user_doc = {
                "username": username,
                "password": password,
                "role": role,
                "profile_pic": profile_pic_url
            }
            users.insert_one(user_doc)
            log_event('admin', 'Staff Created', f"Added {username} as {role}.")
            return jsonify({"success": True})
            
        elif action == 'edit':
            update = {"role": role}
            if password:
                update['password'] = password
            if profile_pic_url:
                update['profile_pic'] = profile_pic_url
                
            users.update_one({"username": username}, {"$set": update})
            log_event('admin', 'Staff Updated', f"Updated role/password for {username}.")
            return jsonify({"success": True})
            
        elif action == 'delete':
            # Prevent removing the last admin account
            target = users.find_one({"username": username})
            if target and target.get('role') == 'admin':
                admin_count = users.count_documents({"role": "admin"})
                if admin_count <= 1:
                    return jsonify({"success": False, "message": "Cannot remove the last administrator account."}), 400
            users.delete_one({"username": username})
            log_event('admin', 'Staff Removed', f"Deleted user account: {username}.")
            return jsonify({"success": True})
            
        return jsonify({"success": False, "message": "Invalid action"}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ─── AUDIT ───────────────────────────────────────────────────────
@app.route('/api/admin/audit')
def get_audit():
    audit = get_coll('audit')
    if audit is None:
        return jsonify([]), 200
    try:
        logs = list(audit.find({}, {"_id": 0}).sort("timestamp", -1).limit(100))
        return jsonify(logs)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ─── SALES ───────────────────────────────────────────────────────
@app.route('/api/admin/sales', methods=['GET'])
def get_sales():
    sales = get_coll('sales')
    if sales is None:
        return jsonify([]), 500
    try:
        return jsonify(list(sales.find({}, {"_id": 0}).sort("timestamp", -1).limit(100)))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ─── PHARMACIST MY SALES ──────────────────────────────────────────
@app.route('/api/my/sales', methods=['GET'])
def get_my_sales():
    sales = get_coll('sales')
    if sales is None:
        return jsonify([]), 200
    try:
        pharmacist = request.args.get('pharmacist')
        query = {"pharmacist": pharmacist} if pharmacist else {}
        my_sales = list(sales.find(query, {"_id": 0}).sort("timestamp", -1).limit(50))
        return jsonify(my_sales)
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

# ─── CHECKOUT ────────────────────────────────────────────────────
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
        log_event(staff_name, 'Dispensed Medicine', f"Customer: {customer_name}. Total: GH₵ {round(total, 2)}.", {"cart": cart, "total": total})
        return jsonify({"success": True, "total": round(total, 2)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ─── REPORTS ─────────────────────────────────────────────────────
@app.route('/api/admin/reports', methods=['GET'])
def admin_reports():
    sales = get_coll('sales')
    if sales is None:
        return jsonify({"total_revenue": 0, "transaction_count": 0, "items_sold": 0, "sales": []}), 200
    try:
        period = request.args.get('period', 'today')
        now = datetime.datetime.utcnow()
        if period == 'month':
            filter_str = now.strftime("%Y-%m")
        elif period == 'year':
            filter_str = now.strftime("%Y")
        else: # today
            filter_str = now.strftime("%Y-%m-%d")
            
        filtered = list(sales.find({"timestamp": {"$regex": f"^{filter_str}"}}, {"_id": 0}).sort("timestamp", -1))
        total_rev = sum(s.get('total_ghs', 0) for s in filtered)
        items_sold = sum(s.get('items', 0) for s in filtered)
        
        return jsonify({
            "period": period,
            "total_revenue": round(total_rev, 2),
            "transaction_count": len(filtered),
            "items_sold": items_sold,
            "sales": filtered
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ─── SETTINGS ────────────────────────────────────────────────────
@app.route('/api/settings', methods=['GET', 'POST'])
def manage_settings():
    settings_coll = get_coll('settings')
    if settings_coll is None:
        return jsonify({"success": False, "error": "DB Offline"}), 500
    try:
        if request.method == 'GET':
            settings = settings_coll.find_one({}, {"_id": 0})
            if not settings:
                settings = {
                    "hospital_name": "Ghana National Hospital",
                    "nhis_id": "GHA-NHIS-9921",
                    "expiry_threshold": 30,
                    "currency": "GH₵",
                    "exchange_rate": 1.0
                }
            return jsonify(settings)
        else:
            data = request.get_json() or {}
            update = {
                "hospital_name": data.get('hospital_name', 'Ghana National Hospital'),
                "nhis_id": data.get('nhis_id', 'GHA-NHIS-9921'),
                "expiry_threshold": int(data.get('expiry_threshold', 30)),
                "currency": data.get('currency', 'GH₵'),
                "exchange_rate": float(data.get('exchange_rate', 1.0))
            }
            settings_coll.update_one({}, {"$set": update}, upsert=True)
            log_event('admin', 'Settings Updated', f"Hospital: {update['hospital_name']}, Threshold: {update['expiry_threshold']} days.")
            return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# Required by Vercel
if __name__ == '__main__':
    from waitress import serve
    print("MedAI GH - Production Server Active")
    print("Local URL: http://localhost:5000")
    serve(app, host='0.0.0.0', port=5000, threads=8)
