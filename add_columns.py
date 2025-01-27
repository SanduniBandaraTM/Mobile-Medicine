import sqlite3

# Example Python script to modify the database
def get_db_connection():
    import sqlite3
    return sqlite3.connect('mobile_medicine.db')  # Replace with your actual database path

conn = get_db_connection()
cursor = conn.cursor()

# Add latitude and longitude columns to the users table
try:
    cursor.execute("ALTER TABLE users ADD COLUMN latitude REAL;")
    cursor.execute("ALTER TABLE users ADD COLUMN longitude REAL;")
    conn.commit()
    print("Columns added successfully.")
except sqlite3.OperationalError as e:
    print("Error:", e)
finally:
    conn.close()
