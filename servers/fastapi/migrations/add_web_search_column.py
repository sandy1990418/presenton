"""
Add web_search_enabled column to presentationmodel table
"""
import sqlite3
import os


def add_web_search_column():
    """Add web_search_enabled column to presentationmodel table if it doesn't exist"""
    
    # Get database path - try common locations
    possible_paths = [
        "/tmp/presenton/fastapi.db",
        os.path.join(os.environ.get("APP_DATA_DIRECTORY", "/tmp/presenton"), "fastapi.db")
    ]
    
    db_path = None
    for path in possible_paths:
        if os.path.exists(path):
            db_path = path
            break
    
    if db_path is None:
        print("Database file not found in any common location")
        return
    
    try:
        # Connect to SQLite database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if column exists
        cursor.execute("PRAGMA table_info(presentationmodel)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'web_search_enabled' not in columns:
            print("Adding web_search_enabled column to presentationmodel table...")
            cursor.execute(
                "ALTER TABLE presentationmodel ADD COLUMN web_search_enabled BOOLEAN DEFAULT 0"
            )
            conn.commit()
            print("✅ Successfully added web_search_enabled column")
        else:
            print("web_search_enabled column already exists")
        
        conn.close()
        
    except Exception as e:
        print(f"Error adding column: {e}")
        if 'conn' in locals():
            conn.close()


if __name__ == "__main__":
    add_web_search_column()