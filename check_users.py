import sqlite3

def check_users():
    print("Users in SQLite database:")
    try:
        conn = sqlite3.connect('medai.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users")
        users = cursor.fetchall()
        for user in users:
            print(f"Username: {user['username']}, Role: {user['role']}")
        conn.close()
    except Exception as e:
        print("Error reading database:", e)

if __name__ == '__main__':
    check_users()
