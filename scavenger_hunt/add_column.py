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
        
        # Check if hunt_teamanswer table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='hunt_teamanswer'")
        if not cursor.fetchone():
            print("Error: hunt_teamanswer table does not exist.")
            conn.close()
            sys.exit(1)
            
        # Check if hunt_teamraceprogress table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='hunt_teamraceprogress'")
        if not cursor.fetchone():
            print("Error: hunt_teamraceprogress table does not exist.")
            conn.close()
            sys.exit(1)

        # Check if the photo_uploaded column already exists in hunt_teamanswer
        cursor.execute("PRAGMA table_info(hunt_teamanswer)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'photo_uploaded' not in columns:
            print("Adding photo_uploaded column to hunt_teamanswer table...")
            # Add the missing column
            cursor.execute("ALTER TABLE hunt_teamanswer ADD COLUMN photo_uploaded BOOLEAN DEFAULT 0")
            conn.commit()
            print("Column added successfully.")
        else:
            print("Column 'photo_uploaded' already exists in hunt_teamanswer.")

        # Check if the photo_questions_completed column exists in the TeamRaceProgress table
        cursor.execute("PRAGMA table_info(hunt_teamraceprogress)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'photo_questions_completed' not in columns:
            print("Adding photo_questions_completed column to hunt_teamraceprogress table...")
            # Add the missing column
            cursor.execute("ALTER TABLE hunt_teamraceprogress ADD COLUMN photo_questions_completed TEXT DEFAULT NULL")
            conn.commit()
            print("Column added successfully.")
        else:
            print("Column 'photo_questions_completed' already exists in hunt_teamraceprogress.")

        # Check if TeamAnswer model exists but the photo_uploaded column is missing
        print("Database update complete.")
        
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
        sys.exit(1)
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    main() 