from db.postgres_connect import get_postgres_connection
from psycopg2 import Binary
from fastapi import HTTPException
import uuid
import json
from datetime import datetime, timezone

class FileService:
    @staticmethod
    def store_file(user_id: int, filename: str, file_data: bytes, mime_type: str):
        try:
            conn = get_postgres_connection()
            cur = conn.cursor()
            
            unique_filename = f"{uuid.uuid4()}_{filename}"
            
            cur.execute("""
                INSERT INTO files (user_id, filename, original_name, file_data, file_size, mime_type) 
                VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
            """, (user_id, unique_filename, filename, Binary(file_data), len(file_data), mime_type))
            
            file_id = cur.fetchone()[0]
            conn.commit()
            cur.close()
            conn.close()
            
            return {"file_id": file_id, "filename": unique_filename}
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to store file: {str(e)}")
    
    @staticmethod
    def get_file(file_id: int, user_id: int):
        try:
            conn = get_postgres_connection()
            cur = conn.cursor()
            
            cur.execute("""
                SELECT filename, original_name, file_data, mime_type, file_size 
                FROM files WHERE id = %s AND user_id = %s
            """, (file_id, user_id))
            
            result = cur.fetchone()
            cur.close()
            conn.close()
            
            if not result:
                raise HTTPException(status_code=404, detail="File not found")
            
            return {
                "filename": result[0],
                "original_name": result[1],
                "file_data": bytes(result[2]),
                "mime_type": result[3],
                "file_size": result[4]
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to retrieve file: {str(e)}")
    
    @staticmethod
    def list_user_files(user_id: int):
        try:
            conn = get_postgres_connection()
            cur = conn.cursor()
            
            cur.execute("""
                SELECT id, original_name, file_size, mime_type, uploaded_at 
                FROM files WHERE user_id = %s ORDER BY uploaded_at DESC
            """, (user_id,))
            
            files = cur.fetchall()
            cur.close()
            conn.close()
            
            return [
                {
                    "file_id": file[0],
                    "filename": file[1],
                    "file_size": file[2],
                    "mime_type": file[3],
                    "uploaded_at": file[4]
                }
                for file in files
            ]
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")

    @staticmethod
    def store_csv_file(user_id: int, table_name: str, column_names: str, filename: str, file_data: bytes):
        try:
            conn = get_postgres_connection()
            cur = conn.cursor()
            
            metadata = {
                "table_name": table_name,
                "column_names": column_names,
                "filename": filename,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            
            cur.execute("""
                INSERT INTO csv_files (user_id, table_name, filename, file_data, metadata) 
                VALUES (%s, %s, %s, %s, %s) RETURNING id
            """, (user_id, table_name, filename, Binary(file_data), json.dumps(metadata)))
            
            file_id = cur.fetchone()[0]
            conn.commit()
            cur.close()
            conn.close()
            
            return {"file_id": file_id}
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to store CSV file: {str(e)}")

    @staticmethod
    def get_csv_file(table_name: str, user_id: int):
        try:
            conn = get_postgres_connection()
            cur = conn.cursor()
            
            cur.execute("""
                SELECT file_data, metadata FROM csv_files 
                WHERE table_name = %s AND user_id = %s
            """, (table_name, user_id))
            
            result = cur.fetchone()
            cur.close()
            conn.close()
            
            if not result:
                raise HTTPException(status_code=404, detail="CSV file not found")
            
            metadata = json.loads(result[1])
            
            return {
                "file_data": bytes(result[0]),
                "column_names": metadata["column_names"]
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to retrieve CSV file: {str(e)}")