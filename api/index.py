from flask import Flask, jsonify, request
from flask_cors import CORS
import os
import sqlite3
import datetime
import random
import re
from dotenv import load_dotenv
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

def get_db():
    conn = sqlite3.connect('medai.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def align_expiry_dates_in_db():
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if database has inventory table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='inventory'")
        if not cursor.fetchone():
            conn.close()
            return
            
        # Get expiry threshold from settings
        cursor.execute("SELECT expiry_threshold FROM settings LIMIT 1")
        settings = cursor.fetchone()
        threshold = settings['expiry_threshold'] if settings else 30
        
        cursor.execute("SELECT Batch_ID, Expiry_Date, Quantity_In_Stock, Reorder_Level FROM inventory")
        rows = cursor.fetchall()
        
        today = datetime.date.today()
        
        for row in rows:
            batch_id = row['Batch_ID']
            expiry_date_str = row['Expiry_Date']
            qty = row['Quantity_In_Stock']
            reorder = row['Reorder_Level']
            
            if expiry_date_str:
                try:
                    expiry_date = datetime.datetime.strptime(expiry_date_str, '%Y-%m-%d').date()
                    days_to_expiry = (expiry_date - today).days
                    
                    # Classify expiry risk level and AI recommendation
                    risk_level = "High Risk" if days_to_expiry <= threshold else ("Medium Risk" if days_to_expiry <= threshold * 3 else "Low Risk")
                    ai_rec = "Reorder stock soon" if qty <= reorder else "No immediate action required"
                    
                    cursor.execute('''UPDATE inventory SET 
                        Days_to_Expiry = ?,
                        Expiry_Risk_Level = ?,
                        AI_Recommendation = ?
                        WHERE Batch_ID = ?''', (days_to_expiry, risk_level, ai_rec, batch_id))
                except Exception as ex:
                    print(f"Error aligning batch {batch_id}: {ex}")
                    
        conn.commit()
        conn.close()
        print("Database inventory dates, risk levels, and AI recommendations successfully aligned with today's date.")
    except Exception as e:
        print(f"Error in align_expiry_dates_in_db: {e}")

# Run alignment immediately on boot/import
align_expiry_dates_in_db()

# Helper: Log event to audit collection
def log_event(username, event, details, metadata=None):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO audit (timestamp, username, event, details, metadata)
            VALUES (?, ?, ?, ?, ?)
        ''', (datetime.datetime.utcnow().isoformat(), username, event, details, str(metadata) if metadata else None))
        conn.commit()
        conn.close()
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
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        conn.close()
        return jsonify({"status": "ok", "db": "connected"})
    except:
        return jsonify({"status": "error", "db": "offline"})

# ─── DASHBOARD ──────────────────────────────────────────────────
@app.route('/api/dashboard')
def get_dashboard():
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Load settings
        cursor.execute("SELECT * FROM settings LIMIT 1")
        settings = cursor.fetchone()
        threshold = settings['expiry_threshold'] if settings else 30
        exchange_rate = settings['exchange_rate'] if settings else 1.0

        cursor.execute("SELECT * FROM inventory")
        items = cursor.fetchall()
        
        # Calculate stock value in USD
        total_value = round(sum(i['Quantity_In_Stock'] * i['Selling_Price_USD'] for i in items if i['Quantity_In_Stock']), 2)
        
        # Calculate low stock count
        low_stock = sum(1 for i in items if i['Quantity_In_Stock'] <= i['Reorder_Level'])
        
        # Calculate near-expiry count
        expiry_risk = sum(1 for i in items if i['Days_to_Expiry'] <= threshold)
        
        # Calculate today's revenue
        today_str = datetime.datetime.utcnow().strftime('%Y-%m-%d')
        cursor.execute("SELECT * FROM sales WHERE timestamp LIKE ?", (f"{today_str}%",))
        today_sales = cursor.fetchall()
        today_rev = round(sum(s['total_ghs'] for s in today_sales), 2)

        # Classify all risks
        risk_count = {"High Risk": 0, "Medium Risk": 0, "Low Risk": 0}
        for i in items:
            risk = get_risk_label(i['Days_to_Expiry'], threshold)
            risk_count[risk] += 1

        conn.close()
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
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM inventory WHERE Expiry_Risk_Level = 'High Risk' ORDER BY Days_to_Expiry ASC LIMIT 10")
        high_risk = [dict(row) for row in cursor.fetchall()]
        if not high_risk:
            cursor.execute("SELECT * FROM inventory ORDER BY Days_to_Expiry ASC LIMIT 10")
            high_risk = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify(high_risk)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ─── CHARTS RISK ─────────────────────────────────────────────────
@app.route('/api/charts/risk')
def get_chart_risk():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT Category, SUM(Quantity_In_Stock) as stock FROM inventory GROUP BY Category ORDER BY stock DESC LIMIT 5")
        rows = cursor.fetchall()
        categories = [{"name": row['Category'] if row['Category'] else 'General', "stock": row['stock']} for row in rows]
        conn.close()
        return jsonify(categories)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ─── DEMAND FORECASTING ───────────────────────────────────────────
@app.route('/api/forecast')
def get_forecast():
    try:
        search = request.args.get('search', '').strip()
        conn = get_db()
        cursor = conn.cursor()
        
        if search:
            cursor.execute("SELECT * FROM inventory WHERE Medicine_Name LIKE ? OR Batch_ID LIKE ? ORDER BY Medicine_Name ASC LIMIT 100", (f"%{search}%", f"%{search}%"))
        else:
            cursor.execute("SELECT * FROM inventory ORDER BY Medicine_Name ASC LIMIT 100")
            
        items = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        forecasted = []
        for item in items:
            stock = item.get('Quantity_In_Stock', 0)
            days = item.get('ML_Predicted_Days_To_Exhaust')
            rate = item.get('Daily_Consumption_Rate') or item.get('ML_Predicted_Consumption', 0.1)
            if rate is None or rate == 0:
                rate = 0.1
            
            if days is None or days == 999:
                days = int(stock / rate)
            
            if days >= 999:
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
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        data = request.get_json() or {}
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        
        cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            role = user['role'] if user['role'] else 'pharmacist'
            log_event(username, 'Login', f"User logged into {role} portal.", {"role": role})
            return jsonify({
                "success": True,
                "role": role,
                "username": user['username'],
                "profile_pic": user['profile_pic']
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
    try:
        data = request.get_json() or {}
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        role = data.get('role', 'pharmacist')

        if not username or not password:
            return jsonify({"success": False, "message": "Username and password are required"}), 400

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        if cursor.fetchone():
            conn.close()
            return jsonify({"success": False, "message": "Username already exists"}), 400

        cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (username, password, role))
        conn.commit()
        conn.close()
        
        log_event('admin', 'Staff Created', f"Registered staff {username} as {role}.")
        return jsonify({"success": True, "username": username, "role": role})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ─── INVENTORY ───────────────────────────────────────────────────
@app.route('/api/inventory', methods=['GET', 'POST'])
def get_inv():
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        if request.method == 'GET':
            search = request.args.get('search', '').strip()
            if search:
                cursor.execute("SELECT * FROM inventory WHERE Medicine_Name LIKE ? OR Batch_ID LIKE ? OR Category LIKE ? LIMIT 100", (f"%{search}%", f"%{search}%", f"%{search}%"))
            else:
                cursor.execute("SELECT * FROM inventory LIMIT 100")
            items = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return jsonify(items)
            
        else: # POST: Add Product
            data = request.get_json() or {}
            
            while True:
                batch_id = f"BATCH-{random.randint(1000, 9999)}"
                cursor.execute("SELECT Batch_ID FROM inventory WHERE Batch_ID = ?", (batch_id,))
                if not cursor.fetchone():
                    break
            
            days_to_expiry = int(data.get('days_to_expiry', 365))
            qty = int(data.get('qty', 0))
            reorder = int(data.get('reorder', 10))
            sales_30 = int(data.get('sales_last_30', 0))
            cost = float(data.get('cost', 0.0))
            category = data.get('category', 'General')
            rate = intelligence.predict_single(category, cost, sales_30) if model_loaded else (sales_30 / 30.0 if sales_30 > 0 else 0.1)
            days_to_exhaust = int(qty / rate) if rate > 0 else 999

            new_item = (
                batch_id,
                data.get('name'),
                category,
                data.get('manufacturer'),
                data.get('manufacturing_date'),
                qty,
                reorder,
                cost,
                float(data.get('price', 0.0)),
                days_to_expiry,
                data.get('expiry_date'),
                sales_30,
                rate,
                rate,
                days_to_exhaust,
                "High Risk" if days_to_expiry <= 30 else ("Medium Risk" if days_to_expiry <= 90 else "Low Risk"),
                "Reorder stock soon" if qty <= reorder else "No immediate action required"
            )
            
            cursor.execute('''INSERT INTO inventory 
                (Batch_ID, Medicine_Name, Category, Manufacturer, Manufacturing_Date, Quantity_In_Stock, Reorder_Level, 
                Unit_Cost_USD, Selling_Price_USD, Days_to_Expiry, Expiry_Date, Sales_Last_30_Days, 
                Daily_Consumption_Rate, ML_Predicted_Consumption, ML_Predicted_Days_To_Exhaust, Expiry_Risk_Level, AI_Recommendation)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', new_item)
            conn.commit()
            conn.close()
            
            log_event('admin', 'Product Added', f"Added product {data.get('name')} ({batch_id}) to inventory.")
            return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/inventory/<batch_id>', methods=['PUT', 'DELETE'])
def update_delete_inv(batch_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
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
            
            risk_level = "High Risk" if days_to_expiry <= 30 else ("Medium Risk" if days_to_expiry <= 90 else "Low Risk")
            ai_rec = "Reorder stock soon" if qty <= reorder else "No immediate action required"

            cursor.execute('''UPDATE inventory SET 
                Medicine_Name=?, Category=?, Manufacturer=?, Manufacturing_Date=?, Quantity_In_Stock=?, Reorder_Level=?, 
                Unit_Cost_USD=?, Selling_Price_USD=?, Days_to_Expiry=?, Expiry_Date=?, Sales_Last_30_Days=?, 
                Daily_Consumption_Rate=?, ML_Predicted_Consumption=?, ML_Predicted_Days_To_Exhaust=?, Expiry_Risk_Level=?, AI_Recommendation=?
                WHERE Batch_ID=?
            ''', (data.get('name'), category, data.get('manufacturer'), data.get('manufacturing_date'), qty, reorder,
                  cost, float(data.get('price', 0.0)), days_to_expiry, data.get('expiry_date'), sales_30,
                  rate, rate, days_to_exhaust, risk_level, ai_rec, batch_id))
            conn.commit()
            conn.close()
            
            log_event('admin', 'Product Updated', f"Updated product {data.get('name')} ({batch_id}) details.")
            return jsonify({"success": True})
        else: # DELETE
            cursor.execute("SELECT Medicine_Name FROM inventory WHERE Batch_ID = ?", (batch_id,))
            item = cursor.fetchone()
            med_name = item['Medicine_Name'] if item else 'Unknown'
            
            cursor.execute("DELETE FROM inventory WHERE Batch_ID = ?", (batch_id,))
            conn.commit()
            conn.close()
            log_event('admin', 'Product Deleted', f"Deleted product {med_name} ({batch_id}) from inventory.")
            return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ─── USERS ───────────────────────────────────────────────────────
@app.route('/api/users', methods=['GET'])
def get_users():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT username, role, profile_pic FROM users")
        users = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify(users)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/users', methods=['POST'])
def manage_users():
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

        conn = get_db()
        cursor = conn.cursor()

        if action == 'add':
            cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
            if cursor.fetchone():
                conn.close()
                return jsonify({"success": False, "message": "User already exists"}), 400
            
            cursor.execute("INSERT INTO users (username, password, role, profile_pic) VALUES (?, ?, ?, ?)", (username, password, role, profile_pic_url))
            conn.commit()
            log_event('admin', 'Staff Created', f"Added {username} as {role}.")
            conn.close()
            return jsonify({"success": True})
            
        elif action == 'edit':
            if password and profile_pic_url:
                cursor.execute("UPDATE users SET role=?, password=?, profile_pic=? WHERE username=?", (role, password, profile_pic_url, username))
            elif password:
                cursor.execute("UPDATE users SET role=?, password=? WHERE username=?", (role, password, username))
            elif profile_pic_url:
                cursor.execute("UPDATE users SET role=?, profile_pic=? WHERE username=?", (role, profile_pic_url, username))
            else:
                cursor.execute("UPDATE users SET role=? WHERE username=?", (role, username))
                
            conn.commit()
            log_event('admin', 'Staff Updated', f"Updated role/password for {username}.")
            conn.close()
            return jsonify({"success": True})
            
        elif action == 'delete':
            cursor.execute("SELECT role FROM users WHERE username = ?", (username,))
            target = cursor.fetchone()
            if target and target['role'] == 'admin':
                cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
                admin_count = cursor.fetchone()[0]
                if admin_count <= 1:
                    conn.close()
                    return jsonify({"success": False, "message": "Cannot remove the last administrator account."}), 400
                    
            cursor.execute("DELETE FROM users WHERE username = ?", (username,))
            conn.commit()
            log_event('admin', 'Staff Removed', f"Deleted user account: {username}.")
            conn.close()
            return jsonify({"success": True})
            
        conn.close()
        return jsonify({"success": False, "message": "Invalid action"}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ─── PHARMACIST MY SALES ──────────────────────────────────────────
@app.route('/api/my/sales', methods=['GET'])
def get_my_sales():
    try:
        pharmacist = request.args.get('pharmacist')
        conn = get_db()
        cursor = conn.cursor()
        if pharmacist:
            cursor.execute("SELECT * FROM sales WHERE pharmacist = ? ORDER BY timestamp DESC LIMIT 50", (pharmacist,))
        else:
            cursor.execute("SELECT * FROM sales ORDER BY timestamp DESC LIMIT 50")
        my_sales = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify(my_sales)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ─── SALES TODAY ──────────────────────────────────────────────────
@app.route('/api/sales/today', methods=['GET'])
def sales_today():
    try:
        today = datetime.datetime.utcnow().strftime('%Y-%m-%d')
        pharmacist = request.args.get('pharmacist')
        conn = get_db()
        cursor = conn.cursor()
        
        if pharmacist:
            cursor.execute("SELECT * FROM sales WHERE timestamp LIKE ? AND pharmacist = ?", (f"{today}%", pharmacist))
        else:
            cursor.execute("SELECT * FROM sales WHERE timestamp LIKE ?", (f"{today}%",))
            
        all_sales = cursor.fetchall()
        total = sum(s['total_ghs'] for s in all_sales)
        conn.close()
        return jsonify({"total_revenue_ghs": round(total, 2), "transaction_count": len(all_sales)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ─── CHECKOUT ────────────────────────────────────────────────────
@app.route('/api/checkout', methods=['POST'])
def checkout():
    try:
        data = request.get_json() or {}
        cart = data.get('cart', [])
        staff_name = data.get('staff_name', 'Unknown')
        customer_name = data.get('customer_name', 'Walk-in Customer')
        
        conn = get_db()
        cursor = conn.cursor()
        
        total = 0
        for item in cart:
            cursor.execute("SELECT * FROM inventory WHERE Batch_ID = ?", (item.get('Batch_ID'),))
            db_item = cursor.fetchone()
            
            if not db_item or db_item['Quantity_In_Stock'] < item.get('qty', 1):
                conn.close()
                return jsonify({"success": False, "error": f"Insufficient stock for {item.get('name')}"}), 400
                
            cursor.execute("UPDATE inventory SET Quantity_In_Stock = Quantity_In_Stock - ? WHERE Batch_ID = ?", (item['qty'], item['Batch_ID']))
            
            price = item.get('price', db_item['Selling_Price_USD'])
            total += item['qty'] * price

        import json
        details_json = json.dumps(cart)
        cursor.execute('''INSERT INTO sales (timestamp, pharmacist, customer_name, items, total_ghs, details)
            VALUES (?, ?, ?, ?, ?, ?)''', (
                datetime.datetime.utcnow().isoformat(),
                staff_name,
                customer_name,
                len(cart),
                round(total, 2),
                details_json
            ))
            
        conn.commit()
        conn.close()
        
        log_event(staff_name, 'Dispensed Medicine', f"Customer: {customer_name}. Total: GH\u20b5 {round(total, 2)}.", {"cart": cart, "total": total, "customer_name": customer_name})
        return jsonify({"success": True, "total": round(total, 2)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ─── GET MY PURCHASES ───────────────────────────────────────────
@app.route('/api/my/purchases')
def get_my_purchases():
    try:
        username = request.args.get('username', '').strip()
        if not username:
            return jsonify([])

        conn = get_db()
        cursor = conn.cursor()

        # Log the patient's check activity
        log_event(username, 'Purchases Checked', 'Patient checked safety/expiry status of clinic-dispensed medicines.')

        cursor.execute("SELECT * FROM sales WHERE customer_name = ? ORDER BY timestamp DESC", (username,))
        rows = cursor.fetchall()

        purchases = []
        import json
        for row in rows:
            try:
                items = json.loads(row['details'])
                for item in items:
                    batch_id = item.get('Batch_ID')
                    cursor.execute("SELECT * FROM inventory WHERE Batch_ID = ?", (batch_id,))
                    inv_item = cursor.fetchone()
                    if inv_item:
                        purchases.append({
                            "batch_id": batch_id,
                            "name": inv_item['Medicine_Name'],
                            "manufacturer": inv_item['Manufacturer'],
                            "expiry_date": inv_item['Expiry_Date'],
                            "days_to_expiry": inv_item['Days_to_Expiry'],
                            "risk_level": inv_item['Expiry_Risk_Level'],
                            "purchase_date": row['timestamp']
                        })
            except Exception:
                pass

        conn.close()
        return jsonify(purchases)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ─── ADMIN AUDIT LOG ─────────────────────────────────────────────
@app.route('/api/admin/audit', methods=['GET'])
def get_audit_logs():
    try:
        limit = request.args.get('limit', 500)
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM audit ORDER BY timestamp DESC LIMIT ?", (int(limit),))
        rows = cursor.fetchall()
        conn.close()

        import json
        logs = []
        for row in rows:
            entry = dict(row)
            # Parse metadata string back into object so JS can do log.metadata?.role etc.
            raw_meta = entry.get('metadata')
            if raw_meta:
                try:
                    entry['metadata'] = json.loads(raw_meta.replace("'", '"'))
                except Exception:
                    entry['metadata'] = {}
            else:
                entry['metadata'] = {}
            logs.append(entry)

        return jsonify(logs)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ─── REPORTS ─────────────────────────────────────────────────────
@app.route('/api/admin/reports', methods=['GET'])
def admin_reports():
    try:
        period = request.args.get('period', 'today')
        now = datetime.datetime.utcnow()
        if period == 'month':
            filter_str = now.strftime("%Y-%m")
        elif period == 'year':
            filter_str = now.strftime("%Y")
        else: # today
            filter_str = now.strftime("%Y-%m-%d")
            
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sales WHERE timestamp LIKE ? ORDER BY timestamp DESC", (f"{filter_str}%",))
        filtered = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        total_rev = sum(s['total_ghs'] for s in filtered)
        items_sold = sum(s['items'] for s in filtered)
        
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
    try:
        conn = get_db()
        cursor = conn.cursor()
        if request.method == 'GET':
            cursor.execute("SELECT * FROM settings LIMIT 1")
            settings = cursor.fetchone()
            if settings:
                conn.close()
                return jsonify(dict(settings))
            else:
                conn.close()
                return jsonify({
                    "hospital_name": "Ghana National Hospital",
                    "nhis_id": "GHA-NHIS-9921",
                    "expiry_threshold": 30,
                    "currency": "GH₵",
                    "exchange_rate": 1.0
                })
        else:
            data = request.get_json() or {}
            update = {
                "hospital_name": data.get('hospital_name', 'Ghana National Hospital'),
                "nhis_id": data.get('nhis_id', 'GHA-NHIS-9921'),
                "expiry_threshold": int(data.get('expiry_threshold', 30)),
                "currency": data.get('currency', 'GH₵'),
                "exchange_rate": float(data.get('exchange_rate', 1.0))
            }
            cursor.execute("SELECT COUNT(*) FROM settings")
            if cursor.fetchone()[0] == 0:
                cursor.execute('''INSERT INTO settings (hospital_name, nhis_id, expiry_threshold, currency, exchange_rate)
                    VALUES (?, ?, ?, ?, ?)''', (update['hospital_name'], update['nhis_id'], update['expiry_threshold'], update['currency'], update['exchange_rate']))
            else:
                cursor.execute('''UPDATE settings SET hospital_name=?, nhis_id=?, expiry_threshold=?, currency=?, exchange_rate=?''',
                    (update['hospital_name'], update['nhis_id'], update['expiry_threshold'], update['currency'], update['exchange_rate']))
            
            conn.commit()
            conn.close()
            
            log_event('admin', 'Settings Updated', f"Hospital: {update['hospital_name']}, Threshold: {update['expiry_threshold']} days.")
            return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ─── REFUNDS ─────────────────────────────────────────────────────
@app.route('/api/refunds', methods=['GET', 'POST'])
def refunds_api():
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        if request.method == 'GET':
            pharmacist = request.args.get('pharmacist')
            if pharmacist:
                cursor.execute("SELECT * FROM refunds WHERE pharmacist_username = ? ORDER BY timestamp DESC", (pharmacist,))
            else:
                cursor.execute("SELECT * FROM refunds ORDER BY timestamp DESC")
                
            refunds = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return jsonify(refunds)
            
        else: # POST
            data = request.get_json() or {}
            pharmacist = data.get('pharmacist_username', 'Unknown')
            amount = float(data.get('amount', 0.0))
            reason = data.get('reason', '')
            medicine_name = data.get('medicine_name', 'Unknown')
            
            cursor.execute('''INSERT INTO refunds (pharmacist_username, amount, reason, status, timestamp, medicine_name) 
                VALUES (?, ?, ?, ?, ?, ?)''', (pharmacist, amount, reason, 'Pending', datetime.datetime.utcnow().isoformat(), medicine_name))
            conn.commit()
            conn.close()
            
            log_event(pharmacist, 'Refund Request', f"Requested refund of GH₵ {amount}. Reason: {reason}.")
            return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/refunds/<int:refund_id>', methods=['PUT'])
def update_refund_api(refund_id):
    try:
        data = request.get_json() or {}
        status = data.get('status')
        admin_username = data.get('admin_username', 'admin')
        
        if status not in ['Approved', 'Rejected']:
            return jsonify({"success": False, "error": "Invalid status"}), 400
            
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM refunds WHERE id = ?", (refund_id,))
        refund = cursor.fetchone()
        if not refund:
            conn.close()
            return jsonify({"success": False, "error": "Refund not found"}), 404
            
        cursor.execute("UPDATE refunds SET status = ? WHERE id = ?", (status, refund_id))
        conn.commit()
        conn.close()
        
        log_event(admin_username, f"Refund {status}", f"Refund #{refund_id} for {refund['pharmacist_username']} was {status}.")
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ─── MEDICINE VERIFICATION (User/Patient Portal) ──────────────────────
@app.route('/api/verify')
def verify_medicine():
    try:
        batch_id = request.args.get('batch_id', '').strip()
        name = request.args.get('name', '').strip()

        if not batch_id and not name:
            return jsonify({"error": "Please provide a batch_id or medicine name."}), 400

        conn = get_db()
        cursor = conn.cursor()

        # Load expiry threshold from settings
        cursor.execute("SELECT expiry_threshold FROM settings LIMIT 1")
        settings = cursor.fetchone()
        threshold = settings['expiry_threshold'] if settings else 30

        if batch_id:
            cursor.execute("SELECT * FROM inventory WHERE Batch_ID = ?", (batch_id,))
            item = cursor.fetchone()
        else:
            cursor.execute("SELECT * FROM inventory WHERE Medicine_Name LIKE ? ORDER BY Days_to_Expiry ASC LIMIT 1", (f"%{name}%",))
            item = cursor.fetchone()

        conn.close()

        username = request.args.get('username', 'anonymous')

        if not item:
            # Not found in database — possibly counterfeit or unregistered
            log_event(username, 'Medicine Verification', f"Verification attempted for unknown item: batch='{batch_id}' name='{name}'. Result: UNVERIFIED.")
            return jsonify({
                "authentic": False,
                "found": False,
                "expiry_status": "UNKNOWN",
                "verdict": "UNVERIFIED",
                "verdict_color": "gray",
                "message": "This batch ID or medicine name was NOT found in the registered pharmacy database. It may be counterfeit, from an unregistered source, or the Batch ID may be incorrect.",
                "medicine": None
            })

        days = item['Days_to_Expiry']
        if days <= 0:
            expiry_status = "EXPIRED"
            verdict = "AUTHENTIC — EXPIRED"
            verdict_color = "red"
            message = f"This medicine WAS dispensed by a registered pharmacy but has EXPIRED. Do not consume it. Dispose of it safely."
        elif days <= threshold:
            expiry_status = "NEAR_EXPIRY"
            verdict = "AUTHENTIC — NEAR EXPIRY"
            verdict_color = "orange"
            message = f"This medicine is authentic but expires in only {days} day(s). Use with caution and consult your pharmacist."
        else:
            expiry_status = "VALID"
            verdict = "AUTHENTIC — VALID"
            verdict_color = "green"
            message = f"This medicine is authentic and has {days} days remaining before expiry. It is safe to use as directed."

        log_event(username, 'Medicine Verification', f"Verified {item['Medicine_Name']} ({item['Batch_ID']}). Result: {verdict}.")

        return jsonify({
            "authentic": True,
            "found": True,
            "expiry_status": expiry_status,
            "verdict": verdict,
            "verdict_color": verdict_color,
            "message": message,
            "medicine": {
                "batch_id": item['Batch_ID'],
                "name": item['Medicine_Name'],
                "category": item['Category'],
                "manufacturer": item['Manufacturer'],
                "manufacturing_date": item['Manufacturing_Date'],
                "expiry_date": item['Expiry_Date'],
                "days_to_expiry": days,
                "risk_level": item['Expiry_Risk_Level'],
                "quantity_in_stock": item['Quantity_In_Stock'],
                "ai_recommendation": item['AI_Recommendation']
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ─── USER SELF-REGISTRATION ────────────────────────────────────────────
@app.route('/api/register/user', methods=['POST'])
def register_public_user():
    try:
        data = request.get_json() or {}
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        full_name = data.get('full_name', '').strip()

        if not username or not password:
            return jsonify({"success": False, "message": "Username and password are required."}), 400

        if len(password) < 6:
            return jsonify({"success": False, "message": "Password must be at least 6 characters."}), 400

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM users WHERE username = ?", (username,))
        if cursor.fetchone():
            conn.close()
            return jsonify({"success": False, "message": "Username already exists. Please choose another."}), 400

        cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (username, password, 'user'))
        conn.commit()
        conn.close()

        log_event(username, 'User Registration', f"New patient account registered: {username} ({full_name}).")
        return jsonify({"success": True, "username": username, "role": "user"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# Required by Vercel
if __name__ == '__main__':
    from waitress import serve
    print("MedAI GH - Production Server Active")
    print("Local URL: http://localhost:5000")
    serve(app, host='0.0.0.0', port=5000, threads=8)
