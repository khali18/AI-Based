from flask import Flask, send_from_directory, jsonify, request
from flask_cors import CORS
from tinydb import TinyDB, Query
import os
from werkzeug.utils import secure_filename
from ml_model import PharmacyIntelligenceLayer
import datetime
import threading

# Profile Picture Upload Config
UPLOAD_FOLDER = 'public/uploads/profiles'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Global lock for thread-safe database access
db_lock = threading.Lock()

app = Flask(__name__, static_folder='public')
CORS(app)

# global database handles
db = None
sales_db = None
audit_db = None
system_audit_db = None
users_db = None
settings_db = None

# --- DATABASE INITIALIZATION ---
# Using a function to handle self-healing (auto-repair on corruption)
def initialize_database():
    global db, sales_db, audit_db, system_audit_db, users_db, settings_db
    DB_PATH = 'database.json'
    
    try:
        db = TinyDB(DB_PATH)
        # Attempt a read to verify integrity
        db.all()
    except Exception as e:
        print(f"CRITICAL: Database corruption detected ({type(e).__name__}). Self-healing triggered.")
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        db = TinyDB(DB_PATH)
    
    # Create / handle tables
    sales_db = db.table('sales')
    audit_db = db.table('sales_audit')
    system_audit_db = db.table('system_audit')
    users_db = db.table('users')
    settings_db = db.table('settings')

initialize_database()

with db_lock:
    # Initialize models and conditionally seed
    intelligence = PharmacyIntelligenceLayer(db)
    print("Booting Intelligence Layer... training models.")
    df = intelligence.train_demand_forecast_model()
    
    # ALWAYS force seeding to guarantee the exact dataset is used for presentations
    print("Database syncing with provided dataset (project dataset.csv)...")
    intelligence.seed_database_and_predict(df)

# --- SETTINGS SEEDING ---
with db_lock:
    # Always force 1.0 exchange rate to keep system 1:1 with Excel dataset
    settings_db.truncate()
    settings_db.insert({
        "hospital_name": "Ghana National Hospital",
        "nhis_id": "GHA-NHIS-9921",
        "expiry_threshold": 30,
        "currency": "GH₵",
        "exchange_rate": 1.0
    })

    # --- USER REGISTRY SEEDING ---
    if not users_db.all():
        users_db.insert({"username": "admin", "password": "admin123", "role": "admin"})
        users_db.insert({"username": "pharm", "password": "pharm123", "role": "pharmacist"})

