import os
import csv
import sqlite3
from datetime import datetime

def init_db():
    print("Initializing SQLite database 'medai.db'...")
    conn = sqlite3.connect('medai.db')
    cursor = conn.cursor()
    
    # 1. Users
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT,
        role TEXT,
        profile_pic TEXT
    )''')
    
    # 2. Inventory
    cursor.execute('''CREATE TABLE IF NOT EXISTS inventory (
        Batch_ID TEXT PRIMARY KEY,
        Medicine_Name TEXT,
        Category TEXT,
        Manufacturer TEXT,
        Manufacturing_Date TEXT,
        Quantity_In_Stock INTEGER,
        Reorder_Level INTEGER,
        Unit_Cost_USD REAL,
        Selling_Price_USD REAL,
        Days_to_Expiry INTEGER,
        Expiry_Date TEXT,
        Sales_Last_30_Days INTEGER,
        Daily_Consumption_Rate REAL,
        ML_Predicted_Consumption REAL,
        ML_Predicted_Days_To_Exhaust INTEGER,
        Expiry_Risk_Level TEXT,
        AI_Recommendation TEXT
    )''')
    
    # 3. Settings
    cursor.execute('''CREATE TABLE IF NOT EXISTS settings (
        id INTEGER PRIMARY KEY,
        hospital_name TEXT,
        nhis_id TEXT,
        expiry_threshold INTEGER,
        currency TEXT,
        exchange_rate REAL,
        system_name TEXT,
        default_tax_rate REAL,
        reorder_alert_threshold INTEGER,
        expiry_alert_threshold INTEGER,
        auto_backup BOOLEAN,
        backup_frequency TEXT,
        ml_model_version TEXT,
        last_training_date TEXT
    )''')
    
    # 4. Audit
    cursor.execute('''CREATE TABLE IF NOT EXISTS audit (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        username TEXT,
        event TEXT,
        details TEXT,
        metadata TEXT
    )''')
    
    # 5. Sales
    cursor.execute('''CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        pharmacist TEXT,
        customer_name TEXT,
        items INTEGER,
        total_ghs REAL,
        details TEXT
    )''')

    # 6. Refunds
    cursor.execute('''CREATE TABLE IF NOT EXISTS refunds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pharmacist_username TEXT,
        medicine_name TEXT,
        amount REAL,
        reason TEXT,
        status TEXT,
        timestamp TEXT
    )''')

    # Insert default users if empty
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", ("sheripha", "admin123", "admin"))
        cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", ("pharm", "pharm123", "pharmacist"))
        print("Default users seeded.")

    # Seed Inventory from CSV
    csv_file_path = "project dataset.csv"
    if os.path.exists(csv_file_path):
        cursor.execute("SELECT COUNT(*) FROM inventory")
        if cursor.fetchone()[0] == 0:
            print("Found project dataset.csv. Seeding inventory collection...")
            records = []
            with open(csv_file_path, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        record = (
                            row["Batch_ID"].strip(),
                            row["Medicine_Name"].strip(),
                            row["Category"].strip(),
                            row["Manufacturer"].strip(),
                            row["Manufacturing_Date"].strip(),
                            int(row["Quantity_In_Stock"]) if row.get("Quantity_In_Stock") else 0,
                            int(row["Reorder_Level"]) if row.get("Reorder_Level") else 0,
                            float(row["Unit_Cost_USD"]) if row.get("Unit_Cost_USD") else 0.0,
                            float(row["Selling_Price_USD"]) if row.get("Selling_Price_USD") else 0.0,
                            int(row["Days_to_Expiry"]) if row.get("Days_to_Expiry") else 0,
                            row["Expiry_Date"].strip(),
                            int(row["Sales_Last_30_Days"]) if row.get("Sales_Last_30_Days") else 0,
                            float(row["Daily_Consumption_Rate"]) if row.get("Daily_Consumption_Rate") else 0.0,
                            float(row["Daily_Consumption_Rate"]) if row.get("Daily_Consumption_Rate") else 0.0,
                            int(float(row["Days_to_Exhaust_Stock"])) if row.get("Days_to_Exhaust_Stock") and row.get("Days_to_Exhaust_Stock") != 'Unlimited' else 999,
                            row["Expiry_Risk_Level"].strip(),
                            row["AI_Recommendation"].strip()
                        )
                        records.append(record)
                    except Exception as e:
                        print(f"Skipping row due to error: {e}")
            
            if records:
                cursor.executemany('''
                    INSERT INTO inventory 
                    (Batch_ID, Medicine_Name, Category, Manufacturer, Manufacturing_Date, Quantity_In_Stock, Reorder_Level, 
                    Unit_Cost_USD, Selling_Price_USD, Days_to_Expiry, Expiry_Date, Sales_Last_30_Days, 
                    Daily_Consumption_Rate, ML_Predicted_Consumption, ML_Predicted_Days_To_Exhaust, Expiry_Risk_Level, AI_Recommendation)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', records)
                print(f"Successfully seeded {len(records)} inventory records into medai.db!")
    else:
        print("project dataset.csv not found, skipping inventory seed.")

    # Seed Default Settings
    cursor.execute("SELECT COUNT(*) FROM settings")
    if cursor.fetchone()[0] == 0:
        print("Seeding default system settings...")
        cursor.execute('''
            INSERT INTO settings (id, system_name, hospital_name, currency, default_tax_rate, 
            reorder_alert_threshold, expiry_alert_threshold, auto_backup, backup_frequency, 
            ml_model_version, last_training_date, expiry_threshold, exchange_rate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (1, "MedAI GH", "Kumasi Technical University Clinic", "GH₵", 0.0, 30, 90, True, "Daily", "Random Forest Regressor v1.2", datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), 30, 1.0))
        print("Default settings seeded!")
    else:
        print("System settings already initialized.")

    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
