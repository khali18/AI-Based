from api.index import app
import os
import socket

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

if __name__ == '__main__':
    from waitress import serve
    local_ip = get_local_ip()
    print("-----------------------------------------------")
    print("MedAI GH - LOCAL DEVELOPMENT WRAPPER")
    print("Directing traffic to api/index.py")
    print(f"Local URL:  http://localhost:5000")
    print(f"Mobile URL: http://{local_ip}:5000")
    print("-----------------------------------------------")
    serve(app, host='0.0.0.0', port=5000, threads=8)
