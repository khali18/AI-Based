import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder
import json
import os
import math
import datetime

class PharmacyIntelligenceLayer:
    def __init__(self, inventory_collection, data_path='project dataset.csv'):
        self.data_path = data_path
        self.inventory_collection = inventory_collection
        self.model = RandomForestRegressor(n_estimators=100, random_state=42)
        self.category_encoder = LabelEncoder()
        self.categories_ = []
        
    def train_demand_forecast_model(self):
        """
        Trains a Random Forest Regressor to predict Daily_Consumption_Rate 
        based on cost, category, and historical sales.
        """
        print("Training Demand Forecasting Model (Random Forest)...")
        if not os.path.exists(self.data_path):
            print(f"Warning: {self.data_path} not found. Skipping training.")
            return None
            
        df = pd.read_csv(self.data_path)
        
        # Prepare features
        self.categories_ = df['Category'].unique().tolist()
        df['Category_Encoded'] = self.category_encoder.fit_transform(df['Category'])
        
        X = df[['Unit_Cost_USD', 'Category_Encoded', 'Sales_Last_30_Days']]
        y = df['Daily_Consumption_Rate']
        
        self.model.fit(X, y)
        print(f"Model trained on {len(df)} records. Model R^2 Score:", self.model.score(X, y))
        return df

    def predict_single(self, category, unit_cost, sales_last_30):
        """
        Predicts Daily_Consumption_Rate for a single item using the trained model.
        """
        try:
            if category not in self.categories_:
                category = self.categories_[0] if self.categories_ else 'General'
            
            cat_encoded = self.category_encoder.transform([category])[0]
            X = pd.DataFrame([[unit_cost, cat_encoded, sales_last_30]], 
                             columns=['Unit_Cost_USD', 'Category_Encoded', 'Sales_Last_30_Days'])
            prediction = self.model.predict(X)[0]
            return float(prediction)
        except Exception as e:
            print(f"Prediction Error: {e}")
            return sales_last_30 / 30.0 if sales_last_30 > 0 else 1.0
        
    def automated_expiry_risk_classifier(self, pred_days_to_exhaust, days_to_expiry):
        """
        Smart classifier logic based on Probability of Utilization.
        Risk = (Current_Stock / Average_Daily_Sales) > Days_to_Expiry
        """
        if pd.isna(days_to_expiry):
            return "Low Risk"
            
        if pred_days_to_exhaust == 'Unlimited':
            if days_to_expiry < 90:
                return "High Risk"
            return "Medium Risk"
            
        if pred_days_to_exhaust > days_to_expiry:
            return "High Risk"
        elif (pred_days_to_exhaust + 30) > days_to_expiry:
            return "Medium Risk"
            
        return "Low Risk"
        
    def seed_database_and_predict(self, df):
        """
        Runs predictions on the entire dataset and seeds the MongoDB collection.
        """
        if df is None: return
        
        print("Preparing predictions and documents for seeding into MongoDB...")
        features = df[['Unit_Cost_USD', 'Category_Encoded', 'Sales_Last_30_Days']]
        predictions = self.model.predict(features)
        
        documents = []
        for index, row in df.iterrows():
            pred_consumption = predictions[index]
            
            if pred_consumption > 0:
                pred_days_to_exhaust = math.floor(row['Quantity_In_Stock'] / pred_consumption)
                if pred_days_to_exhaust > 36500:
                    pred_days_to_exhaust = 'Unlimited'
            else:
                pred_days_to_exhaust = 'Unlimited'
                
            risk_level = self.automated_expiry_risk_classifier(pred_days_to_exhaust, row['Days_to_Expiry'])
            expiry_date_obj = datetime.datetime.now() + datetime.timedelta(days=int(row['Days_to_Expiry']))
            expiry_date_str = expiry_date_obj.strftime('%Y-%m-%d')

            doc = {
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
                "ML_Predicted_Consumption": float(pred_consumption),
                "ML_Predicted_Days_To_Exhaust": pred_days_to_exhaust,
                "Expiry_Risk_Level": risk_level,
                "AI_Recommendation": str(row['AI_Recommendation'])
            }
            documents.append(doc)
            
        # MongoDB operations
        existing_count = self.inventory_collection.count_documents({})
        if existing_count > 0:
            print(f"MongoDB contains {existing_count} records. Purging and reseeding...")
            self.inventory_collection.delete_many({})
            
        self.inventory_collection.insert_many(documents)
        print(f"Seeding complete. {len(documents)} records indexed in MongoDB.")
