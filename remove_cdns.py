import os
import glob

public_dir = os.path.join(os.path.dirname(__file__), 'public')
html_files = glob.glob(os.path.join(public_dir, '*.html'))

font_str = '<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">'
avatar_str = 'https://ui-avatars.com/api/?name=Pharm+Staff&background=10b981&color=fff'
local_avatar_str = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='100' height='100' viewBox='0 0 100 100'><rect width='100' height='100' fill='%230D8ABC'/><text x='50%' y='54%' font-family='sans-serif' font-weight='bold' font-size='38' fill='%23ffffff' dominant-baseline='middle' text-anchor='middle'>U</text></svg>"

for file_path in html_files:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    new_content = content.replace(font_str, '<!-- Offline Mode: Google Fonts Disabled -->')
    new_content = new_content.replace(avatar_str, local_avatar_str)
    
    if new_content != content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated {os.path.basename(file_path)}")

print("Done removing external CDNs.")
