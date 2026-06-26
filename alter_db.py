import sqlite3
try:
    conn = sqlite3.connect('medai.db')
    cursor = conn.cursor()
    cursor.execute("ALTER TABLE refunds ADD COLUMN medicine_name TEXT")
    conn.commit()
    print("Successfully added medicine_name to refunds table.")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("Column already exists.")
    else:
        print("Error:", e)
finally:
    conn.close()
