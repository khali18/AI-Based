import json
import os
from http.server import BaseHTTPRequestHandler

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
        db, err = get_db()
        self._respond(200, {"status": "ok", "db": "connected" if db else "offline", "error": err})

    def _respond(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass
