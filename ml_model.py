import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder
from tinydb import TinyDB
import json
import os
import math

import datetime

class PharmacyIntelligenceLayer:
    def __init__(self, db, data_path='project dataset.csv'):
        self.data_path = data_path
        self.db = db
        self.model = RandomForestRegressor(n_estimators=100, random_state=42)
        self.category_encoder = LabelEncoder()
        
    def train_demand_forecast_model(self):
        """
        Trains a Random Forest Regressor to predict Daily_Consumption_Rate 
        based on cost, category, and historical sales.
        This provides the predictive foresight for inventory needs.
        """
        print("Training Demand Forecasting Model (Random Forest)...")
        df = pd.read_csv(self.data_path)
        
        # Prepare features
        # encode categorical variables like Category
        self.categories_ = df['Category'].unique().tolist()
        df['Category_Encoded'] = self.category_encoder.fit_transform(df['Category'])
        
        X = df[['Unit_Cost_USD', 'Category_Encoded', 'Sales_Last_30_Days']]
        y = df['Daily_Consumption_Rate']
        
        self.model.fit(X, y)
        print(f"Model trained on {len(df)} records. Model R^2 Score:", self.model.score(X, y))
        
        # Return dataframe for database seeding
        return df
        
    def predict_single(self, category, unit_cost, sales_last_30):
        """
        Predicts Daily_Consumption_Rate for a single item.
        """
        try:
            # Handle unknown categories by falling back to 'General' or the first category
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
        Runs predictions on the entire dataset and seeds the TinyDB document NoSQL store.
        """
        print("Preparing predictions and documents for seeding...")
        features = df[['Unit_Cost_USD', 'Category_Encoded', 'Sales_Last_30_Days']]
        predictions = self.model.predict(features)
        
        documents = []
        for index, row in df.iterrows():
            pred_consumption = predictions[index]
            
            # Predict Days to exhaust based on predicted consumption
            if pred_consumption > 0:
                pred_days_to_exhaust = math.floor(row['Quantity_In_Stock'] / pred_consumption)
                # Cap to prevent JS Overflow (100 years max)
                if pred_days_to_exhaust > 36500:
                    pred_days_to_exhaust = 'Unlimited'
            else:
                pred_days_to_exhaust = 'Unlimited'
                
            risk_level = self.automated_expiry_risk_classifier(pred_days_to_exhaust, row['Days_to_Expiry'])
            
            # Calculate actual expiry date
            expiry_date_obj = datetime.datetime.now() + datetime.timedelta(days=int(row['Days_to_Expiry']))
            expiry_date_str = expiry_date_obj.isoformat()

            doc = {
                "Batch_ID": row['Batch_ID'],
                "Medicine_Name": row['Medicine_Name'],
                "Category": row['Category'],
                "Manufacturer": row['Manufacturer'],
                "Manufacturing_Date": row['Manufacturing_Date'],
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
                "AI_Recommendation": row['AI_Recommendation']
            }
            documents.append(doc)
            
        if len(self.db) > 0:
            print(f"TinyDB contains {len(self.db)} records. Purging and reseeding with fresh ML logic...")
            self.db.truncate()
            
        self.db.insert_multiple(documents)
        print(f"Seeding complete. {len(documents)} records indexed.")

if __name__ == "__main__":
    ai_db = TinyDB('database.json')
    ai_layer = PharmacyIntelligenceLayer(ai_db)
    df = ai_layer.train_demand_forecast_model()
    ai_layer.seed_database_and_predict(df)
