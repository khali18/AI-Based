from api.index import app
import os

if __name__ == '__main__':
    from waitress import serve
    print("-----------------------------------------------")
    print("MedAI GH - LOCAL DEVELOPMENT WRAPPER")
    print("Directing traffic to api/index.py")
    print("Local URL: http://localhost:5000")
    print("-----------------------------------------------")
    serve(app, host='0.0.0.0', port=5000, threads=8)
