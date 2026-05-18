import json
import os
import re
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

MONGO_URI = 'mongodb+srv://sheripha2_db_user:Admin123@cluster0.xpjpg6o.mongodb.net/medai_gh?retryWrites=true&w=majority&appName=Cluster0'

def get_db():
    if not MONGO_URI:
        return None, "MONGO_URI not set"
    try:
        from pymongo import MongoClient
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=8000,
                             connectTimeoutMS=8000, socketTimeoutMS=8000)
        return client.get_database(), None
    except ImportError:
        return None, "pymongo not installed"
    except Exception as e:
        return None, str(e)

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            db, err = get_db()
            if db is None:
                return self._respond(200, [])

            inv = db['inventory']
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            search = params.get('search', [''])[0].strip()

            if search:
                regex = re.compile(search, re.IGNORECASE)
                query = {"$or": [
                    {"Medicine_Name": regex},
                    {"Batch_ID": regex},
                    {"Category": regex}
                ]}
            else:
                query = {}

            items = list(inv.find(query, {"_id": 0}).limit(100))
            self._respond(200, items)
        except Exception as e:
            self._respond(500, {"error": str(e)})

    def _respond(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass
