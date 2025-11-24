from fastapi import APIRouter, Depends, HTTPException
from db.postgres_connect import get_postgres_connection
from main import UserModel, get_current_user
import pandas as pd
import io
import json
from datetime import datetime, timedelta

router = APIRouter()

@router.get("/dashboard/overview")
async def get_dashboard_overview(current_user: UserModel = Depends(get_current_user)):
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()
        
        # Total files count
        cur.execute("SELECT COUNT(*) FROM files WHERE user_id = %s", (current_user.user_id,))
        total_files = cur.fetchone()[0]
        
        # Total file size
        cur.execute("SELECT COALESCE(SUM(file_size), 0) FROM files WHERE user_id = %s", (current_user.user_id,))
        total_size = cur.fetchone()[0]
        
        # Files uploaded today
        cur.execute("""
            SELECT COUNT(*) FROM files 
            WHERE user_id = %s AND DATE(uploaded_at) = CURRENT_DATE
        """, (current_user.user_id,))
        files_today = cur.fetchone()[0]
        
        # Files by type
        cur.execute("""
            SELECT mime_type, COUNT(*) FROM files 
            WHERE user_id = %s 
            GROUP BY mime_type
        """, (current_user.user_id,))
        files_by_type = dict(cur.fetchall())
        
        cur.close()
        conn.close()
        
        return {
            "total_files": total_files,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "files_today": files_today,
            "files_by_type": files_by_type
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/dashboard/recent-files")
async def get_recent_files(current_user: UserModel = Depends(get_current_user)):
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT id, original_name, file_size, mime_type, uploaded_at 
            FROM files WHERE user_id = %s 
            ORDER BY uploaded_at DESC LIMIT 10
        """, (current_user.user_id,))
        
        files = cur.fetchall()
        cur.close()
        conn.close()
        
        return {
            "recent_files": [
                {
                    "id": file[0],
                    "name": file[1],
                    "size_kb": round(file[2] / 1024, 2),
                    "type": file[3],
                    "uploaded_at": file[4]
                }
                for file in files
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/dashboard/file-analytics/{file_id}")
async def get_file_analytics(file_id: int, current_user: UserModel = Depends(get_current_user)):
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT file_data, mime_type, original_name FROM files 
            WHERE id = %s AND user_id = %s
        """, (file_id, current_user.user_id))
        
        result = cur.fetchone()
        cur.close()
        conn.close()
        
        if not result:
            raise HTTPException(status_code=404, detail="File not found")
        
        file_data, mime_type, original_name = result
        
        if not mime_type or 'csv' not in mime_type.lower():
            return {"error": "File is not a CSV", "filename": original_name}
        
        df = pd.read_csv(io.BytesIO(bytes(file_data)))
        
        # Basic stats
        total_rows = len(df)
        total_columns = len(df.columns)
        
        # Column analysis
        numeric_columns = df.select_dtypes(include=['number']).columns.tolist()
        text_columns = df.select_dtypes(include=['object']).columns.tolist()
        
        # Missing values
        missing_data = df.isnull().sum().to_dict()
        
        # Sample data
        sample_data = df.head(5).to_dict(orient="records")
        
        return {
            "filename": original_name,
            "total_rows": total_rows,
            "total_columns": total_columns,
            "numeric_columns": numeric_columns,
            "text_columns": text_columns,
            "missing_data": missing_data,
            "sample_data": sample_data,
            "columns": list(df.columns)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/dashboard/upload-trends")
async def get_upload_trends(current_user: UserModel = Depends(get_current_user)):
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()
        
        # Last 7 days upload trend
        cur.execute("""
            SELECT DATE(uploaded_at) as upload_date, COUNT(*) as file_count
            FROM files 
            WHERE user_id = %s AND uploaded_at >= CURRENT_DATE - INTERVAL '7 days'
            GROUP BY DATE(uploaded_at)
            ORDER BY upload_date
        """, (current_user.user_id,))
        
        trends = cur.fetchall()
        cur.close()
        conn.close()
        
        return {
            "upload_trends": [
                {
                    "date": str(trend[0]),
                    "count": trend[1]
                }
                for trend in trends
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))