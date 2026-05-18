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
        db = get_db()
        status = "connected" if db else "offline"
        self._respond(200, {"status": "ok", "db": status})

    def _respond(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass
