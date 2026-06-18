import urllib.request
import json
import urllib.error

req = urllib.request.Request(
    'https://ai-based-eosin.vercel.app/api/login',
    data=json.dumps({'username':'sheripha', 'password':'password123'}).encode(),
    headers={'Content-Type': 'application/json'}
)

try:
    print(urllib.request.urlopen(req).read().decode())
except urllib.error.HTTPError as e:
    print('Error Body:', e.read().decode())
except Exception as e:
    print('Error:', str(e))
