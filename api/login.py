import json
import os
from http.server import BaseHTTPRequestHandler

MONGO_URI = 'mongodb+srv://sheripha2_db_user:Admin123@cluster0.xpjpg6o.mongodb.net/medai_gh?retryWrites=true&w=majority&appName=Cluster0'

def get_db():
    if not MONGO_URI:
        return None, "MONGO_URI environment variable not set in Vercel dashboard"
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
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            data = json.loads(body) if body else {}

            db, err = get_db()
            if db is None:
                return self._respond(500, {"success": False, "error": err or "DB Offline"})

            users = db['users']

            # Seed default admin if empty
            if users.count_documents({}) == 0:
                users.insert_one({"username": "sheripha", "password": "admin123", "role": "admin"})

            username = data.get('username', '').strip()
            password = data.get('password', '').strip()

            user = users.find_one({"username": username, "password": password})
            if user:
                return self._respond(200, {
                    "success": True,
                    "role": user.get('role', 'pharmacist'),
                    "username": user.get('username')
                })
            return self._respond(401, {"success": False, "message": "Invalid credentials"})
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
