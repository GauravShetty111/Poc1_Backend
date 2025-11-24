import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# PostgreSQL connection for file storage
def get_postgres_connection():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
        database=os.getenv("POSTGRES_DB", "filestore"),
        user=os.getenv("POSTGRES_USER", "fileuser"),
        password=os.getenv("POSTGRES_PASSWORD", "password123"),
        port=os.getenv("POSTGRES_PORT", "5432")
    )

def init_file_storage():
    """Initialize file storage tables"""
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                filename VARCHAR(255) NOT NULL,
                original_name VARCHAR(255) NOT NULL,
                file_data BYTEA NOT NULL,
                file_size BIGINT NOT NULL,
                mime_type VARCHAR(100),
                uploaded_at TIMESTAMP DEFAULT NOW()
            );
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS csv_files (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                table_name VARCHAR(255) NOT NULL,
                filename VARCHAR(255) NOT NULL,
                file_data BYTEA NOT NULL,
                metadata JSONB NOT NULL,
                uploaded_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(user_id, table_name)
            );
        """)
        
        conn.commit()
        cur.close()
        conn.close()
        print("File storage tables initialized successfully")
    except Exception as e:
        print(f"Warning: Could not initialize file storage tables: {e}")
        print("Run: psql -U postgres -d filestore -c 'GRANT CREATE ON SCHEMA public TO fileuser;'")
        raise