# --- STATIC FILE SERVING ---
@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    # API 404 Guard: Don't return index.html for missing API calls
    if path.startswith('api/'):
        return jsonify({"success": False, "message": "API endpoint not found"}), 404
        
    # route fallback to file
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
    
    # Check credentials in DB
    with db_lock:
        user = users_db.get(Query().username == username)
        
    if user and user.get('password') == password:
        role = user.get('role')
        
        # LOG LOGIN
        with db_lock:
            system_audit_db.insert({
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
    with db_lock:
        system_audit_db.insert({
            "event": "Logout",
            "username": username,
            "timestamp": datetime.datetime.now().isoformat(),
            "details": "User manually closed session."
        })
    return jsonify({"success": True})


@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    if request.method == 'POST':
        data = request.json
        with db_lock:
            settings_db.truncate()
            settings_db.insert(data)
        return jsonify({"success": True})
    
    with db_lock:
        settings = settings_db.all()
    return jsonify(settings[0] if settings else {})


@app.route('/api/system-audit', methods=['GET'])
def get_system_audit():
    with db_lock:
        logs = system_audit_db.all()
    logs.reverse()
    return jsonify(logs[:200])


@app.route('/api/dashboard', methods=['GET'])
def get_dashboard():
    with db_lock:
        all_items = db.all()
    total_items = len(all_items)
    
    total_stock_value = sum((item.get('Quantity_In_Stock', 0) * item.get('Selling_Price_USD', 0)) for item in all_items)
    low_stock_count = sum(1 for item in all_items if item.get('Quantity_In_Stock', 0) <= item.get('Reorder_Level', 0))
    
    risk_count = {'High Risk': 0, 'Medium Risk': 0, 'Low Risk': 0}
    expired_count = 0
    
    for item in all_items:
        risk = item.get('Expiry_Risk_Level', 'Low Risk')
        if risk not in risk_count:
            risk_count[risk] = 0
        risk_count[risk] += 1
        if item.get('Days_to_Expiry', 0) <= 30:
            expired_count += 1
            
    # Calculate Today's Revenue
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    with db_lock:
        todays_sales = sales_db.search(Query().date == today)
    today_revenue = sum(s.get('total_ghs', 0) for s in todays_sales)

    return jsonify({
        "totalItems": total_items,
        "totalStockValue": round(total_stock_value, 2),
        "todayRevenue": round(today_revenue, 2),
        "lowStockCount": low_stock_count,
        "expiredOrNearExpiryCount": expired_count,
        "riskCount": risk_count
    })

@app.route('/api/recommendations', methods=['GET'])
def get_recommendations():
    with db_lock:
        all_items = db.all()
    # Sort by Days_to_Expiry ascending
    all_items.sort(key=lambda x: x.get('Days_to_Expiry', 9999))
    high_risk = [i for i in all_items if i.get('Expiry_Risk_Level') == 'High Risk'][:10]
    return jsonify(high_risk)

@app.route('/api/charts/risk', methods=['GET'])
def get_charts():
    categories = {}
    with db_lock:
        all_items = db.all()
    for item in all_items:
        cat = item.get('Category', 'General')
        if cat not in categories:
            categories[cat] = {'name': cat, 'stock': 0}
        categories[cat]['stock'] += item.get('Quantity_In_Stock', 0)
    
    # Return top 5 categories
    top_5 = list(categories.values())[:5]
    return jsonify(top_5)

@app.route('/api/inventory', methods=['GET'])
def get_inventory():
    search = request.args.get('search', '').lower()
    with db_lock:
        all_items = db.all()
    
    if search:
        all_items = [i for i in all_items if search in i.get('Medicine_Name', '').lower() or search in i.get('Category', '').lower() or search in str(i.get('Batch_ID', '')).lower()]
        
    # Sort alphabetically as requested, while showing all 1000+ records
    all_items.sort(key=lambda x: x.get('Medicine_Name', '').lower())
    return jsonify(all_items) # Removed 100-item cutoff

@app.route('/api/inventory', methods=['POST'])
def add_inventory_item():
    data = request.json

    # Validate required fields
    required = ['name', 'category', 'manufacturer', 'manufacturing_date', 'qty', 'reorder', 'cost', 'price', 'days_to_expiry']
    for field in required:
        if field not in data or data[field] is None or str(data[field]).strip() == '':
            return jsonify({"success": False, "message": f"Missing required field: {field}"}), 400

    # Generate a unique Batch ID
    import random
    batch_id = f"BATCH-{random.randint(1000, 9999)}"
    with db_lock:
        # Ensure Batch_ID is unique
        while db.search(Query().Batch_ID == batch_id):
            batch_id = f"BATCH-{random.randint(1000, 9999)}"
        
        # Get dynamic exchange rate from settings
        settings = settings_db.all()
        exchange_rate = float(settings[0].get('exchange_rate', 1.0)) if settings else 14.5

    days_to_expiry = int(data['days_to_expiry'])
    if 'expiry_date' in data and data['expiry_date']:
        expiry_date = data['expiry_date']
        expiry_dt = datetime.datetime.strptime(expiry_date, '%Y-%m-%d')
        days_to_expiry = (expiry_dt - datetime.datetime.now()).days
    else:
        expiry_date = (datetime.datetime.now() + datetime.timedelta(days=days_to_expiry)).strftime('%Y-%m-%d')

    sales_last_30 = int(data.get('sales_last_30', 0))
    qty = int(data['qty'])
    cost_usd  = round(float(data['cost'])  / exchange_rate, 4)
    price_usd = round(float(data['price']) / exchange_rate, 4)

    # AI PREDICTION: Use the Random Forest Model
    daily_rate = intelligence.predict_single(data['category'], cost_usd, sales_last_30)
    
    if daily_rate > 0:
        pred_days_to_exhaust = math.floor(qty / daily_rate)
        if pred_days_to_exhaust > 36500: # Cap at 100 years
            pred_days_to_exhaust = 'Unlimited'
    else:
        pred_days_to_exhaust = 'Unlimited'

    # AI CLASSIFICATION: Probability of Utilization
    risk_level = intelligence.automated_expiry_risk_classifier(pred_days_to_exhaust, days_to_expiry)

    new_item = {
        "Batch_ID": batch_id,
        "Medicine_Name": data['name'],
        "Category": data['category'],
        "Manufacturer": data['manufacturer'],
        "Manufacturing_Date": data['manufacturing_date'],
        "Quantity_In_Stock": qty,
        "Reorder_Level": int(data['reorder']),
        "Cost_Price_USD":    cost_usd,
        "Selling_Price_USD": price_usd,
        "Days_to_Expiry": days_to_expiry,
        "Expiry_Date": expiry_date,
        "Expiry_Risk_Level": risk_level,
        "Sales_Last_30_Days": sales_last_30,
        "ML_Predicted_Consumption": round(daily_rate, 2),
        "ML_Predicted_Days_To_Exhaust": pred_days_to_exhaust,
        "AI_Recommendation": "Reprioritize stock based on AI demand forecast." if risk_level == 'High Risk' else "Monitor stock levels and update consumption data regularly.",
    }

    with db_lock:
        db.insert(new_item)
        system_audit_db.insert({
            "event": "Product Added",
            "username": "Admin",
            "details": f"New medicine added: {data['name']} ({batch_id})",
            "timestamp": datetime.datetime.now().isoformat()
        })

    return jsonify({"success": True, "batch_id": batch_id})


@app.route('/api/inventory/<batch_id>', methods=['PUT'])
def update_inventory_item(batch_id):
    data = request.json

    # Validate required fields
    required = ['name', 'category', 'manufacturer', 'manufacturing_date', 'qty', 'reorder', 'cost', 'price', 'days_to_expiry']
    for field in required:
        if field not in data or data[field] is None or str(data[field]).strip() == '':
            return jsonify({"success": False, "message": f"Missing required field: {field}"}), 400

    with db_lock:
        item = db.get(Query().Batch_ID == batch_id)
        if not item:
            return jsonify({"success": False, "message": "Product not found"}), 404
            
        # Get dynamic exchange rate from settings
        settings = settings_db.all()
        exchange_rate = float(settings[0].get('exchange_rate', 1.0)) if settings else 14.5

    days_to_expiry = int(data['days_to_expiry'])
    if 'expiry_date' in data and data['expiry_date']:
        expiry_date = data['expiry_date']
        expiry_dt = datetime.datetime.strptime(expiry_date, '%Y-%m-%d')
        days_to_expiry = (expiry_dt - datetime.datetime.now()).days
    else:
        expiry_date = (datetime.datetime.now() + datetime.timedelta(days=days_to_expiry)).strftime('%Y-%m-%d')

    sales_last_30 = int(data.get('sales_last_30', 0))
    qty = int(data['qty'])
    cost_usd  = round(float(data['cost'])  / exchange_rate, 4)
    price_usd = round(float(data['price']) / exchange_rate, 4)

    # AI PREDICTION: Use the Random Forest Model
    daily_rate = intelligence.predict_single(data['category'], cost_usd, sales_last_30)
    
    if daily_rate > 0:
        pred_days_to_exhaust = math.floor(qty / daily_rate)
        if pred_days_to_exhaust > 36500: # Cap at 100 years
            pred_days_to_exhaust = 'Unlimited'
    else:
        pred_days_to_exhaust = 'Unlimited'

    # AI CLASSIFICATION: Probability of Utilization
    risk_level = intelligence.automated_expiry_risk_classifier(pred_days_to_exhaust, days_to_expiry)

    updated_item = {
        "Batch_ID": batch_id,
        "Medicine_Name": data['name'],
        "Category": data['category'],
        "Manufacturer": data['manufacturer'],
        "Manufacturing_Date": data['manufacturing_date'],
        "Quantity_In_Stock": qty,
        "Reorder_Level": int(data['reorder']),
        "Cost_Price_USD":    cost_usd,
        "Selling_Price_USD": price_usd,
        "Days_to_Expiry": days_to_expiry,
        "Expiry_Date": expiry_date,
        "Expiry_Risk_Level": risk_level,
        "Sales_Last_30_Days": sales_last_30,
        "ML_Predicted_Consumption": round(daily_rate, 2),
        "ML_Predicted_Days_To_Exhaust": pred_days_to_exhaust,
        "AI_Recommendation": "Reprioritize stock based on AI demand forecast." if risk_level == 'High Risk' else "Monitor stock levels and update consumption data regularly.",
    }

    with db_lock:
        db.update(updated_item, Query().Batch_ID == batch_id)
        system_audit_db.insert({
            "event": "Product Updated",
            "username": "Admin",
            "details": f"Medicine updated: {data['name']} ({batch_id})",
            "timestamp": datetime.datetime.now().isoformat()
        })

    return jsonify({"success": True})


@app.route('/api/inventory/<batch_id>', methods=['DELETE'])
def delete_inventory_item(batch_id):
    with db_lock:
        item = db.get(Query().Batch_ID == batch_id)
        if not item:
            return jsonify({"success": False, "message": "Product not found"}), 404

        db.remove(Query().Batch_ID == batch_id)
        system_audit_db.insert({
            "event": "Product Deleted",
            "username": "Admin",
            "details": f"Medicine deleted: {item['Medicine_Name']} ({batch_id})",
            "timestamp": datetime.datetime.now().isoformat()
        })

    return jsonify({"success": True})


@app.route('/api/forecast', methods=['GET'])
def get_forecast():
    search = request.args.get('search', '').lower()
    with db_lock:
        all_items = db.all()
    
    if search:
        all_items = [i for i in all_items if search in i.get('Medicine_Name', '').lower()]
        
    # Build payload to match frontend exactly
    forecast_data = []
    for item in all_items:
        days_to_exhaust = item.get('ML_Predicted_Days_To_Exhaust')
        
        # calculate outdate
        if days_to_exhaust == 'Unlimited' or days_to_exhaust is None:
            stockout_date = None
            sort_val = float('inf')
        else:
            try:
                days_num = float(days_to_exhaust)
                delta = datetime.timedelta(days=days_num)
                stockout_date = (datetime.datetime.now() + delta).isoformat() + "Z"
                sort_val = days_num
            except:
                stockout_date = None
                sort_val = float('inf')
            
        forecast_data.append({
            "Batch_ID": item.get('Batch_ID'),
            "Medicine_Name": item.get('Medicine_Name'),
            "Category": item.get('Category'),
            "Manufacturer": item.get('Manufacturer'),
            "Manufacturing_Date": item.get('Manufacturing_Date'),
            "Quantity_In_Stock": item.get('Quantity_In_Stock'),
            "Reorder_Level": item.get('Reorder_Level'),
            "Daily_Consumption_Rate": item.get('ML_Predicted_Consumption'),
            "Days_to_Exhaust_Stock": days_to_exhaust if days_to_exhaust == 'Unlimited' else float('inf') if type(days_to_exhaust) == str else days_to_exhaust,
            "Predicted_Stockout_Date": stockout_date,
            "Expiry_Date": item.get('Expiry_Date'),
            "Expiry_Risk_Level": item.get('Expiry_Risk_Level'),
            "AI_Recommendation": item.get('AI_Recommendation', 'No immediate action required'),
            "_sort_val": sort_val # internal
        })
        
    forecast_data.sort(key=lambda x: x['_sort_val'])
    
    # Clean up _sort_val before returning all rows
    for dict_item in forecast_data:
        if dict_item['Days_to_Exhaust_Stock'] == float('inf'):
            dict_item['Days_to_Exhaust_Stock'] = None # Maps back to infinity equivalent on UI or will be handled
        del dict_item['_sort_val']
        
    return jsonify(forecast_data) # Removed cutoff

@app.route('/api/checkout', methods=['POST'])
def checkout():
    data = request.json
    cart = data.get('cart', [])
    staff_name = data.get('staff_name', 'Unknown Staff')
    total = 0
    
    for item in cart:
        batch_id = item.get('Batch_ID')
        qty = int(item.get('qty', 1))
        
        # Find item to deduct stock
        with db_lock:
            record = db.search(Query().Batch_ID == batch_id)
            if record:
                doc = record[0]
                if doc.get('Quantity_In_Stock', 0) >= qty:
                    new_qty = doc['Quantity_In_Stock'] - qty
                    db.update({'Quantity_In_Stock': new_qty}, Query().Batch_ID == batch_id)
                    total += doc.get('Selling_Price_USD', 0) * qty
                else:
                    return jsonify({"success": False, "error": f"Not enough stock for {doc.get('Medicine_Name')}"}), 400
                
    # Record Sale
    if total > 0:
        with db_lock:
            sales_db.insert({
                "date": datetime.datetime.now().strftime("%Y-%m-%d"),
                "timestamp": datetime.datetime.now().isoformat(),
                "total_ghs": round(total, 2),
                "items": len(cart),
                "pharmacist": staff_name,
                "details": ", ".join([f"{i.get('name')} (x{i.get('qty')})" for i in cart])
            })
            
            # LOG TO SYSTEM AUDIT
            system_audit_db.insert({
                "event": "Pharmacy Sale",
                "username": staff_name,
                "details": f"Sold {len(cart)} items for GH₵ {round(total, 2)}",
                "timestamp": datetime.datetime.now().isoformat(),
                "metadata": {
                    "total": round(total, 2),
                    "items_count": len(cart),
                    "cart": cart
                }
            })
        
    return jsonify({"success": True, "total": round(total, 2)})

@app.route('/api/admin/audit', methods=['GET'])
def get_audit():
    # Return last 100 logs
    with db_lock:
        logs = system_audit_db.all()
    logs.reverse()
    return jsonify(logs[:100])

@app.route('/api/admin/sales', methods=['GET'])
def get_all_sales():
    with db_lock:
        sales = sales_db.all()
    sales.reverse()
    return jsonify(sales[:100])

# Users management endpoints
@app.route('/api/users', methods=['GET'])
def get_users():
    with db_lock:
        users = users_db.all()
    return jsonify(users)

@app.route('/api/admin/users', methods=['POST'])
def save_user():
    # Handle multipart/form-data for file uploads
    if request.is_json:
        data = request.json
    else:
        data = request.form

    username = data.get('username')
    password = data.get('password')
    role = data.get('role', 'pharmacist')
    action = data.get('action', 'add')
    
    profile_pic_url = None
    
    # Handle File Upload
    if 'profile_pic' in request.files:
        file = request.files['profile_pic']
        if file and file.filename != '':
            ext = file.filename.rsplit('.', 1)[1].lower()
            if ext in ALLOWED_EXTENSIONS:
                filename = secure_filename(f"{username}_profile.{ext}")
                file.save(os.path.join(UPLOAD_FOLDER, filename))
                profile_pic_url = f"/uploads/profiles/{filename}"

    with db_lock:
        if action == 'add':
            if users_db.get(Query().username == username):
                return jsonify({"success": False, "message": "User already exists"}), 400
            
            user_doc = {
                "username": username, 
                "password": password, 
                "role": role,
                "profile_pic": profile_pic_url
            }
            users_db.insert(user_doc)
            
        elif action == 'edit':
            update_data = {"role": role}
            if password: # only update password if provided
                update_data["password"] = password
            if profile_pic_url:
                update_data["profile_pic"] = profile_pic_url
                
            users_db.update(update_data, Query().username == username)
            
        elif action == 'delete':
            if username == 'admin':
                return jsonify({"success": False, "message": "Cannot delete primary admin"}), 400
            users_db.remove(Query().username == username)
        
    return jsonify({"success": True})

@app.route('/api/admin/reports', methods=['GET'])
def admin_reports():
    period = request.args.get('period', 'today')
    now = datetime.datetime.now()
    
    if period == 'month':
        filter_str = now.strftime("%Y-%m")
    elif period == 'year':
        filter_str = now.strftime("%Y")
    else: # today
        filter_str = now.strftime("%Y-%m-%d")
        
    with db_lock:
        # Search for sales where the date string starts with the filter (e.g., '2026-04')
        filtered_sales = [s for s in sales_db.all() if s.get('date', '').startswith(filter_str)]
    
    total_rev = sum(s.get('total_ghs', 0) for s in filtered_sales)
    txn_count = len(filtered_sales)
    items_sold = sum(s.get('items', 0) for s in filtered_sales)
    
    return jsonify({
        "period": period,
        "total_revenue": round(total_rev, 2),
        "transaction_count": txn_count,
        "items_sold": items_sold,
        "sales": filtered_sales[:100] # Return recent sales for the detailed table
    })

@app.route('/api/sales/today', methods=['GET'])
def sales_today():
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    pharmacist_filter = request.args.get('pharmacist', None)
    
    with db_lock:
        todays_sales = sales_db.search(Query().date == today)
    
    # Filter by pharmacist if provided (personal dashboard)
    if pharmacist_filter:
        todays_sales = [s for s in todays_sales if s.get('pharmacist', '').lower() == pharmacist_filter.lower()]
    
    total_rev = sum(s['total_ghs'] for s in todays_sales)
    transaction_count = len(todays_sales)
    
    return jsonify({
        "total_revenue_ghs": round(total_rev, 2),
        "transaction_count": transaction_count
    })

@app.route('/api/my/sales', methods=['GET'])
def my_sales():
    """Returns sales history for a specific pharmacist only."""
    pharmacist = request.args.get('pharmacist', None)
    if not pharmacist:
        return jsonify([]), 200
    
    with db_lock:
        all_sales = sales_db.all()
    # Case-insensitive filter by pharmacist name
    my = [s for s in all_sales if s.get('pharmacist', '').lower() == pharmacist.lower()]
    my.reverse()  # Latest first
    return jsonify(my[:50])


if __name__ == '__main__':
    from waitress import serve
    print("MedAI GH Production Server started on http://localhost:5000")
    # Increased threads to handle concurrent frontend requests better
    serve(app, host='0.0.0.0', port=5000, threads=8)
