import os
import csv
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
MONGO_URI = os.getenv('MONGO_URI') or "mongodb+srv://sheripha2_db_user:Admin123@cluster0.xpjpg6o.mongodb.net/medai_gh?retryWrites=true&w=majority&appName=Cluster0"

try:
    print(f"Connecting to database with URI...")
    client = MongoClient(MONGO_URI)
    db = client.get_database("medai_gh")
    print("Successfully connected to database:", db.name)
    
    # 1. Seed Inventory from CSV
    inventory_col = db["inventory"]
    csv_file_path = "project dataset.csv"
    
    if os.path.exists(csv_file_path):
        print("Found project dataset.csv. Clearing and seeding inventory collection...")
        inventory_col.delete_many({}) # Clear existing inventory to seed the correct fresh project dataset
        
        records = []
        with open(csv_file_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    record = {
                        "Batch_ID": row["Batch_ID"].strip(),
                        "Medicine_Name": row["Medicine_Name"].strip(),
                        "Category": row["Category"].strip(),
                        "Manufacturer": row["Manufacturer"].strip(),
                        "Manufacturing_Date": row["Manufacturing_Date"].strip(),
                        "Expiry_Date": row["Expiry_Date"].strip(),
                        "Unit_Cost": float(row["Unit_Cost_USD"]) if row.get("Unit_Cost_USD") else 0.0,
                        "Unit_Cost_USD": float(row["Unit_Cost_USD"]) if row.get("Unit_Cost_USD") else 0.0,
                        "Selling_Price": float(row["Selling_Price_USD"]) if row.get("Selling_Price_USD") else 0.0,
                        "Selling_Price_USD": float(row["Selling_Price_USD"]) if row.get("Selling_Price_USD") else 0.0,
                        "Quantity_In_Stock": int(row["Quantity_In_Stock"]) if row.get("Quantity_In_Stock") else 0,
                        "Reorder_Level": int(row["Reorder_Level"]) if row.get("Reorder_Level") else 0,
                        "Sales_Last_30_Days": int(row["Sales_Last_30_Days"]) if row.get("Sales_Last_30_Days") else 0,
                        "Storage_Condition": row["Storage_Condition"].strip(),
                        "Days_to_Expiry": int(row["Days_to_Expiry"]) if row.get("Days_to_Expiry") else 0,
                        "Daily_Consumption_Rate": float(row["Daily_Consumption_Rate"]) if row.get("Daily_Consumption_Rate") else 0.0,
                        "ML_Predicted_Consumption": float(row["Daily_Consumption_Rate"]) if row.get("Daily_Consumption_Rate") else 0.0,
                        "Days_to_Exhaust_Stock": float(row["Days_to_Exhaust_Stock"]) if row.get("Days_to_Exhaust_Stock") else 0.0,
                        "ML_Predicted_Days_To_Exhaust": float(row["Days_to_Exhaust_Stock"]) if row.get("Days_to_Exhaust_Stock") else 0.0,
                        "Expiry_Risk_Level": row["Expiry_Risk_Level"].strip(),
                        "AI_Recommendation": row["AI_Recommendation"].strip()
                    }
                    records.append(record)
                except Exception as e:
                    print(f"Skipping row due to error: {e}, row values: {row}")
        
        if records:
            inventory_col.insert_many(records)
            print(f"Successfully seeded {len(records)} inventory records into MongoDB Atlas!")
    else:
        print("project dataset.csv not found, skipping inventory seed.")

    # 2. Seed Default Settings
    settings_col = db["settings"]
    if settings_col.count_documents({}) == 0:
        print("Seeding default system settings...")
        settings_col.insert_one({
            "system_name": "MedAI GH",
            "hospital_name": "Kumasi Technical University Clinic",
            "currency": "GH₵",
            "default_tax_rate": 0.0,
            "reorder_alert_threshold": 30,
            "expiry_alert_threshold": 90,
            "auto_backup": True,
            "backup_frequency": "Daily",
            "ml_model_version": "Random Forest Regressor v1.2",
            "last_training_date": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        })
        print("Default settings seeded!")
    else:
        print("System settings already initialized.")

except Exception as e:
    print("Database seeding failed:", e)
