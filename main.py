from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from db.connect import supabase
from db.postgres_connect import get_postgres_connection
from services.emailService import sendOTPEmail
from psycopg2 import Binary
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel, Field, EmailStr
from utils.utils import create_access_token, create_refresh_token, verify_token
from dotenv import load_dotenv
import os
import random
import string
import csv
import io
import pandas as pd
import json
from passlib.context import CryptContext
# from dashboard_routes import router as dashboard_router

load_dotenv()

ACCESS_TOKEN_EXPIRE_MINUTES = 15
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_expiry():
    return datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

def generate_otp():
    return "".join(random.choices(string.digits, k=6))

def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str

class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class ResendOTPRequest(BaseModel):
    email: EmailStr

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class UserModel(BaseModel):
    user_id: int
    email: str
    exp: datetime = Field(default_factory=get_expiry)

app = FastAPI()
security = HTTPBearer()

# app.include_router(dashboard_router, prefix="/api", tags=["dashboard"])

@app.on_event("startup")
async def startup_event():
    print("Server started")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token_data = verify_token(credentials.credentials, UserModel)
    return token_data

@app.get("/health-check")
async def root():
    return {"status": "healthy", "message": "API is running"}

@app.post("/register")
async def register(request: RegisterRequest):
    try:
        existing_user = supabase.table("users").select("*").eq("email", request.email).execute()
        if existing_user.data:
            raise HTTPException(status_code=400, detail="User already exists")

        otp = generate_otp()
        otp_expiry = datetime.now(timezone.utc) + timedelta(minutes=10)
        hashed_password = hash_password(request.password)

        user_data = {
            "email": request.email,
            "password": hashed_password,
            "otp": otp,
            "otp_expiry": otp_expiry.isoformat(),
            "is_verified": False,
        }

        supabase.table("users").insert(user_data).execute()
        sendOTPEmail(request.email, otp)

        return {"message": "Registration initiated. Please check your email for OTP verification."}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/verify-otp")
