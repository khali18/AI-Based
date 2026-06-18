import os
import urllib.request

# Define paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VENDOR_DIR = os.path.join(BASE_DIR, 'public', 'vendor')
CSS_DIR = os.path.join(VENDOR_DIR, 'css')
JS_DIR = os.path.join(VENDOR_DIR, 'js')
FONTS_DIR = os.path.join(VENDOR_DIR, 'webfonts')

# Create directories
os.makedirs(CSS_DIR, exist_ok=True)
os.makedirs(JS_DIR, exist_ok=True)
os.makedirs(FONTS_DIR, exist_ok=True)

# Download list
downloads = {
    "https://cdn.jsdelivr.net/npm/chart.js": os.path.join(JS_DIR, 'chart.js'),
    "https://cdn.jsdelivr.net/npm/jsbarcode@3.11.5/dist/JsBarcode.all.min.js": os.path.join(JS_DIR, 'JsBarcode.all.min.js'),
    "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css": os.path.join(CSS_DIR, 'all.min.css'),
    "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/webfonts/fa-solid-900.woff2": os.path.join(FONTS_DIR, 'fa-solid-900.woff2'),
    "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/webfonts/fa-brands-400.woff2": os.path.join(FONTS_DIR, 'fa-brands-400.woff2'),
    "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/webfonts/fa-regular-400.woff2": os.path.join(FONTS_DIR, 'fa-regular-400.woff2'),
}

headers = {'User-Agent': 'Mozilla/5.0'}

print("Starting asset localization downloads...")
for url, path in downloads.items():
    print(f"Downloading {url} to {path}...")
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            with open(path, 'wb') as f:
                f.write(response.read())
        print("Success!")
    except Exception as e:
        print(f"Failed to download {url}: {e}")
print("Finished download process.")
