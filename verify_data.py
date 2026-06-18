import urllib.request
import json

def test_route(url, name):
    try:
        response = urllib.request.urlopen(url)
        data = json.loads(response.read().decode('utf-8'))
        print(f"\n=== {name} ({url}) ===")
        if isinstance(data, list):
            print(f"Loaded {len(data)} items. First item:")
            if len(data) > 0:
                print(json.dumps(data[0], indent=2))
        else:
            print(json.dumps(data, indent=2))
    except Exception as e:
        print(f"Error calling {name}: {e}")

test_route("http://localhost:5000/api/dashboard", "Dashboard Metrics")
test_route("http://localhost:5000/api/inventory", "Inventory Items")
test_route("http://localhost:5000/api/forecast", "Forecasting Engine")
