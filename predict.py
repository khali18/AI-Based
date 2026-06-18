import sys
import os
import json
import joblib
import pandas as pd

# Load model and encoder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, 'model.pkl')
ENCODER_PATH = os.path.join(BASE_DIR, 'encoder.pkl')

def main():
    if len(sys.argv) < 4:
        print(json.dumps({"error": "Missing arguments. Usage: python predict.py <category> <unit_cost_usd> <sales_last_30_days>"}))
        sys.exit(1)
        
    category = sys.argv[1]
    try:
        unit_cost = float(sys.argv[2])
        sales_last_30 = int(sys.argv[3])
    except ValueError:
        print(json.dumps({"error": "Invalid numerical parameters."}))
        sys.exit(1)
        
    if not os.path.exists(MODEL_PATH) or not os.path.exists(ENCODER_PATH):
        # Fallback to simple calculation if model files don't exist
        rate = sales_last_30 / 30.0 if sales_last_30 > 0 else 0.1
        print(json.dumps({"predicted_rate": rate, "is_fallback": True}))
        return

    try:
        model = joblib.load(MODEL_PATH)
        category_encoder = joblib.load(ENCODER_PATH)
        
        # Safe transform category
        if category not in category_encoder.classes_:
            # Fallback to general or first class
            cat_encoded = category_encoder.transform([category_encoder.classes_[0]])[0]
        else:
            cat_encoded = category_encoder.transform([category])[0]
            
        X = pd.DataFrame([[unit_cost, cat_encoded, sales_last_30]], 
                         columns=['Unit_Cost_USD', 'Category_Encoded', 'Sales_Last_30_Days'])
        prediction = model.predict(X)[0]
        
        print(json.dumps({
            "predicted_rate": float(prediction),
            "is_fallback": False
        }))
    except Exception as e:
        rate = sales_last_30 / 30.0 if sales_last_30 > 0 else 0.1
        print(json.dumps({"predicted_rate": rate, "is_fallback": True, "error": str(e)}))

if __name__ == '__main__':
    main()
