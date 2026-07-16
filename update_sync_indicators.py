import os
import glob

public_dir = os.path.join(os.path.dirname(__file__), 'public')
html_files = glob.glob(os.path.join(public_dir, '*.html'))

live_str = '<div class="sync-indicator"><i class="fa-solid fa-circle"></i> Live</div>'
offline_str = '<div class="sync-indicator"><i class="fa-solid fa-circle"></i> Offline Mode</div>'

old_sync_header = """                <div class="sync-indicator">
                    <i class="fa-solid fa-circle"></i>
                    <span>Clinical Data Sync: Active</span>
                </div>"""

new_sync_header = """                <div class="sync-indicator">
                    <i class="fa-solid fa-circle"></i>
                    <span>Local Database: Active (Air-Gapped)</span>
                </div>"""

for file_path in html_files:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    new_content = content.replace(live_str, offline_str)
    new_content = new_content.replace(old_sync_header, new_sync_header)
    
    if new_content != content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated sync indicator in {os.path.basename(file_path)}")

print("Done updating sync indicators.")
