import os
import glob

html_files = glob.glob('public/*.html')

insertion = '            <li><a href="/refunds.html"><i class="fa-solid fa-money-bill-transfer"></i> Refunds</a></li>\n'

for file in html_files:
    if file.endswith('login.html'):
        continue
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if 'refunds.html' in content:
        continue
        
    # Find settings link and insert before it
    search_str = '            <li class="admin-only"><a href="/settings.html">'
    if search_str in content:
        content = content.replace(search_str, insertion + search_str)
        with open(file, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated {file}")
    else:
        print(f"Could not find anchor in {file}")
