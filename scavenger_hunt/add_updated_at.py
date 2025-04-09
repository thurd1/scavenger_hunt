#!/usr/bin/env python
import os
import sqlite3
import sys

def main():
    # Check if the script is being run from the correct directory
    if not os.path.exists('db.sqlite3'):
        print("Error: db.sqlite3 not found in current directory.")
        print("Please run this script from the directory containing the database file.")
        sys.exit(1)

    # Connect to the SQLite database
    try:
        conn = sqlite3.connect('db.sqlite3')
        cursor = conn.cursor()
        
        # Check if hunt_lobby table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='hunt_lobby'")
        if not cursor.fetchone():
            print("Error: hunt_lobby table does not exist.")
            conn.close()
            sys.exit(1)

        # Check if the updated_at column already exists in hunt_lobby
        cursor.execute("PRAGMA table_info(hunt_lobby)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'updated_at' not in columns:
            print("Adding updated_at column to hunt_lobby table...")
            # Add the missing column
            cursor.execute("ALTER TABLE hunt_lobby ADD COLUMN updated_at DATETIME DEFAULT NULL")
            conn.commit()
            print("Column added successfully.")
        else:
            print("Column 'updated_at' already exists in hunt_lobby.")

        # Also check for last_accessed column which might be related
        if 'last_accessed' not in columns:
            print("Adding last_accessed column to hunt_lobby table...")
            # Add the missing column
            cursor.execute("ALTER TABLE hunt_lobby ADD COLUMN last_accessed DATETIME DEFAULT NULL")
            conn.commit()
            print("Column added successfully.")
        else:
            print("Column 'last_accessed' already exists in hunt_lobby.")
            
        print("Database update complete.")
        
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
        sys.exit(1)
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    main() 