async def verify_otp(request: VerifyOTPRequest):
    try:
        user_response = supabase.table("users").select("*").eq("email", request.email).execute()

        if not user_response.data:
            raise HTTPException(status_code=404, detail="User not found")

        user = user_response.data[0]
        if user["is_verified"]:
            raise HTTPException(status_code=400, detail="User already verified")

        otp_expiry = datetime.fromisoformat(user["otp_expiry"].replace("Z", "+00:00"))
        if datetime.now(timezone.utc) > otp_expiry:
            raise HTTPException(status_code=400, detail="OTP expired")

        if user["otp"] != request.otp:
            raise HTTPException(status_code=400, detail="Invalid OTP")

        supabase.table("users").update({"is_verified": True, "otp": None, "otp_expiry": None}).eq("email", request.email).execute()

        return {"message": "Email verified successfully. You can now login."}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    try:
        user_response = supabase.table("users").select("*").eq("email", request.email).execute()

        if not user_response.data:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        user = user_response.data[0]

        if not user["is_verified"]:
            raise HTTPException(status_code=401, detail="Email not verified")

        if not verify_password(request.password, user["password"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        user_id = user.get("id") or user.get("user_id") or user.get("uuid")
        if not user_id:
            raise HTTPException(status_code=500, detail="User ID not found")

        user_data = {"user_id": user_id, "email": user["email"]}
        access_token = create_access_token(user_data)
        refresh_token = create_refresh_token(user_data)

        return TokenResponse(access_token=access_token, refresh_token=refresh_token)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshTokenRequest):
    try:
        token_data = verify_token(request.refresh_token, UserModel)

        user_response = None
        for id_field in ["user_id"]:
            try:
                user_response = supabase.table("users").select("*").eq(id_field, token_data.user_id).execute()
                if user_response.data:
                    break
            except:
                continue

        if not user_response.data:
            raise HTTPException(status_code=401, detail="User not found")

        user = user_response.data[0]

        user_id = user.get("id") or user.get("user_id") or user.get("uuid")
        if not user_id:
            raise HTTPException(status_code=500, detail="User ID not found")

        user_data = {"user_id": user_id, "email": user["email"]}
        new_access_token = create_access_token(user_data)
        new_refresh_token = create_refresh_token(user_data)

        return TokenResponse(access_token=new_access_token, refresh_token=new_refresh_token)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

@app.post("/resend-otp")
async def resend_otp(request: ResendOTPRequest):
    try:
        user_response = supabase.table("users").select("*").eq("email", request.email).execute()
        
        if not user_response.data:
            raise HTTPException(status_code=404, detail="User not found")
        
        user = user_response.data[0]
        if user["is_verified"]:
            raise HTTPException(status_code=400, detail="User already verified")
        
        otp = generate_otp()
        otp_expiry = datetime.now(timezone.utc) + timedelta(minutes=10)
        
        supabase.table("users").update({
            "otp": otp,
            "otp_expiry": otp_expiry.isoformat()
        }).eq("email", request.email).execute()
        
        sendOTPEmail(request.email, otp)
        
        return {"message": "OTP resent successfully. Please check your email."}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload-csv")
async def upload_csv(
    table_name: str = Form(...),
    column_names: str = Form(...),
    file: UploadFile = File(...),
    current_user: UserModel = Depends(get_current_user),
):
    try:
        if not file.filename.endswith(".csv"):
            raise HTTPException(status_code=400, detail="File must be CSV")

        os.makedirs("data", exist_ok=True)
        file_path = f"data/{table_name}_{current_user.user_id}.csv"
        
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        metadata_path = f"data/{table_name}_{current_user.user_id}.json"
        metadata = {
            "table_name": table_name,
            "column_names": column_names,
            "filename": file.filename,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        with open(metadata_path, "w") as f:
            json.dump(metadata, f)
        
        return {
            "message": "Successfully stored CSV file locally",
            "table_name": table_name,
            "filename": file.filename
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload-csv-db")
async def upload_csv_db(
    table_name: str = Form(...),
    column_names: str = Form(...),
    file: UploadFile = File(...),
    current_user: UserModel = Depends(get_current_user),
):
    try:
        if not file.filename.endswith(".csv"):
            raise HTTPException(status_code=400, detail="File must be CSV")

        file_data = await file.read()
        
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
                metadata JSONB,
                uploaded_at TIMESTAMP DEFAULT NOW()
            );
        """)
        
        metadata = {
            "table_name": table_name,
            "column_names": column_names,
            "file_type": "csv"
        }
        
        cur.execute("""
            INSERT INTO files (user_id, filename, original_name, file_data, file_size, mime_type, metadata) 
            VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
        """, (current_user.user_id, f"{table_name}_{file.filename}", file.filename, 
              Binary(file_data), len(file_data), "text/csv", json.dumps(metadata)))
        
        file_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        
        return {
            "message": "Successfully stored CSV file in PostgreSQL database",
            "table_name": table_name,
            "filename": file.filename,
            "file_id": file_id
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get-data/{table_name}")
async def get_data(
    table_name: str,
    limit: int = 100,
    offset: int = 0,
    current_user: UserModel = Depends(get_current_user)
):
    try:
        file_path = f"data/{table_name}_{current_user.user_id}.csv"
        metadata_path = f"data/{table_name}_{current_user.user_id}.json"
        
        if not os.path.exists(file_path) or not os.path.exists(metadata_path):
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        with open(metadata_path, "r") as f:
            metadata = json.load(f)
        
        columns = [col.strip() for col in metadata["column_names"].split(",")]
        
        df = pd.read_csv(file_path)
        df_filtered = df[columns] if all(col in df.columns for col in columns) else df
        
        start = offset
        end = offset + limit
        data_slice = df_filtered.iloc[start:end]
        
        return {
            "data": data_slice.to_dict(orient="records"),
            "total_rows": len(df_filtered),
            "returned_rows": len(data_slice),
            "columns": list(df_filtered.columns)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get-data-db/{table_name}")
async def get_data_db(
    table_name: str,
    limit: int = 100,
    offset: int = 0,
    current_user: UserModel = Depends(get_current_user)
):
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT file_data, metadata FROM files 
            WHERE user_id = %s AND metadata->>'table_name' = %s AND metadata->>'file_type' = 'csv'
        """, (current_user.user_id, table_name))
        
        result = cur.fetchone()
        cur.close()
        conn.close()
        
        if not result:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        file_data, metadata = result
        metadata_dict = json.loads(metadata)
        columns = [col.strip() for col in metadata_dict["column_names"].split(",")]
        
        df = pd.read_csv(io.BytesIO(bytes(file_data)))
        df_filtered = df[columns] if all(col in df.columns for col in columns) else df
        
        start = offset
        end = offset + limit
        data_slice = df_filtered.iloc[start:end]
        
        return {
            "data": data_slice.to_dict(orient="records"),
            "total_rows": len(df_filtered),
            "returned_rows": len(data_slice),
            "columns": list(df_filtered.columns)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@app.get("/get-columns/{table_name}")
async def get_columns(
    table_name: str,
    current_user: UserModel = Depends(get_current_user)
):
    try:
        file_path = f"data/{table_name}_{current_user.user_id}.csv"
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        df = pd.read_csv(file_path)
        
        return {
            "table_name": table_name,
            "columns": list(df.columns),
            "total_columns": len(df.columns)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload-file")
async def upload_file(
    file: UploadFile = File(...),
    current_user: UserModel = Depends(get_current_user)
):
    try:
        file_data = await file.read()
        
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
            INSERT INTO files (user_id, filename, original_name, file_data, file_size, mime_type) 
            VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
        """, (current_user.user_id, f"{current_user.user_id}_{file.filename}", file.filename, 
              Binary(file_data), len(file_data), file.content_type))
        
        file_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        
        return {
            "message": "File uploaded successfully to PostgreSQL database",
            "filename": file.filename,
            "file_id": file_id
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/list-files-db")
async def list_files_db(
    current_user: UserModel = Depends(get_current_user)
):
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT id, filename, original_name, file_size, mime_type, uploaded_at 
            FROM files WHERE user_id = %s ORDER BY uploaded_at DESC
        """, (current_user.user_id,))
        
        files = cur.fetchall()
        cur.close()
        conn.close()

        return {
            "files": [
                {
                    "file_id": file[0],
                    "filename": file[1],
                    "original_name": file[2],
                    "file_size": file[3],
                    "mime_type": file[4],
                    "uploaded_at": file[5]
                }
                for file in files
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get-file-data/{file_id}")
async def get_file_data(
    file_id: int,
    limit: int = 100,
    offset: int = 0,
    current_user: UserModel = Depends(get_current_user)
):
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
        
        if not original_name.lower().endswith('.csv'):
            raise HTTPException(status_code=400, detail="File is not a CSV")
        
        try:
            # Try different encodings
            for encoding in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
                try:
                    df = pd.read_csv(io.BytesIO(bytes(file_data)), encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise Exception("Could not decode file with any supported encoding")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error reading CSV: {str(e)}")
        
        start = offset
        end = offset + limit
        data_slice = df.iloc[start:end]
        
        data_records = data_slice.to_dict(orient="records")
        
        import math
        for record in data_records:
            for key, value in record.items():
                if isinstance(value, float) and math.isnan(value):
                    record[key] = None
        
        return {
            "data": data_records,
            "total_rows": len(df),
            "returned_rows": len(data_slice),
            "columns": list(df.columns),
            "filename": original_name
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get-file-columns/{file_id}")
async def get_file_columns(
    file_id: int,
    current_user: UserModel = Depends(get_current_user)
):
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
            raise HTTPException(status_code=400, detail="File is not a CSV")
        
        # Try different encodings
        for encoding in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
            try:
                df = pd.read_csv(io.BytesIO(bytes(file_data)), encoding=encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise HTTPException(status_code=400, detail="Could not decode CSV file")
        
        return {
            "filename": original_name,
            "columns": list(df.columns),
            "total_columns": len(df.columns),
            "file_id": file_id
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate-chart-db")
async def generate_chart_db(
    file_id: int = Form(...),
    chart_type: str = Form(...),
    x_column: str = Form(...),
    y_column: str = Form(None),
    current_user: UserModel = Depends(get_current_user)
):
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT file_data, mime_type FROM files 
            WHERE id = %s AND user_id = %s
        """, (file_id, current_user.user_id))
        
        result = cur.fetchone()
        cur.close()
        conn.close()
        
        if not result:
            raise HTTPException(status_code=404, detail="File not found")
        
        file_data, mime_type = result
        
        if not mime_type or 'csv' not in mime_type.lower():
            raise HTTPException(status_code=400, detail="File is not a CSV")
        
        # Try different encodings
        for encoding in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
            try:
                df = pd.read_csv(io.BytesIO(bytes(file_data)), encoding=encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise HTTPException(status_code=400, detail="Could not decode CSV file")
        
        if x_column not in df.columns:
            raise HTTPException(status_code=400, detail="X column not found")
        
        if chart_type == "pie":
            data = df[x_column].dropna().value_counts().to_dict()
            return {
                "chart_type": "pie",
                "data": [{"label": str(k), "value": int(v)} for k, v in data.items()]
            }
        
        if y_column and y_column not in df.columns:
            raise HTTPException(status_code=400, detail="Y column not found")
        
        if chart_type in ["bar", "line", "scatter"]:
            if not y_column:
                raise HTTPException(status_code=400, detail="Y column required")
            
            df_filtered = df[[x_column, y_column]].dropna()
            
            x_values = df_filtered[x_column].tolist()
            y_values = df_filtered[y_column].tolist()
            
            import math
            x_clean = [str(x) if not (isinstance(x, float) and math.isnan(x)) else "" for x in x_values]
            y_clean = [float(y) if not (isinstance(y, float) and math.isnan(y)) else 0 for y in y_values]
            
            return {
                "chart_type": chart_type,
                "x": x_clean,
                "y": y_clean,
                "x_column": x_column,
                "y_column": y_column
            }
        
        raise HTTPException(status_code=400, detail="Invalid chart type")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/list-files")
async def list_files(
    current_user: UserModel = Depends(get_current_user)
):
    try:
        uploads_dir = "uploads"
        if not os.path.exists(uploads_dir):
            return {"files": []}
        
        user_files = []
        prefix = f"{current_user.user_id}_"
        
        for filename in os.listdir(uploads_dir):
            if filename.startswith(prefix):
                file_path = os.path.join(uploads_dir, filename)
                original_name = filename[len(prefix):]
                file_size = os.path.getsize(file_path)
                
                user_files.append({
                    "filename": original_name,
                    "file_size": file_size,
                    "uploaded_at": os.path.getctime(file_path)
                })
        
        return {"files": user_files}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class ChartRequest(BaseModel):
    table_name: str
    chart_type: str
    x_column: str
    y_column: str = None
    
@app.post("/generate-chart")
async def generate_chart(
    request: ChartRequest,
    current_user: UserModel = Depends(get_current_user)
):
    try:
        file_path = f"data/{request.table_name}_{current_user.user_id}.csv"
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        df = pd.read_csv(file_path)
        
        if request.x_column not in df.columns:
            raise HTTPException(status_code=400, detail="X column not found")
        
        if request.chart_type == "pie":
            data = df[request.x_column].value_counts().to_dict()
            return {
                "chart_type": "pie",
                "data": [{"label": k, "value": v} for k, v in data.items()]
            }
        
        if request.y_column and request.y_column not in df.columns:
            raise HTTPException(status_code=400, detail="Y column not found")
        
        if request.chart_type in ["bar", "line", "scatter"]:
            if not request.y_column:
                raise HTTPException(status_code=400, detail="Y column required")
            
            df_filtered = df[[request.x_column, request.y_column]].dropna()
            
            return {
                "chart_type": request.chart_type,
                "x": df_filtered[request.x_column].tolist(),
                "y": df_filtered[request.y_column].tolist(),
                "x_column": request.x_column,
                "y_column": request.y_column
            }
        
        raise HTTPException(status_code=400, detail="Invalid chart type")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))