import os

html_dir = 'public'
files = [f for f in os.listdir(html_dir) if f.endswith('.html')]

replacements = {
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css': '/vendor/css/all.min.css',
    'https://cdn.jsdelivr.net/npm/jsbarcode@3.11.5/dist/JsBarcode.all.min.js': '/vendor/js/JsBarcode.all.min.js',
    'https://cdn.jsdelivr.net/npm/chart.js': '/vendor/js/chart.js',
    'https://ui-avatars.com/api/?name=Admin+User&background=0D8ABC&color=fff': 'data:image/svg+xml;utf8,<svg xmlns=\'http://www.w3.org/2000/svg\' width=\'100\' height=\'100\' viewBox=\'0 0 100 100\'><rect width=\'100\' height=\'100\' fill=\'%230D8ABC\'/><text x=\'50%\' y=\'54%\' font-family=\'sans-serif\' font-weight=\'bold\' font-size=\'38\' fill=\'%23ffffff\' dominant-baseline=\'middle\' text-anchor=\'middle\'>U</text></svg>'
}

print("Starting HTML asset path updates...")
for filename in files:
    filepath = os.path.join(html_dir, filename)
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        modified = False
        for old, new in replacements.items():
            if old in content:
                content = content.replace(old, new)
                modified = True
                
        if modified:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Updated {filename}")
        else:
            print(f"No updates required for {filename}")
    except Exception as e:
        print(f"Error processing {filename}: {e}")
print("HTML asset path updates complete.")
