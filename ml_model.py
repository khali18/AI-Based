import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder
import joblib
import json
import os
import math
import datetime

class PharmacyIntelligenceLayer:
    def __init__(self, inventory_collection=None, data_path='project dataset.csv'):
        self.data_path = data_path
        self.inventory_collection = inventory_collection
        self.model = RandomForestRegressor(n_estimators=100, random_state=42)
        self.category_encoder = LabelEncoder()
        self.categories_ = []
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        self.MODEL_PATH = os.path.join(BASE_DIR, 'model.pkl')
        self.ENCODER_PATH = os.path.join(BASE_DIR, 'encoder.pkl')
        
    def train_demand_forecast_model(self):
        """
        Trains the model and SAVES it to disk for production use.
        """
        print("Training Demand Forecasting Model (Random Forest)...")
        if not os.path.exists(self.data_path):
            return None
            
        df = pd.read_csv(self.data_path)
        self.categories_ = df['Category'].unique().tolist()
        df['Category_Encoded'] = self.category_encoder.fit_transform(df['Category'])
        
        X = df[['Unit_Cost_USD', 'Category_Encoded', 'Sales_Last_30_Days']]
        y = df['Daily_Consumption_Rate']
        
        self.model.fit(X, y)
        
        # Save for Vercel/Production
        joblib.dump(self.model, self.MODEL_PATH)
        joblib.dump(self.category_encoder, self.ENCODER_PATH)
        print("Model and Encoder saved to disk.")
        return df

    def load_model(self):
        """
        Loads pre-trained model from disk (Critical for Vercel).
        """
        if os.path.exists(self.MODEL_PATH) and os.path.exists(self.ENCODER_PATH):
            self.model = joblib.load(self.MODEL_PATH)
            self.category_encoder = joblib.load(self.ENCODER_PATH)
            self.categories_ = self.category_encoder.classes_.tolist()
            print("Pre-trained Model loaded successfully.")
            return True
        return False

    def predict_single(self, category, unit_cost, sales_last_30):
        try:
            if category not in self.categories_:
                category = self.categories_[0] if self.categories_ else 'General'
            
            cat_encoded = self.category_encoder.transform([category])[0]
            X = pd.DataFrame([[unit_cost, cat_encoded, sales_last_30]], 
                             columns=['Unit_Cost_USD', 'Category_Encoded', 'Sales_Last_30_Days'])
            prediction = self.model.predict(X)[0]
            return float(prediction)
        except Exception as e:
            return sales_last_30 / 30.0 if sales_last_30 > 0 else 1.0
        
    def automated_expiry_risk_classifier(self, pred_days_to_exhaust, days_to_expiry):
        if pd.isna(days_to_expiry): return "Low Risk"
        if pred_days_to_exhaust == 'Unlimited':
            return "High Risk" if days_to_expiry < 90 else "Medium Risk"
        if pred_days_to_exhaust > days_to_expiry: return "High Risk"
        elif (pred_days_to_exhaust + 30) > days_to_expiry: return "Medium Risk"
        return "Low Risk"
        
    def seed_database_and_predict(self, df):
        if df is None or self.inventory_collection is None: return
        
        # Check if already seeded to prevent duplicate operations in Serverless
        if self.inventory_collection.count_documents({}) > 500:
            print("Database already contains records. Skipping re-seed.")
            return

        print("Seeding initial dataset into MongoDB...")
        features = df[['Unit_Cost_USD', 'Category_Encoded', 'Sales_Last_30_Days']]
        predictions = self.model.predict(features)
        
        documents = []
        for index, row in df.iterrows():
            pred_consumption = predictions[index]
            pred_days_to_exhaust = math.floor(row['Quantity_In_Stock'] / pred_consumption) if pred_consumption > 0 else 'Unlimited'
            if isinstance(pred_days_to_exhaust, int) and pred_days_to_exhaust > 36500: pred_days_to_exhaust = 'Unlimited'
                
            risk_level = self.automated_expiry_risk_classifier(pred_days_to_exhaust, row['Days_to_Expiry'])
            expiry_date_str = (datetime.datetime.now() + datetime.timedelta(days=int(row['Days_to_Expiry']))).strftime('%Y-%m-%d')

            documents.append({
                "Batch_ID": str(row['Batch_ID']),
                "Medicine_Name": str(row['Medicine_Name']),
                "Category": str(row['Category']),
                "Manufacturer": str(row['Manufacturer']),
                "Manufacturing_Date": str(row['Manufacturing_Date']),
                "Quantity_In_Stock": int(row['Quantity_In_Stock']),
                "Unit_Cost_USD": float(row['Unit_Cost_USD']),
                "Selling_Price_USD": float(row['Selling_Price_USD']),
                "Reorder_Level": int(row['Reorder_Level']),
                "Sales_Last_30_Days": int(row['Sales_Last_30_Days']),
                "Days_to_Expiry": int(row['Days_to_Expiry']),
                "Expiry_Date": expiry_date_str,
                "ML_Predicted_Consumption": round(float(pred_consumption), 2),
                "ML_Predicted_Days_To_Exhaust": pred_days_to_exhaust,
                "Expiry_Risk_Level": risk_level,
                "AI_Recommendation": str(row['AI_Recommendation'])
            })
            
        self.inventory_collection.insert_many(documents)
        print(f"Seeding complete. {len(documents)} records indexed.")
