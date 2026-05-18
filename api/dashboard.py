import json
import os
from http.server import BaseHTTPRequestHandler
from pymongo import MongoClient

MONGO_URI = os.environ.get('MONGO_URI', '')

def get_db():
    if not MONGO_URI:
        return None
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=8000,
                             connectTimeoutMS=8000, socketTimeoutMS=8000)
        return client.get_database()
    except:
        return None

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            db = get_db()
            if db is None:
                return self._respond(500, {"success": False, "error": "DB Offline"})

            inv = db['inventory']
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

            return self._respond(200, {
                "totalItems": len(items),
                "totalStockValue": total_value,
                "todayRevenue": 0,
                "lowStockCount": low_stock,
                "expiredOrNearExpiryCount": expiry_risk,
                "riskCount": {
                    "High Risk": expiry_risk,
                    "Medium Risk": 0,
                    "Low Risk": max(0, len(items) - expiry_risk)
                }
            })
        except Exception as e:
            return self._respond(500, {"success": False, "error": str(e)})

    def _respond(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass
